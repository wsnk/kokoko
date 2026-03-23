import tomllib
import tomli_w
from pathlib import Path
from .common import dbg, normalized_name
from packaging.requirements import Requirement


def _remove_empty_leafs(d: dict) -> dict:
    ret = {}
    for k, v in d.items():
        if isinstance(v, dict):
            v = _remove_empty_leafs(v)
            if not v:
                continue
        if isinstance(v, list) and not v:
            continue
        ret[k] = v
    return ret


def parse_dependencies(dependencies: list[str]) -> list[Requirement]:
    return [Requirement(it) for it in dependencies]


class PyProject:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self._data = None

    @property
    def data(self):
        if self._data is None:
            self.load()
        return self._data

    @property
    def dependencies(self) -> list[Requirement]:
        deps = self.data.get("project", {}).get("dependencies", [])
        return parse_dependencies(deps)

    def load(self):
        dbg("Loading pyproject data from '%s'...", self.path)
        self._data = tomllib.loads(self.path.read_text())

    def save(self, path: Path = None, *, remove_empty_leafs=True):
        target = path or self.path
        if remove_empty_leafs:
            dbg("Removing empty leafs from pyproject data before saving...")
            self._data = _remove_empty_leafs(self.data)
        dbg("Saving pyproject data to '%s'...", target)
        target.write_text(tomli_w.dumps(self._data), encoding="utf-8")

    def remove_from_uv_sources(self, packages: list[str]):
        uv_sources = self.data.get("tool", {}).get("uv", {}).get("sources", {})
        if not uv_sources:
            dbg("No uv.sources found in pyproject, skipping...")
            return

        pkgs_to_remove = [
            it for it in uv_sources
            if (normalized_name(it) in packages)
        ]

        for pkg in pkgs_to_remove:
            dbg("Removing uv.source for '%s' dependency...", pkg)
            uv_sources.pop(pkg)
