import argparse
import logging
from pathlib import Path
from .common import inf, dbg

class BuildDistributionBundle:
    """ Build a distribution bundle of a uv-locked python project.
    """

    CLI_NAME = "build-distr-bundle"


# @dataclass
# class Config:
#     pyproject: Path
#     lock_file: Path
#     dist_dir: Path = Path("./dist")  # directory to store built artifacts
#     build_dir: Path = Path(".build")  # temporary directory for building dependencies

    @classmethod
    def add_arguments(cls, ap: argparse.ArgumentParser):
        ap.add_argument("--pyproject-dir", type=Path, default=Path("."),
                        help="Path to the pyproject.toml of the project")
        ap.add_argument("--dist-dir", type=Path, default=Path("./dist"),
                        help="Directory to store built distribution bundles (default: ./dist)")

    @classmethod
    def run(cls, args):
        # 1. Ensure uv.lock and collect internal dependecies
        # 2. Build internal dependencies
        # 3. Build the project itself
        # 4. Make local simple index
        # 5. Make a sync script

        from .uv_utils import get_internal_packages
        from .build_utils import build_packages, Config, get_wheels
        from .make_index import make_index
        from .common import Uv
        from .pyproject_utils import PyProject, parse_dependencies
        import shutil

        config = Config(
            pyproject=(args.pyproject_dir/"pyproject.toml").resolve(),
            lock_file=(args.pyproject_dir/"uv.lock").resolve(),
            dist_dir=args.dist_dir.resolve()
        )

        if not config.lock_file.is_file():
            raise FileNotFoundError(f"uv.lock not found at '{config.lock_file}'")

        internal_packages = get_internal_packages(config.lock_file)
        inf("Found %d internal packages in '%s'", len(internal_packages), config.lock_file)

        build_packages(internal_packages, config)
        Uv(args.pyproject_dir).build(config.dist_dir)

        # make simple index for local dependencies
        index_dir = config.dist_dir / "index"
        make_index(config.dist_dir, index_dir)

        # create modified pyproject for distribution bundle
        pyproject = PyProject(config.pyproject)
        wheeled_packages = set(w.name for w in get_wheels(config.dist_dir))

        pyproject.remove_from_uv_sources(wheeled_packages)

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

        pyproject.save(config.dist_dir/"pyproject.toml")

        # re-lock the bundle using local index
        rel_index_path = index_dir.relative_to(config.dist_dir)

        shutil.copy(config.lock_file, config.dist_dir/"uv.lock")
        Uv(config.dist_dir).lock(["--index", str(rel_index_path)])

        # make a sync script to sync the bundle to a target project
        sync_script = config.dist_dir / "sync.sh"
        sync_script.write_text(f"""\
#!/bin/bash
set -eo pipefail

BUNDLE_DIR="$(realpath "$(dirname "$0")")"
cd "$BUNDLE_DIR"
uv sync --no-dev --no-editable --locked
""", encoding="utf-8")
        sync_script.chmod(0o755)
        inf("Distribution bundle created at '%s'", config.dist_dir)



def main(raw_args=None):
    ap = argparse.ArgumentParser(description="Packing Utils CLI")

    g = ap.add_mutually_exclusive_group()
    g.set_defaults(log_level=logging.INFO)
    g.add_argument("-v", "--verbose", action="store_const", const=logging.DEBUG, dest="log_level",
                   help="Enable debug logs")
    g.add_argument("-q", "--quiet", action="store_const", const=logging.WARNING, dest="log_level",
                   help="Be quiet in logs")

    subparsers = ap.add_subparsers(title="Commands", required=True, dest="command")
    for it in (BuildDistributionBundle,):
        p = subparsers.add_parser(it.CLI_NAME, help=it.__doc__)
        it.add_arguments(p)
        p.set_defaults(func=it.run)

    args = ap.parse_args(raw_args)
    logging.basicConfig(level=args.log_level)

    if hasattr(args, "func"):
        args.func(args)
    else:
        ap.print_help()
