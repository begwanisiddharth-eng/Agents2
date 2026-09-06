from crewai.tools import tool
from pathlib import Path
import shutil
import subprocess


SANDBOX_DIR = Path(__file__).parents[3]/"sandbox" ## Goes 4 levels up the base coder directory
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

def ResetSandbox() -> None:
    """ Wipe out the existing sandbox and re-initialize it as a fresh uv project with gradio """
    if SANDBOX_DIR.exists():
        shutil.rmtree(SANDBOX_DIR)
    SANDBOX_DIR.mkdir(parents=True)

    subprocess.run(["uv", "init", "--bare", "--no-workspace", "--python","3.13"], cwd=SANDBOX_DIR, check=True)
    subprocess.run(["uv","add", "gradio"], cwd=SANDBOX_DIR, check=True)

@tool("List sandbox files")
def ListSandboxFiles() -> str:
    """ List the filenames currrently in the sandbox directory
    Returns: A newline-separated list of filenames, or a message if the directory is empty
    """
    Names = sorted(File.name for File in SANDBOX_DIR.iterdir())
    return "\n".join(Names) if Names else "The sandbox is empty"

@tool("Read sandbox file")
def ReadSandboxFile(FileName: str) -> str:
    """ Read and return the text contents of a file in the sandbox directory
    Args:
        FileName: The name of the file to read
    Returns:
        The contents of the file in text format as a string. If the file is
        empty, return an appropriate message
    """
    path = SANDBOX_DIR / FileName
    if not path.is_file():
        return f"No such file in the sandbox: {FileName}"
    else:
        return path.read_text(encoding="utf-8")

@tool("Write sandbox file")
def WriteSandboxFile(FileName: str, Content: str) -> str:
    """Write a file to the sandbox directory
    Args:
        FileName: Name of the file to be written (e.g. 'solution.py')
        Content: Text contents of the file to be written
    Returns:
        A configuration message
    """
    path = SANDBOX_DIR / FileName ## Uses an overloaded operator for Path class
    path.write_text(Content, encoding="utf-8")
    return f"Wrote {len(Content)} characters to the file {FileName}"

@tool("Run Sandbox Python File")
def RunSandboxPython(FileName: str) -> str:
    """
    Execute a Python file from the sandbox directory inside an ephemeral Docker
    container, with the sandbox mounted as a working directory, using `uv run` to run the code
    in the uv project.

    Returns the exit code, stdout and stderr, clearly labelled. Note that Python's unittest module
    prints test results - including failures and tracebacks - to stderr by default and not stdout. 
    Hence stderr is just as important as stdout for understanding what happened.
    Args:
        FileName: The Python file to be run in the Docker container (e.g. 'solution.py')
    Returns:
        A labelled block containing the exit code, stdout and stderr  
    """
    
    try:
        Result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{SANDBOX_DIR}:/workspace",
                "-w", "/workspace",
                "ghcr.io/astral-sh/uv:python3.13-bookworm-slim",
                "uv", "run", FileName
            ],
            capture_output = True,
            text = True,
            timeout = 400
        )
        return (
            f"Exit code: {Result.returncode}\n\n"
            f"--- stdout so far ---\n{Result.stdout or '(Empty)'}\n\n"
            f"--- stderr so far ---\n{Result.stderr or '(Empty)'}"
        )
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        return (
            "The script timed out after 400 seconds.\n\n"
            f"--- stdout so far ---\n{stdout or '(Empty)'}\n\n"
            f"--- stderr so far ---\n{stderr or '(Empty)'}"
        )


SandboxTools = [ListSandboxFiles,ReadSandboxFile,WriteSandboxFile,RunSandboxPython]

def _never_cache(*_args, **_kwargs) -> bool:
    return False

## Sandbox state changes between runs (files are created, changed, run) so cahing tool results 
## would feed the agents with stale data. We need to opt out of CrewAI's default tool caching
for _t in SandboxTools:
    _t.cache_function = _never_cache





