import subprocess
import tomllib
from pathlib import Path
from dataclasses import dataclass
import os
import json
import asyncio
from .log import dbg, inf, err
from .proc import run, ToFile, run_async


@dataclass
class ProjectVersionInfo:
    name: str
    version: str
    # other fields can be added as needed


class Uv:
    def __init__(self, project_dir: Path, *, asynchronous: bool = False):
        self.project_dir = project_dir
        self.run_func = run_async if asynchronous else run

    async def version(self) -> ProjectVersionInfo:
        """Returns version info of the project, using `uv version` command.
        """
        proc = await run_async(["uv", "version", "--frozen", "--output-format", "json"],
            cwd=self.project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        data = json.loads(proc.stdout)
        dbg("Project version info: %s", data)
        return ProjectVersionInfo(name=data["package_name"], version=data["version"])

    async def build(self, outdir: Path = None, args: list[str] = None, *, stdout=None, stderr=None):
        """Builds the project, using 'uv build' command.

        If outdir is provided, the built artifacts will be stored there.
        """

        if args is None:
            args = []
        if outdir is not None:
            outdir.mkdir(parents=True, exist_ok=True)
            args += ["--out-dir", str(outdir.resolve())]

        dbg("Building project using 'uv build' command, args: %s", args)
        await run_async(
            ["uv", "build", *args],
            cwd=self.project_dir,
            stdout=stdout,
            stderr=stderr
        )

    def lock(self, args: list[str] = None):
        """Lock the project dependencies, using 'uv lock' command.
        """

        if args is None:
            args = []
        dbg("Generating lock file using 'uv lock' command, args: %s", args)
        result = subprocess.run(["uv", "lock", *args], cwd=self.project_dir)
        if result.returncode != 0:
            err("Failed to generate lock file: %s", result.stderr)
            raise RuntimeError(f"uv lock failed with exit code {result.returncode}")
        dbg("Lock file generated successfully. Output:\n%s", result.stdout)


@dataclass
class LockedPackage:
    """ Data of a locked package from `uv.lock` file
    """
    name: str
    version: str
    source: dict


def get_locked_packages(uvlock: Path):
    dbg("Reading locked packages from '%s'...", uvlock)
    data = tomllib.loads(uvlock.read_text())

    package_list =  data.get("package", [])
    dbg("Found %d packages in '%s'", len(package_list), uvlock)

    for package in package_list:
        dbg("Processing package: %s", package)
        name = package["name"]
        version = package["version"]
        source = package.get("source")
        yield LockedPackage(name, version, source)


def get_internal_packages(uvlock: Path) -> list[LockedPackage]:
    from .python import PUBLIC_INDEXES

    internal = []
    for pkg in get_locked_packages(uvlock):
        if pkg.source:
            if pkg.source.get("registry") in PUBLIC_INDEXES:
                dbg("Skipping public package '%s' (version: %s)", pkg.name, pkg.version)
                continue

        internal.append(pkg)
        dbg("Found internal package %r: source=%r", pkg.name, pkg.source)

    dbg("Total internal packages collected: %d", len(internal))
    return internal


async def build_wheel(
    project_dir: Path, dist_dir: Path, *, output_path: Path | None = None
):
    stdout = None
    stderr = None
    if output_path is not None:
        stdout = ToFile(output_path)
        stderr = subprocess.STDOUT

    await Uv(project_dir).build(
        dist_dir,
        ["--wheel"],
        stdout=stdout,
        stderr=stderr
    )


async def build_many(
    project_dirs: list[Path],
    dist_dir: Path, *,
    logs_dir: Path | None = None,
):
    dbg("Building %d projects in parallel: %s", len(project_dirs), project_dirs)

    async def build_one(project_dir: Path) -> Path:
        uv = Uv(project_dir)

        stdout = None
        stderr = None

        if logs_dir is not None:
            version_info = await uv.version()
            output_path = logs_dir / f"{version_info.name}-build.log"
            stdout = ToFile(output_path)
            stderr = subprocess.STDOUT
            dbg("Save build logs for project '%s' to '%s'...", version_info.name, output_path)

        await uv.build(
            outdir=dist_dir,
            args=["--wheel"],
            stdout=stdout,
            stderr=stderr
        )
    
    # for it in project_dirs:
    #     await build_one(it)
    await asyncio.gather(
        *(build_one(it) for it in project_dirs)
    )
