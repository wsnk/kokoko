import shutil
import tempfile
from pathlib import Path
import pytest
from .common import run_build_distr_bundle, make_pyproject, Any, run
from packing_utils.build_utils import get_wheels
from packing_utils.pyproject_utils import PyProject


@pytest.fixture(scope="module")
def module_tmpdir(tmp_path_factory) -> Path:
    # Create a temporary directory for the entire test module
    tmpdir = tmp_path_factory.mktemp("module-tmpdir")
    return tmpdir


def mk_hello_py(who: str, path: Path):
    path.write_text(f"""
def main():
    print('Hello, {who}!')

if __name__ == '__main__':
    main()
""")


@pytest.fixture(scope="module")
def localpkg_dep_1(module_tmpdir) -> Path:
    proj_dir = make_pyproject(
        module_tmpdir / "localpkg_dep_1",
        "localpkg_dep_1",
        tool={
            "uv": {
                "package": True,
            }
        }
    )
    mk_hello_py("localpkg_dep_1", proj_dir / "localpkg_dep_1.py")
    return proj_dir.resolve()


@pytest.fixture(scope="module")
def localpkg_dep_2(module_tmpdir) -> Path:
    proj_dir = make_pyproject(
        module_tmpdir / "localpkg-dep-2",
        "localpkg-dep-2",
        tool={
            "uv": {
                "package": True,
            }
        }
    ).resolve()
    mk_hello_py("localpkg-dep-2", proj_dir / "localpkg_dep_2.py")
    return proj_dir.resolve()


@pytest.fixture(scope="module")
def localpkg_root(module_tmpdir, localpkg_dep_1, localpkg_dep_2) -> Path:
    return make_pyproject(
        module_tmpdir / "localpkg_root",
        "localpkg_root",
        dependencies=[
            "localpkg_dep_1",
            f"localpkg-dep-2 @ file://{localpkg_dep_2.resolve()}",
        ],
        tool={
            "uv": {
                "sources": {
                    "localpkg_dep_1": {"path": str(localpkg_dep_1.resolve())},
                }
            }
        }
    )




def test_cli_build_local_dependency(localpkg_root):
    dist_dir = localpkg_root / "dist"
    run_build_distr_bundle(localpkg_root, dist_dir)

    # check that wheels are built
    wheels = tuple(get_wheels(dist_dir))
    wheel_names = {w.name for w in wheels}
    assert wheel_names == {"localpkg-dep-1", "localpkg-dep-2", "localpkg-root"}
    assert (dist_dir / "localpkg_dep_1-0.1.0-py3-none-any.whl").is_file()
    assert (dist_dir / "localpkg_dep_2-0.1.0-py3-none-any.whl").is_file()
    assert (dist_dir / "localpkg_root-0.1.0-py3-none-any.whl").is_file()

    # check that index is created
    dist_index_dir = dist_dir/"index"
    assert dist_index_dir.is_dir(), "Index directory not found in dist dir"
    assert (dist_index_dir/"index.html").is_file(), "Index file not found in index directory"

    # check that pyproject is created
    dist_pyproject = dist_dir / "pyproject.toml"
    assert dist_pyproject.is_file(), "pyproject.toml not found in dist dir"
    assert PyProject(dist_pyproject).data == {
        'project': {
            'name': 'localpkg_root',
            'version': '0.1.0',
            'dependencies': [
                'localpkg_dep_1',
                'localpkg-dep-2',
            ]
        }
    }

    # syncing and running the bundle to check that local dependencies are installed from the local index
    run(["./sync.sh"], cwd=dist_dir)

    run_script = (
        "source ./.venv/bin/activate"
        " && python -m localpkg_dep_1"
        " && python -m localpkg_dep_2"
    )
    run(["bash", "-c", run_script], cwd=dist_dir)
