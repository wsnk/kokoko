from .common import dbg, Uv, Git, Wheel
from .uv_utils import LockedPackage
from pathlib import Path
from dataclasses import dataclass
from typing import Iterable


@dataclass
class Config:
    pyproject: Path
    lock_file: Path
    dist_dir: Path = Path("./dist")  # directory to store built artifacts
    build_dir: Path = Path(".build")  # temporary directory for building dependencies


def _build_wheel(project_dir: Path, config: Config) -> Path:    
    Uv(project_dir).build(config.dist_dir, ["--wheel"])


def build_local_dependency(pkg: LockedPackage, config: Config) -> str:
    dbg("Building local dependency '%s' (version: %s) from source '%s'...", pkg.name, pkg.version, pkg.source)
    project_dir = Path(pkg.source["directory"])
    _build_wheel(project_dir, config)


def build_git_dependency(pkg: LockedPackage, config: Config) -> str:
    dbg("Building git dependency '%s' (version: %s) from source '%s'...", pkg.name, pkg.version, pkg.source)
    url = pkg.source["git"]
    project_dir = Git.ensure_repo(url, config.build_dir/pkg.name)
    _build_wheel(project_dir, config)



def build_dependency(pkg: LockedPackage, config: Config) -> str:
    if pkg.source.get("directory"):
        return build_local_dependency(pkg, config)
    if pkg.source.get("git"):
        return build_git_dependency(pkg, config)
    if pkg.source.get("virtual"):
        dbg("Package '%s' is a virtual dependency, skipping build.", pkg.name)
        return None
    if pkg.source.get("editable") == ".":
        dbg("Package '%s' is an editable local dependency, skipping build.", pkg.name)
        return None

    raise ValueError(f"Unsupported source type for package '{pkg.name}': {pkg.source}")


def build_packages(pkgs: list[LockedPackage], config: Config) -> list[str]:
    for pkg in pkgs:
        build_dependency(pkg, config)


def get_wheels(dist_dir: Path) -> Iterable[Wheel]:
    for p in dist_dir.iterdir():
        if not p.is_file():
            continue
        if not p.name.endswith(".whl"):
            continue
        yield Wheel.from_path(p)
