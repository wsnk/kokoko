import tomllib
from dataclasses import dataclass
from pathlib import Path
from .common import LockedPackage, dbg


PUBLIC_INDEXES = [
    "https://pypi.org/simple"
]


def _is_public_source(source: dict) -> bool:
    registry = source.get("registry")
    return registry in PUBLIC_INDEXES


@dataclass
class LockedPackage:
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
    internal = []
    for pkg in get_locked_packages(uvlock):
        if pkg.source and _is_public_source(pkg.source):
            dbg("Skipping public package '%s' (version: %s)", pkg.name, pkg.version)
            continue
        internal.append(pkg)
        dbg("Collected internal package '%s' (version: %s, source: %s)", pkg.name, pkg.version, pkg.source)
    
    dbg("Total internal packages collected: %d", len(internal))
    return internal
