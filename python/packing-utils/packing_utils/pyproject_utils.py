from os import name
import re
import tomllib
import tomli_w
import argparse
import logging
from dataclasses import dataclass
from pathlib import Path


_log = logging.getLogger(__name__)


def dbg(*args, **kwargs):
    _log.debug(*args, **kwargs, stacklevel=2)



@dataclass
class Wheel:
    path: Path
    name: str
    version: str


@dataclass
class Dependency:
    name: str
    extras: list[str]
    version: str
    source: dict

    @property
    def normalized_name(self) -> str:
        return self.name.lower().replace("-", "_")

    def to_string(self) -> str:
        extras_str = f"[{','.join(self.extras)}]" if self.extras else ""
        return f"{self.name}{extras_str}=={self.version}"

    @classmethod
    def from_string(cls, dep_str: str):
        # This is a very naive parser and may not cover all cases
        name_extras_version = dep_str.split(maxsplit=1)[0]  # not fully correct, but OK

        name = name_extras_version.split("==")[0].split(">=")[0].split("<=")[0].split(">")[0].split("<")[0]
        version = name_extras_version[len(name):].lstrip("=>< ")

        extras = []
        if "[" in name and "]" in name:
            name, extras_str = name.split("[", 1)
            extras_str = extras_str.rstrip("]")
            extras = [e.strip() for e in extras_str.split(",")]

        return cls(name=name, extras=extras, version=version, source={})


def normalize(name: str) -> str:
    return name.lower().replace("-", "_")



def rewrite_list(dep_list, wheel_map: dict[str, Wheel], uv_sources=None):
    new = []

    for dep in dep_list:
        if not isinstance(dep, str):
            raise ValueError(f"Unsupported dependency format ({type(dep)}): {dep}")
        
        dependency = Dependency.from_string(dep)
        dbg("Processing dependency: %s", dependency)
        
        if dependency.normalized_name not in wheel_map:
            new.append(dep)
            dbg("No wheel found for dependency '%s', keeping unchanged.", dependency.name)
            continue
        
        wheel = wheel_map[dependency.normalized_name]
        dependency.version = wheel.version
        dependency_str = dependency.to_string()
        new.append(dependency_str)
        dbg("Dependency '%s' replaced with: %s", dependency.name, dependency_str)

        if not uv_sources:
            continue
        
        dep_source = uv_sources.get(dependency.name) or uv_sources.get(dependency.normalized_name)
        if not dep_source:
            dbg("No uv.source found for '%s' dependency", dependency.name)
            continue
        
        dep_source.clear()
        dep_source["path"] = wheel.path

    return new


def get_wheels(dir: Path) -> dict[str, Wheel]:
    WHEEL_REGEX = re.compile(
        r"(?P<name>.+?)-(?P<version>\d+[^-]*)-.*\.whl"
    )

    wheel_map = {}

    for whl in dir.glob("*.whl"):
        m = WHEEL_REGEX.match(whl.name)
        if not m:
            continue

        name = normalize(m.group("name"))
        wheel = Wheel(path=whl, name=name, version=m.group("version"))
        wheel_map[name] = wheel
        dbg("Found wheel: %s", wheel)

    return wheel_map


def replace_dependencies_with_local_wheels(dist_dir: Path, pyproject: Path) -> dict:
    wheel_map = get_wheels(dist_dir)

    data = tomllib.loads(pyproject.read_text())

    uv_sources = data.get("tool", {}).get("uv", {}).get("sources", {})
    dbg("UV sources found: %s", uv_sources)

    # 3. Rewrite main deps
    dependencies = data.get("project", {}).get("dependencies", [])
    if dependencies:
        dependencies = rewrite_list(dependencies, wheel_map, uv_sources)

    # 4. Rewrite optional deps
    opt = data.get("project", {}).get("optional-dependencies", {})
    for group, deps in opt.items():
        opt[group] = rewrite_list(deps, wheel_map, uv_sources)
   
    data.get("project", {})["dependencies"] = dependencies

    # Update UV sources if modified
    if uv_sources:
        for it, source in uv_sources.items():
            src_path = source.get("path")
            if src_path and isinstance(src_path, Path):
                dbg("Updating uv.source path for '%s' from '%s' to wheel path...", it, src_path)
                source["path"] = str(src_path.relative_to(pyproject.parent))

    return data


def remove_dependecies_paths_uv_sources(dist_dir: Path, pyproject: Path) -> None:
    wheel_map = get_wheels(dist_dir)
    data = tomllib.loads(pyproject.read_text())

    uv_sources = data.get("tool", {}).get("uv", {}).get("sources", {})
    dbg("UV sources found: %s", uv_sources)

    to_remove = []

    for dep_name, dep_data  in uv_sources.items():
        normalize(dep_name)
        if dep_name in wheel_map:
            to_remove.append(dep_name)
        elif normalize(dep_name) in wheel_map:
            to_remove.append(dep_name)
        else:
            dbg("No wheel found for '%s' uv.source, skipping...", dep_name)
            continue
    
    for dep_name in to_remove:
        dbg("Removing uv.source for '%s' dependency...", dep_name)
        uv_sources.pop(dep_name)

    return data



def main():
    parser = argparse.ArgumentParser(description="Convert path dependencies in pyproject.toml to versioned dependencies.")
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"), help="Path to the pyproject.toml file")
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"), help="Directory containing the built wheel files")
    parser.add_argument("--output", type=Path, default=None, help="Path to write the updated pyproject.toml file")

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)

    ROOT = Path(args.pyproject)
    if not ROOT.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {ROOT}")
    ROOT = ROOT.resolve()

    dist_dir = args.dist_dir
    if not dist_dir.exists() or not dist_dir.is_dir():
        raise FileNotFoundError(f"Dist directory not found at {dist_dir}")

    data = replace_dependencies_with_local_wheels(dist_dir, ROOT)

    output = tomli_w.dumps(data)
    if args.output:
        Path(args.output).write_text(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
