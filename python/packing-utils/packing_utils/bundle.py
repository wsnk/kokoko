from .uv_utils import get_internal_packages
from .build_utils import build_packages, Config as BuildConfig, get_wheels
from .make_index import make_index
from .common import Uv, dbg, inf
from .pyproject_utils import PyProject, parse_dependencies
import shutil
from pathlib import Path
from dataclasses import dataclass


@dataclass(kw_only=True)
class Config:
    pyproject_dir: Path
    bundle_dir: Path = Path("./bundle")  # directory to store the distribution bundle
    build_dir: Path | None = None  # Path(".build")  # temporary directory for building dependencies

    @property
    def pyproject_toml(self) -> Path:
        return self.pyproject_dir / "pyproject.toml"

    @property
    def uv_lock(self) -> Path:
        return self.pyproject_dir / "uv.lock"

    @property
    def wheels_dir(self) -> Path:
        return self.bundle_dir / "wheels"

    @property
    def index_dir(self) -> Path:
        return self.bundle_dir / "index"

    @property
    def build_config(self) -> BuildConfig:
        return BuildConfig(
            pyproject=self.pyproject_toml,
            lock_file=self.uv_lock,
            dist_dir=self.wheels_dir,
            build_dir=self.build_dir
        )

    def resolve(self):
        if self.build_dir is None:
            self.build_dir = self.pyproject_dir / ".build"

        self.pyproject_dir = self.pyproject_dir.resolve()
        self.bundle_dir = self.bundle_dir.resolve()
        self.build_dir = self.build_dir.resolve()


def sync_bash(rel_index_path, pyproject: PyProject) -> str:
    return f"""\
#!/bin/bash

set -eo pipefail

BUNDLE_DIR="$(realpath "$(dirname "$0")")"
cd "$BUNDLE_DIR"

export VIRTUAL_ENV="${{VENV_PATH:-"$BUNDLE_DIR/.venv"}}"
echo "Syncing distribution bundle to '$VIRTUAL_ENV'..." >&2

uv sync --no-dev --no-editable --no-install-project --locked
uv pip install --no-deps --reinstall --index '{rel_index_path}' '{pyproject.name}'
"""


def build_bundle(config: Config):
    config.resolve()

    if not config.pyproject_toml.is_file():
        raise FileNotFoundError(f"pyproject.toml not found at '{config.pyproject_toml}'")
    if not config.uv_lock.is_file():
        raise FileNotFoundError(f"uv.lock not found at '{config.uv_lock}'")

    internal_packages = get_internal_packages(config.uv_lock)
    inf("Found %d internal packages in '%s'", len(internal_packages), config.uv_lock)

    build_packages(internal_packages, config.build_config)
    Uv(config.pyproject_dir).build(config.wheels_dir, ["--wheel"])

    # make simple index for local dependencies
    make_index(config.wheels_dir, config.index_dir)

    # create modified pyproject for distribution bundle
    pyproject = PyProject(config.pyproject_toml)
    wheeled_packages = set(w.name for w in get_wheels(config.wheels_dir))

    dbg("Removing uv.sources for wheeled packages...")
    pyproject.remove_from_uv_sources(wheeled_packages)

    dbg("Removing URLs from dependencies that are included in the bundle...")
    # remove URLs from dependencies that are included in the bundle, so that they will be
    # installed from the local simple index
    deps = parse_dependencies(pyproject.data.get("project", {}).get("dependencies", []))
    for it in deps:
        if (it.name not in wheeled_packages) or (it.url is None):
            continue
        dbg("Removing URL from dependency '%s'...", it.name)
        it.url = None
    pyproject.data["project"]["dependencies"] = [str(it) for it in deps]

    # TODO: handle optional dependency groups?

    pyproject.save(config.bundle_dir/"pyproject.toml")

    # re-lock the bundle using local index
    rel_index_path = config.index_dir.relative_to(config.bundle_dir)

    shutil.copy(config.uv_lock, config.bundle_dir/"uv.lock")
    Uv(config.bundle_dir).lock(["--index", str(rel_index_path)])

    # make a sync script to sync the bundle to a target project
    sync_script = config.bundle_dir / "sync.sh"
    sync_script.write_text(sync_bash(rel_index_path, pyproject), encoding="utf-8")
    sync_script.chmod(0o755)

    inf("Distribution bundle created at '%s'", config.bundle_dir)
