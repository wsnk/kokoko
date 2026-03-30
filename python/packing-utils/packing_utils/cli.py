import argparse
import logging
from pathlib import Path


class BuildDistributionBundle:
    """ Build a distribution bundle of a uv-locked python project.
    """

    CLI_NAME = "build-distr-bundle"

    @classmethod
    def add_arguments(cls, ap: argparse.ArgumentParser):
        ap.add_argument("--pyproject-dir", type=Path, default=Path("."),
                        help="Path to the pyproject.toml of the project")
        ap.add_argument("--bundle-dir", type=Path, default=Path("./bundle"),
                        help="Directory to store built distribution bundles (default: ./bundle)")

    @classmethod
    def run(cls, args):
        from .bundle import build_bundle, Config

        config = Config(
            pyproject_dir=args.pyproject_dir.resolve(),
            bundle_dir=args.bundle_dir.resolve()
        )
        config.resolve()
        build_bundle(config)



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
