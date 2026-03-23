import subprocess
import sys
import logging
import tomli_w
from pathlib import Path


def dbg(msg, *args, **kwargs):
    logging.debug(msg, *args, **kwargs)


def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    dbg("Command '%s' stdout:\n%s", " ".join(cmd), result.stdout)
    dbg("Command '%s' stderr:\n%s", " ".join(cmd), result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"Command '{' '.join(cmd)}' failed with exit code {result.returncode}:\n{result.stderr}")


def make_pyproject(project_dir: Path, name: str, version="0.1.0", dependencies=None, **kwargs) -> Path:
    project_dir.mkdir(exist_ok=True)

    pyproject_data = {
        "project": {
            "name": name,
            "version": version,
            "dependencies": dependencies or [],
        },
        **kwargs
    }

    (project_dir / "pyproject.toml").write_text(tomli_w.dumps(pyproject_data))

    subprocess.check_call(["uv", "lock"], cwd=project_dir)
    return project_dir.resolve()


def run_build_distr_bundle(project_dir: Path, dist_dir: Path):
    result = subprocess.run([
        sys.executable, "-m", "packing_utils",
        "--verbose",
        "build-distr-bundle",
        "--pyproject-dir", str(project_dir),
        "--dist-dir", str(dist_dir)
    ], capture_output=True, text=True)
    dbg("CLI stdout:\n%s", result.stdout)
    dbg("CLI stderr:\n%s", result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"CLI failed with exit code {result.returncode}:\n{result.stderr}")


class _Any:
    def __eq__(self, value):
        return True


Any = _Any()
