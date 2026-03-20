from .common import dbg
from .build_utils import Config, build_packages
from .uv_utils import get_internal_packages
from .uv_utils import LockedPackage
from pathlib import Path


def build_dependencies(pkgs: list[LockedPackage], config: Config) -> list[str]:
    return build_packages(pkgs, config)


def main():
    from argparse import ArgumentParser
    import logging

    parser = ArgumentParser(description="Build internal dependencies for a project")
    parser.add_argument("-p", "--pyproject", type=Path, default=Path("pyproject.toml"), help="Path to the pyproject.toml file")
    parser.add_argument("-l", "--lock-file", type=Path, default=Path("uv.lock"), help="Path to the uv.lock file")
    parser.add_argument("-d", "--dist-dir", type=Path, default=Path("dist"), help="Directory to store built dependencies")

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)

    config = Config(
        pyproject=args.pyproject.resolve(),
        lock_file=args.lock_file.resolve(),
        dist_dir=args.dist_dir.resolve(),
        build_dir=Path(".build").resolve()
    )

    pkgs = get_internal_packages(config.lock_file)
    dbg("Internal packages to build: %s", pkgs)
    build_packages(pkgs, config)


if __name__ == "__main__":
    main()