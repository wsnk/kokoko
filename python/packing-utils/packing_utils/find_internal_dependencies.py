import argparse
import logging
from pathlib import Path
from .common import LockedPackage
from .uv_utils import get_internal_packages


def collect_internal_dependencies(uvlock: Path) -> list[LockedPackage]:
    return get_internal_packages(uvlock)


def main():
    parser = argparse.ArgumentParser(description="Extracts internal dependencies for a project")
    parser.add_argument("-l", "--lock-file", type=Path, default=Path("uv.lock"), help="Path to the uv.lock file")

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)

    pacakges = get_internal_packages(args.lock_file)
    print("Internal dependencies:")
    for pkg in pacakges:
        print(f"- {pkg.name} (version: {pkg.version}, source: {pkg.source})")


if __name__ == "__main__":
    main()
