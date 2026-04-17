import pytest
from pathlib import Path
from packing_utils.infratools.uv import Uv, build_many
from .common import make_pyproject


@pytest.fixture(scope="module")
def project_a_dir(tmp_path_factory) -> Path:
    tmpdir = tmp_path_factory.mktemp("project-a")
    return make_pyproject(tmpdir, "project-a")


@pytest.fixture(scope="module")
def project_b_dir(tmp_path_factory) -> Path:
    tmpdir = tmp_path_factory.mktemp("project-b")
    return make_pyproject(tmpdir, "project-b")


def create_project_with_files(project_dir: Path, name: str) -> Path:
    file_tree = {
        name: {
            "__init__.py": "",
            "main.py": f"print('Hello from {name}!')"
        }
    }
    return make_pyproject(project_dir, name, file_tree=file_tree)


async def test_build_wheel(project_a_dir: Path, tmp_path):
    """Build wheel for a single project.
    """

    await Uv(project_a_dir).build(
        outdir=tmp_path,
        args=["--wheel"],
    )

    whl_name = "project_a-0.1.0-py3-none-any.whl"
    assert (tmp_path / whl_name).exists()


async def test_build_many_wheels(tmp_path):
    """Build multiple projects concurrently, with saving build logs to files.
    """

    project_syms = "abcdef"

    project_dirs = [
        create_project_with_files(tmp_path/f"project-{n}", f"project-{n}")
        for n in project_syms
    ]

    await build_many(
        project_dirs,
        dist_dir=tmp_path/"dist",
        logs_dir=tmp_path/"logs"
    )

    for n in project_syms:
        assert (tmp_path / "dist" / f"project_{n}-0.1.0-py3-none-any.whl").exists()
        assert (tmp_path / "logs" / f"project-{n}-build.log").exists()
