import subprocess
from pathlib import Path
from .proc import run_async
import os
from .log import dbg, inf, err
from dataclasses import dataclass, field


# def parse_url(cls, url, dest_dir: Path):
#     """ Checks out a git repository from the given URL and returns the path to the directory.

#     URL is like:
#     ssh://git@github.com/org-name/repo-name.git[?subdirectory=path/to/a/dir]#commithash

#     """

#     from urllib.parse import urlparse, parse_qs

#     # Parse the URL
#     parsed = urlparse(url)

#     # Extract the git URL (without fragment and query)
#     git_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
#     commit_hash = parsed.fragment
#     dbg("git: URL='%s', commit='%s'", git_url, commit_hash)

#     # Extract subdirectory if present
#     subdirectory = None
#     if parsed.query:
#         params = parse_qs(parsed.query)
#         if 'subdirectory' in params:
#             subdirectory = params['subdirectory'][0]


class Git:
    @classmethod
    def is_repository(cls, path: Path) -> bool:
        return (path / ".git").is_dir()

    @classmethod
    def get_commit_hash(cls, repo_dir: Path) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            err("Failed to get commit hash: %s", result.stderr)
            raise RuntimeError(f"git rev-parse failed with exit code {result.returncode}")
        return result.stdout.strip()

    @classmethod
    def has_commit(cls, repo_dir: Path, commit_hash: str) -> bool:
        result = subprocess.run(
            ["git", "cat-file", "-t", commit_hash], cwd=repo_dir, capture_output=True, text=True
        )
        return result.returncode == 0 and result.stdout.strip() == "commit"

    @classmethod
    def fetch(cls, repo_dir: Path):
        dbg(f"Fetching latest changes for repository at '{repo_dir}'")
        result = subprocess.run(["git", "fetch"], cwd=repo_dir, capture_output=True, text=True)
        if result.returncode != 0:
            err("Failed to fetch repository: %s", result.stderr)
            raise RuntimeError(f"git fetch failed with exit code {result.returncode}")
        dbg("Repository fetched successfully. Output:\n%s", result.stdout)

    @classmethod
    def clone(cls, url: str, dest_dir: Path):
        dbg(f"Cloning repository: {url} into '{dest_dir}'")
        result = subprocess.run(
            ["git", "clone", url, str(dest_dir)], capture_output=True, text=True
        )
        if result.returncode != 0:
            err(f"Failed to clone repository: {result.stderr}")
            raise RuntimeError(f"git clone failed with exit code {result.returncode}")

    @classmethod
    def checkout(cls, repo_dir: Path, commit_hash: str):
        dbg(f"Checking out commit '{commit_hash}' in repository '{repo_dir}'")
        result = subprocess.run(
            ["git", "checkout", commit_hash], cwd=repo_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            err(f"Failed to checkout commit: {result.stderr}")
            raise RuntimeError(f"git checkout failed with exit code {result.returncode}")

    @classmethod
    def ensure_repo(cls, url, dest_dir: Path):
        """ Checks out a git repository from the given URL and returns the path to the directory.

        URL is like:
        ssh://git@github.com/org-name/repo-name.git[?subdirectory=path/to/a/dir]#commithash

        """

        from urllib.parse import urlparse, parse_qs

        # Parse the URL
        parsed = urlparse(url)

        # Extract the git URL (without fragment and query)
        git_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        commit_hash = parsed.fragment
        dbg("git: URL='%s', commit='%s'", git_url, commit_hash)

        # Extract subdirectory if present
        subdirectory = None
        if parsed.query:
            params = parse_qs(parsed.query)
            if 'subdirectory' in params:
                subdirectory = params['subdirectory'][0]

        # Create destination directory if not provided
        dest_dir.mkdir(parents=True, exist_ok=True)

        if cls.is_repository(dest_dir):
            dbg("Repository already exists at '%s', skipping clone.", dest_dir)
        else:
            cls.clone(git_url, dest_dir)

        # Checkout specific commit if provided
        if commit_hash:
            if not cls.has_commit(dest_dir, commit_hash):
                dbg("Commit hash '%s' not found in repository '%s'", commit_hash, git_url)
                cls.fetch(dest_dir)  # fetch latest changes and check again
                if not cls.has_commit(dest_dir, commit_hash):
                    raise ValueError(
                        f"Commit hash '{commit_hash}' not found in repository '{git_url}'"
                    )
            cls.checkout(dest_dir, commit_hash)

        # Return the path (or subdirectory path if specified)
        if subdirectory:
            return dest_dir/subdirectory

        return dest_dir


def parse_remotes(output: str):
    # origin  https://github.com/FFmpeg/FFmpeg.git (fetch) [blob:none]
    # origin  https://github.com/FFmpeg/FFmpeg.git (push)
    for ln in output.splitlines():
        if not ln:
            continue
        name, url, mode = ln.split(maxsplit=2)
        yield (name, url, mode)



class GitCli:
    def __init__(self, repo_dir=None, git_bin=None):
        self.repo_dir = repo_dir
        self.git_bin = git_bin or "git"

    async def run(self, args, **kwargs):
        kwargs.setdefault("cwd", self.repo_dir)
        return await run_async(
            [self.git_bin, *(str(it) for it in args)],
            **kwargs
        )


RemoteUrlT = tuple[str, str]  # URL, mode


@dataclass(kw_only=True)
class RemoteRepository:
    name: str
    urls: list[RemoteUrlT] = field(default_factory=list)

    def has_url(self, url: str) -> bool:
        # FIXME
        for it in self.urls:
            if it[0] == url:
                return True
        return False


class Remotes:
    def __init__(self, git_repo: 'GitRepository'):
        self.git_repo = git_repo

    async def get_remotes(self) -> dict[str, RemoteRepository]:
        proc = await self.git_repo.run(["remote", "-v"], stdout=subprocess.PIPE, text=True)
        
        ret: dict[str, RemoteRepository] = {}
        for (name, url, mode) in parse_remotes(proc.stdout):
            rr = ret.setdefault(name, RemoteRepository(name=name))
            rr.urls.append((url, mode))

        return ret
    
    async def set_remote(self, url, name="origin"):
        """
        Ensure the named remote is configured with the given URL.
        """

        remotes = await self.get_remotes()
        r = remotes.get(name)
        if r is not None:
            if r.has_url(url):
                dbg("Remote already has the given URL: name='%s', URL='%s'", name, url)
                return

            dbg("Removing existing remote: name='%s', %s", name, r)
            await self.git_repo.run(["remote", "remove", name])

        dbg("Adding new remote: name='%s', URL='%s'...", name, url)
        await self.git_repo.run(["remote", "add", name, url])
        inf("New '%s' remote added", name)


class GitRepository:
    @classmethod
    async def clone(cls, url: str, dest_dir: Path, *, git_bin=None):
        if git_bin is None:
            git_bin = "git"

        dbg(f"Cloning repository: {url} into '{dest_dir}'")
        await run_async([git_bin, "clone", url, str(dest_dir)])
        return cls(dest_dir)

    def __init__(self, repo_dir: Path, *, git_bin=None):
        self.repo_dir = repo_dir
        self.git_bin = git_bin or "git"

    async def run(self, args, **kwargs):
        return await run_async(
            [self.git_bin, *(str(it) for it in args)],
            cwd=self.repo_dir,
            **kwargs
        )

    @property
    def remotes(self) -> Remotes:
        return Remotes(self)

    async def init(self):
        await self.run(["init", "."])
    
    async def checkout(self, branch):
        await self.run(["checkout", branch])

    async def fetch_light(self, refspec, remote="origin"):
        """
        Fetch given <refspec> from a remote repository without blobs.
        """
        await self.run([
            "fetch",
            "--depth", "1",
            "--filter=blob:none",
            remote,
            refspec
        ])

    async def get_commit_hash(self) -> str:
        result = await run_async(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            text=True
        )
        return result.stdout.strip()
