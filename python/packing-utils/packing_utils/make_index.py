#!/usr/bin/env python3
"""
Generate a minimal PEP-503 "simple" index in ./simple from wheel/sdist files in ./dist.
Serve the parent directory with: python -m http.server 8000
Then use uv with --index http://localhost:8000/simple/
"""
import re
import os
from pathlib import Path
from urllib.parse import quote
from .common import dbg, inf, Wheel
from .build_utils import get_wheels


def normalize(pkg_name: str) -> str:
    return re.sub(r"[-_.]+", "-", pkg_name).lower()


def relpath(from_dir: Path, to_file: Path) -> str:
    return os.path.relpath(to_file, start=from_dir)


def make_project_page(parent_dir: Path, name: str, wheels: list[Wheel]):
    pkg_dir = parent_dir / name
    pkg_dir.mkdir(exist_ok=True)

    lines = [
        "<!doctype html>\n<html><head><meta charset='utf-8'></head><body>\n"
    ]

    whl: Wheel
    for whl in sorted(wheels):
        webpath = relpath(pkg_dir, whl.path)
        dbg("Adding link for package '%s': %s -> %s", name, webpath, whl)
        lines.append(f"<a href=\"{webpath}\">{whl.name}</a><br/>\n")

    lines.append("</body></html>\n")

    (pkg_dir / "index.html").write_text("".join(lines), encoding="utf-8")


def make_index(dist_dir: Path, out_dir: Path):
    """
    Generate a PEP-503 'simple' index in ./simple that links to ../dist/<file>.
    This layout works with both file:// and http:// URLs.
    """

    if not dist_dir.exists() or not dist_dir.is_dir():
        raise SystemExit(f"Distribution '{dist_dir}' directory not found")

    out_dir.mkdir(exist_ok=True)

    packages: dict[str, list[Wheel]] = {}
    for wheel in get_wheels(dist_dir):
        packages.setdefault(wheel.name, []).append(wheel)

    dbg("Found %d packages for index", len(packages))

    # write top-level index
    index_lines = [
        "<!doctype html>\n",
        "<html><head><meta charset='utf-8'><title>Simple Index</title></head><body>\n",
        "<h1>Simple Index</h1>\n",
        "<ul>\n",
    ]
    for pkg in sorted(packages):
        index_lines.append(f"  <li><a href=\"{quote(pkg)}/\">{pkg}</a></li>\n")
    index_lines.append("</ul>\n</body></html>\n")

    (out_dir/ "index.html").write_text("".join(index_lines), encoding="utf-8")

    # per-package pages
    for pkg, whls in packages.items():
        make_project_page(out_dir, pkg, whls)

    inf("Index generated successfully at '%s': %d packages", out_dir, len(packages))
