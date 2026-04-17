import subprocess
from contextlib import contextmanager
from .log import dbg, inf, err


class ToFile:
    def __init__(self, file_path, *, mode='w'):
        self.file_path = file_path
        self.mode = mode

    @contextmanager
    def open(self):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, self.mode) as f:
            yield f


@contextmanager
def _prepare_output(out):
    if isinstance(out, ToFile):
        with out.open() as f:
            yield f
    else:
        yield out


@contextmanager
def redirect_output(stdout=None, stderr=None):
    """Context manager to redirect stdout and stderr to files or capture them in memory.
    Usage:
        with redirect_output(stdout=ToFile("output.log"), stderr=ToFile("error.log")):
            # code that produces output
    """

    with _prepare_output(stdout) as out_stdout, _prepare_output(stderr) as out_stderr:
        yield out_stdout, out_stderr



def run(cmd, *, stdout=None, stderr=None, **kwargs):
    dbg("Running command: %s", cmd)
    with (
        _prepare_output(stdout) as stdout,
        _prepare_output(stderr) as stderr
    ):
        result = subprocess.run(
            cmd,
            **kwargs,
            stdout=stdout,
            stderr=stderr,
        )
    
    if result.returncode != 0:
        err("Command failed: %s", result.stderr)
        raise RuntimeError(f"Command failed with exit code {result.returncode}")

    dbg("Command output:\n%s", result.stdout)
    return result

async def run_async(cmd, *, stdout=None, stderr=None, text=False, **kwargs) -> subprocess.CompletedProcess:
    import asyncio

    dbg("Running subprocess command: %s", cmd)

    with (
        _prepare_output(stdout) as stdout,
        _prepare_output(stderr) as stderr
    ):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            **kwargs,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
        )
        dbg("Started subprocess: PID=%d", proc.pid)
        stdout_data, stderr_data = await proc.communicate()

        dbg("Subprocess completed: PID=%d, code=%d", proc.pid, proc.returncode)

        if text:
            stdout_data = stdout_data.decode() if stdout_data else ""
            stderr_data = stderr_data.decode() if stderr_data else ""

        if proc.returncode != 0:
            err("Subprocess failed: PID=%s, stderr=%s", proc.pid, stderr_data)
            raise RuntimeError(f"Subprocess failed with exit code {proc.returncode}")

        inf("Subprocess sucessfully completed: PID=%d, stdout=%s", proc.pid, stdout_data)

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode,
            stdout=stdout_data,
            stderr=stderr_data
        )
