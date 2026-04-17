from pathlib import Path
import tomli_w
import subprocess
import logging


def create_file_tree(tree: dict[str, str], root: Path):
    for name, content in tree.items():
        path = root / name
        if isinstance(content, dict):
            path.mkdir(exist_ok=True)
            create_file_tree(content, path)
        else:
            path.write_text(content)



def make_pyproject(project_dir: Path, name: str, version=None, dependencies=None, file_tree=None, **kwargs) -> Path:
    project_dir.mkdir(exist_ok=True)

    pyproject_data = {
        "project": {
            "name": name,
            "version": version or "0.1.0",
            "requires-python": ">=3.10",
            "dependencies": dependencies or [],
        },
        **kwargs
    }

    (project_dir / "pyproject.toml").write_text(tomli_w.dumps(pyproject_data))

    if file_tree:
        create_file_tree(file_tree, project_dir)

    subprocess.check_call(["uv", "lock"], cwd=project_dir)
    return project_dir.resolve()


def make_git_repo(repo_dir: Path, pyproject_name: str, version=None, dependencies=None, file_tree=None) -> Path:
    repo_dir.mkdir(exist_ok=True)

    make_pyproject(repo_dir, pyproject_name, version, dependencies, file_tree)

    subprocess.check_call(["git", "init"], cwd=repo_dir)
    subprocess.check_call(["git", "add", "."], cwd=repo_dir)
    subprocess.check_call(["git", "commit", "-m", "Initial commit"], cwd=repo_dir)

    logging.info(f"Created git repository at '{repo_dir}' with project '{pyproject_name}'")

    return repo_dir.resolve()