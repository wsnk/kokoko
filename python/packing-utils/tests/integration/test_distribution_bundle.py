from pathlib import Path
import pytest
from .common import run_build_distr_bundle, make_pyproject, run
from packing_utils.bundle import Config, build_bundle
import os


@pytest.fixture(scope="module")
def module_tmpdir(tmp_path_factory) -> Path:
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
        tool={"uv": {"package": True}}
    )
    mk_hello_py("localpkg-dep-1", proj_dir / "localpkg_dep_1.py")
    return proj_dir.resolve()


@pytest.fixture(scope="module")
def localpkg_dep_2(module_tmpdir) -> Path:
    proj_dir = make_pyproject(
        module_tmpdir / "localpkg-dep-2",
        "localpkg-dep-2",
        tool={"uv": {"package": True}}
    ).resolve()
    mk_hello_py("localpkg-dep-2", proj_dir / "localpkg_dep_2.py")
    return proj_dir.resolve()


@pytest.fixture
def localpkg_root(tmp_path, localpkg_dep_1, localpkg_dep_2) -> Path:
    proj_dir = make_pyproject(
        tmp_path / "localpkg_root",
        "localpkg_root",
        dependencies=[
            "localpkg_dep_1",
            f"localpkg-dep-2 @ file://{localpkg_dep_2.resolve()}",
        ],
        **{
            "build-system": {
                "requires": ["setuptools", "wheel"],
                "build-backend": "setuptools.build_meta"
            },
            "tool": {
                "uv": {
                    "sources": {
                        "localpkg_dep_1": {"path": str(localpkg_dep_1.resolve())},
                    }
                },
                "setuptools": {
                    "py-modules": ["localpkg_root"]
                }
            }
        }
    ).resolve()
    mk_hello_py("root", proj_dir / "localpkg_root.py")
    return proj_dir.resolve()


@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch: pytest.MonkeyPatch):
    with monkeypatch.context() as m:
        m.setenv("UV_CACHE_DIR", str(tmp_path / "uv_cache"))
        m.chdir(tmp_path)
        yield


def run_in_venv(venv_dir: Path, cmd: str, cwd=None, env=None):
    return run(
        ["bash", "-c", f"source {venv_dir.resolve()}/bin/activate && {cmd}"],
        cwd=cwd,
        env=env
    )


def test_cli_build_local_dependency(localpkg_root):
    bundle_dir = localpkg_root / "bundle"
    run_build_distr_bundle(localpkg_root, bundle_dir)

    wheels_dir = bundle_dir / "wheels"
    index_dir = bundle_dir / "index"

    # check that wheels are built
    assert (wheels_dir / "localpkg_dep_1-0.1.0-py3-none-any.whl").is_file()
    assert (wheels_dir / "localpkg_dep_2-0.1.0-py3-none-any.whl").is_file()
    assert (wheels_dir / "localpkg_root-0.1.0-py3-none-any.whl").is_file()

    # check that index is created
    assert index_dir.is_dir(), "Index directory not found in bundle dir"
    assert (index_dir/"index.html").is_file(), "Index file not found in index directory"

    # check that pyproject and uv.lock are created
    assert (bundle_dir/"pyproject.toml").is_file()
    assert (bundle_dir/"uv.lock").is_file()

    # syncing venv with the provided script
    run(["./sync.sh"], cwd=bundle_dir)

    # check, that all packages are installed and work
    CMDS = [
        ("python -m localpkg_dep_1", "Hello, localpkg-dep-1!"),
        ("python -m localpkg_dep_2", "Hello, localpkg-dep-2!"),
        ("python -m localpkg_root", "Hello, root!"),
    ]
    for cmd, expected_output in CMDS:
        output = run_in_venv(bundle_dir/".venv", cmd)
        assert output.strip() == expected_output.strip(), \
            f"Command '{cmd}' output did not match expected one"


def test_reinstallation_of_bundle(tmp_path: Path, localpkg_root):
    bundle_dir = tmp_path / "bundle"
    config = Config(
        pyproject_dir=localpkg_root,
        bundle_dir=bundle_dir
    )

    env = {**os.environ}
    env.pop("VIRTUAL_ENV", None)

    # 1. build and install first version of the bundle
    build_bundle(config)
    run(["./sync.sh"], cwd=bundle_dir, env=env)
    out = run_in_venv(bundle_dir/".venv", "python -m localpkg_root", env=env)
    assert out.strip() == "Hello, root!", "Initial installation failed"

    # 2. change the source code of the root package and rebuild the bundle
    mk_hello_py("root v2", localpkg_root / "localpkg_root.py")
    build_bundle(config)

    # 3. reinstall the bundle and check that the changes are reflected
    run(["./sync.sh"], cwd=bundle_dir, env=env)
    out = run_in_venv(bundle_dir/".venv", "python -m localpkg_root", env=env)
    assert out.strip() == "Hello, root v2!", "Reinstallation failed"
