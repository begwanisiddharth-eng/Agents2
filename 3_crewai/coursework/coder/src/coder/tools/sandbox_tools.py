from crewai.tools import tool
from pathlib import Path
import subprocess

SANDBOX_DIR = Path(__file__).parents[3]/"sandbox" ## Goes 4 levels up the base coder directory
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

@tool("List sandbox files")
def ListSandboxFiles() -> str:
    """ List the filenames currrently in the sandbox directory
    Returns: A newline-seprate list of filenames, or a message if the directory is empty
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
        return path.read_text()

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
    path.write_text(Content)
    return f"Wrote {len(Content)} characters to the file {FileName}"

@tool("Run Sandbox Python File")
def RunSandboxPython(FileName: str) -> str:
    """
    Execute a Python file from the sandbox directory inside an ephemeral Docker
    container, with the sandbox mounted as a working directory, and return whatever the
    script printed to stdout.
    Args:
        FileName: The Python file to be run in the Docker container (e.g. 'solution.py')
    Returns:
        The text printed to stdout by the executed script  
    """
    Result = subprocess.run(
        [
            "docker", "run", "--rm",
            "-v", f"{SANDBOX_DIR}:/workspace",
            "-w", "/workspace",
            "python:3.13-slim",
            "python", FileName,
        ],
        capture_output = True,
        text = True,
        timeout = 60
    )
    return Result.stdout

SandboxTools = [ListSandboxFiles,ReadSandboxFile,WriteSandboxFile,RunSandboxPython]




