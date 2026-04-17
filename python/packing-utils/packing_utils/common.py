from dataclasses import dataclass
from pathlib import Path
import logging
import subprocess
from urllib.parse import urlparse, parse_qs
import json
from packaging.utils import parse_wheel_filename, canonicalize_name


_log = logging.getLogger(__name__)


def dbg(*args, **kwargs):
    _log.debug(*args, **kwargs, stacklevel=2)


def inf(*args, **kwargs):
    _log.info(*args, **kwargs, stacklevel=2)


def err(*args, **kwargs):
    _log.error(*args, **kwargs, stacklevel=2)


def normalized_name(name: str) -> str:
    return canonicalize_name(name)
    # see https://packaging.python.org/en/latest/specifications/name-normalization/
    # return re.sub(r"[-_.]+", "-", name).lower()


@dataclass
class Wheel:
    path: Path
    name: str  # normalized name
    version: str = None
    build: str = None
    tags: str = None

    @classmethod
    def from_path(cls, path: Path):
        name, ver, build, tags = parse_wheel_filename(path.name)
        return cls(
            path=path.resolve(),
            name=name,
            version=ver,
            build=build,
            tags=tags
        )
