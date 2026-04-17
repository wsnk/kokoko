import subprocess
from .common import dbg, Wheel
from .infratools.git import Git
from .infratools.uv import Uv, LockedPackage, build_wheel, build_many
from .infratools.proc import ToFile
from pathlib import Path
from dataclasses import dataclass
from typing import Iterable
import asyncio


@dataclass(kw_only=True)
class Config:
    pyproject: Path
    lock_file: Path
    dist_dir: Path = Path("./dist")  # directory to store built artifacts
    build_dir: Path = Path(".build")  # temporary directory for building dependencies


PackageT = LockedPackage | Path


def _get_package_dir(pkg: PackageT) -> Path:
    if isinstance(pkg, Path):
        return pkg
    return Path(pkg.source["directory"])


def _is_local_package(pkg: PackageT) -> bool:
    if isinstance(pkg, Path):
        return True
    return pkg.source and "directory" in pkg.source


async def _build_wheel(project_dir: Path, config: Config) -> Path:
    ver_info = await Uv(project_dir).version()
    await build_wheel(
        project_dir,
        config.dist_dir,
        output_path=config.build_dir / f"{ver_info.name}-build.log"
    )



async def build_local_dependency(project_dir: Path, config: Config) -> str:
    dbg("Building package from directory: '%s'...", project_dir)
    await _build_wheel(project_dir, config)


async def build_git_dependency(pkg: LockedPackage, config: Config) -> str:
    dbg(
        "Building git dependency '%s' (version: %s) from source '%s'...",
        pkg.name, pkg.version, pkg.source
    )
    url = pkg.source["git"]
    project_dir = Git.ensure_repo(url, config.build_dir/pkg.name)
    await _build_wheel(project_dir, config)



async def build_dependency(pkg: LockedPackage, config: Config) -> str:
    if "directory" in pkg.source:
        project_dir = Path(pkg.source["directory"])
        return await build_local_dependency(project_dir, config)

    if pkg.source.get("git"):
        return await build_git_dependency(pkg, config)
    if pkg.source.get("virtual"):
        dbg("Package '%s' is a virtual dependency, skipping build.", pkg.name)
        return None
    if pkg.source.get("editable") == ".":
        dbg("Package '%s' is an editable local dependency, skipping build.", pkg.name)
        return None

    raise ValueError(f"Unsupported source type for package '{pkg.name}': {pkg.source}")





def build_packages(pkgs: list[PackageT], config: Config) -> list[str]:
    import asyncio

    local_pkgs = [pkg for pkg in pkgs if _is_local_package(pkg)]
    others = [pkg for pkg in pkgs if not _is_local_package(pkg)]

    asyncio.run(
        build_many(
            [_get_package_dir(pkg) for pkg in local_pkgs],
            config.dist_dir,
            logs_dir=config.build_dir
        )
    )

    for pkg in others:
        asyncio.run(build_dependency(pkg, config))


def get_wheels(dist_dir: Path) -> Iterable[Wheel]:
    for p in dist_dir.iterdir():
        if not p.is_file():
            continue
        if not p.name.endswith(".whl"):
            continue
        yield Wheel.from_path(p)


def get_wheel(dist_dir: Path, pkg_name: str) -> Wheel:
    for wheel in get_wheels(dist_dir):
        if wheel.name == pkg_name:
            return wheel
    raise FileNotFoundError(f"Wheel for package '{pkg_name}' not found in '{dist_dir}'")
