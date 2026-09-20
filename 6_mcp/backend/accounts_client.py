import sys
import mcp
from pathlib import Path
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters

if sys.platform.startswith("win"):
    ## Under Windows, IPykernel's sys.stderr is not backed by a real file
    ## descriptor. Redirect errlog to DEVNULL to avoid io.UnsupportedOperation: fileno
    ## when stdio_client creates its subprocess
    try:
        from IPython import get_ipython
        if get_ipython().__class__.__name__ == "ZMQInteractiveShell":
            import functools
            import subprocess

            ## We are running inside Jupyter under Windows so redirect errlog
            stdio_client = functools.partial(stdio_client, errlog=subprocess.DEVNULL)
    except (ImportError, ModuleNotFoundError, AttributeError):
        pass

Params = StdioServerParameters(
    command = "uv",
    args = ["run", "-m", "backend.accounts_server"],
    cwd=str(Path(__file__).resolve().parent.parent),
    env = None
)

async def ReadAccountResource(Name):
    ## stdio_client(Params) starts the subprocess described by Params, which is uv run -m backend.accounts_server 
    ## in the 6_mcp folder. It connects to that process's stdin and stdout. Streams is a pair of channels: one to 
    ## read messages coming from the server and one to write messages to it. They carry raw MCP messages, which are JSON.
    async with stdio_client(Params) as Streams:
        ## *Streams unpacks the pair into two separate arguments, so this is ClientSession(read_stream, write_stream).
        ## ClientSession is the MCP protocol layer on top of the raw pipes. It formats requests, matches each response 
        ## to its request, and runs a background task that listens for incoming messages.
        async with mcp.ClientSession(*Streams) as Session:
            ## This is the MCP handshake, and nothing else works before it. The client sends its protocol version and 
            ## capabilities, the server replies with its own, and the client confirms. Skipping it makes the server reject 
            ## later requests.
            await Session.initialize()
            Result = await Session.read_resource(f"accounts://accounts_server/{Name}")
            ## Result is a ReadResourceResult object. Its contents attribute is a list, because a resource can return 
            ## several pieces. The return sits inside both async with blocks. Python runs the exits first, in reverse order. 
            ## It closes the session, then the pipes, then stops the subprocess, and only then hands the string back to the caller. 
            return Result.contents[0].text

async def ReadStrategyResource(Name):
    async with stdio_client(Params) as Streams:
        async with mcp.ClientSession(*Streams) as Session:
            await Session.initialize()
            Result = await Session.read_resource(f"accounts://strategy/{Name}")
            return Result.contents[0].text

