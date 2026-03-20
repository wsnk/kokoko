from dataclasses import dataclass
from pathlib import Path
import logging
import subprocess
from unittest import result
from urllib.parse import urlparse, parse_qs
import tempfile
import shutil
import json

_log = logging.getLogger(__name__)


def dbg(*args, **kwargs):
    _log.debug(*args, **kwargs, stacklevel=2)


def inf(*args, **kwargs):
    _log.info(*args, **kwargs, stacklevel=2)


def err(*args, **kwargs):
    _log.error(*args, **kwargs, stacklevel=2)


@dataclass
class Wheel:
    path: Path
    name: str

    @classmethod
    def from_path(cls, path: Path):
        pkg, _ = path.name.split("-", 1)
        return cls(path=path.resolve(), name=pkg)


@dataclass
class LockedPackage:
    """ Data of a locked package from `uv.lock` file
    """
    name: str
    version: str
    source: dict



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




class Uv:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
    
    def version(self):
        cmd = ["uv", "version", "--frozen", "--output-format", "json"]
        out = subprocess.run(cmd, cwd=self.project_dir, check=True, capture_output=True, text=True)
        data = json.loads(out.stdout)
        dbg("Project version info: %s", data)
        return data
    
    def build(self, outdir: Path = None, args: list[str] = None):
        if args is None:
            args = []
        if outdir is not None:
            outdir.mkdir(parents=True, exist_ok=True)
            args += ["--out-dir", str(outdir.resolve())]

        dbg("Building project using 'uv build' command, args: %s", args)
        result = subprocess.run(["uv", "build", *args], cwd=self.project_dir)
        if result.returncode != 0:
            _log.error("Failed to build project: %s", result.stderr)
            raise RuntimeError(f"uv build failed with exit code {result.returncode}")
        dbg("Project built successfully. Output:\n%s", result.stdout)

    def lock(self, args: list[str] = None):
        if args is None:
            args = []
        dbg("Generating lock file using 'uv lock' command, args: %s", args)
        result = subprocess.run(["uv", "lock", *args], cwd=self.project_dir)
        if result.returncode != 0:
            _log.error("Failed to generate lock file: %s", result.stderr)
            raise RuntimeError(f"uv lock failed with exit code {result.returncode}")
        dbg("Lock file generated successfully. Output:\n%s", result.stdout)


class Git:
    @classmethod
    def is_repository(cls, path: Path) -> bool:
        return (path / ".git").is_dir()
    
    @classmethod
    def get_commit_hash(cls, repo_dir: Path) -> str:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True)
        if result.returncode != 0:
            _log.error("Failed to get commit hash: %s", result.stderr)
            raise RuntimeError(f"git rev-parse failed with exit code {result.returncode}")
        return result.stdout.strip()

    @classmethod
    def has_commit(cls, repo_dir: Path, commit_hash: str) -> bool:
        result = subprocess.run(["git", "cat-file", "-t", commit_hash], cwd=repo_dir, capture_output=True, text=True)
        return result.returncode == 0 and result.stdout.strip() == "commit"

    @classmethod
    def fetch(cls, repo_dir: Path):
        dbg(f"Fetching latest changes for repository at '{repo_dir}'")
        result = subprocess.run(["git", "fetch"], cwd=repo_dir, capture_output=True, text=True)
        if result.returncode != 0:
            _log.error("Failed to fetch repository: %s", result.stderr)
            raise RuntimeError(f"git fetch failed with exit code {result.returncode}")
        dbg("Repository fetched successfully. Output:\n%s", result.stdout)

    @classmethod
    def clone(cls, url: str, dest_dir: Path):
        dbg(f"Cloning repository: {url} into '{dest_dir}'")
        result = subprocess.run(["git", "clone", url, str(dest_dir)], capture_output=True, text=True)
        if result.returncode != 0:
            err(f"Failed to clone repository: {result.stderr}")
            raise RuntimeError(f"git clone failed with exit code {result.returncode}")

    @classmethod
    def checkout(cls, repo_dir: Path, commit_hash: str):
        dbg(f"Checking out commit '{commit_hash}' in repository '{repo_dir}'")
        result = subprocess.run(["git", "checkout", commit_hash], cwd=repo_dir, capture_output=True, text=True)
        if result.returncode != 0:
            err(f"Failed to checkout commit: {result.stderr}")
            raise RuntimeError(f"git checkout failed with exit code {result.returncode}")

    @classmethod
    def ensure_repo(cls, url, dest_dir: Path):
        """Checks out a git repository from the given URL and returns the path to the checked-out directory.
        URL is like: 'ssh://git@github.com/org-name/repo-name.git[?subdirectory=path/to/a/dir]#commithash'
        """
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
                    raise ValueError(f"Commit hash '{commit_hash}' not found in repository '{git_url}'")
            cls.checkout(dest_dir, commit_hash)

        # Return the path (or subdirectory path if specified)
        if subdirectory:
            return dest_dir/subdirectory

        return dest_dir