import pytest
from .common import make_git_repo
from packing_utils.infratools.git import GitRepository


@pytest.fixture(scope="module")
def git_repo_dir(tmp_path_factory) -> str:
    tmpdir = tmp_path_factory.mktemp("git-repo")
    return make_git_repo(tmpdir, "pyproj-in-git").resolve()


async def test_get_commit_hash(git_repo_dir: str):
    """Test building a package from a git repository source.
    """

    repo = GitRepository(git_repo_dir)
    commit_hash = await repo.get_commit_hash()
    assert len(commit_hash) == 40  # commit hash should be 40 characters long


async def test_clone_git_repository(git_repo_dir: str, tmp_path):
    """Test cloning a git repository from a URL with a commit hash.
    """

    url = f"file://{git_repo_dir}"
    dest_dir = tmp_path / "git-repo-clone"

    repo = await GitRepository.clone(url, dest_dir)

    assert repo.repo_dir.exists()
    await repo.get_commit_hash()  # no exception means the repository is valid