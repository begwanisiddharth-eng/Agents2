"""Tools for the Sidekick: a mix of MCP servers, ready-made LangChain tools and our own."""

import asyncio
from contextlib import AsyncExitStack

import requests
import wikipedia
from dotenv import load_dotenv
from langchain_community.tools import GoogleSerperRun, WikipediaQueryRun
from langchain_community.utilities import GoogleSerperAPIWrapper, WikipediaAPIWrapper
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

load_dotenv(override=True)

# The `wikipedia` package sends a generic default User-Agent header on every
# HTTP request. Wikimedia's servers reject requests that look like they come
# from an unidentified bot/script, so we set a descriptive user agent that
# names the project and gives a contact URL, as Wikimedia's etiquette asks.
wikipedia.set_user_agent("Agentic AI (https://edwarddonner.com)")

Search = GoogleSerperRun(api_wrapper=GoogleSerperAPIWrapper())
WikipediaLookup = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())

@tool
def SendPushNotification(Text: str) -> str:
    "Send a short push notification to the user"
    Topic = "ross919gain370"
    URL = f"https://ntfy.sh/{Topic}"
    Response = requests.post(URL, data=Text.encode(encoding="utf-8"))
    # raise_for_status() turns a non-2xx HTTP response into a Python exception.
    # We deliberately do NOT catch that exception here: sidekick.py wraps every
    # tool call in a `TolerateToolErrors` middleware that converts any raised
    # exception into a message the agent can read and react to, so there is no
    # need for defensive try/except inside individual tools. If the response
    # is a HTPP 2xx response, then then it returns None and the execution carries
    # onto the next line
    Response.raise_for_status()
    return "Notification sent"

@tool
def RequestHumanHelp(Instructions: str) -> str:
    """
    Ask the user to do something in the browser window that you cannot do yourself,
    such as logging in to a site, passing a captcha, or approving two-factor
    authentication. Explain exactly what you need them to do. The run pauses until 
    they have done it.
    """
    # In sidekick.py, `HumanInTheLoopMiddleware` is configured to intercept any
    # call to this tool (by name) BEFORE it actually runs, and suspend the
    # agent's execution until a human approves the call from outside (see
    # Sidekick.resume() in sidekick.py). Once approved, the middleware lets the
    # call proceed, this function body executes, and the agent sees the return
    # value below as if the human had just finished what was asked.
    return "The user says it is done. Please proceed."

def MCPConnections(Sandbox: str) -> dict:
    """The MCP servers the Sidekick uses: a headed browser and a sandbox filesystem"""
    return {
        "playwright": {
            "transport": "stdio",
            "command": "npx",
            "args": ["@playwright/mcp@latest", "--isolated"]
        },
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", Sandbox]
        }
    }


class MCPSessions:
    """Holds persistent MCP sessions open so that the browser keeps its state between tool calls
    The stdio transport must be opened and closed from the same asyncio task, so one
    background task owns the sessions. It opens them, waits and unwinds them when stop() is
    called. Stopping shuts down the servers, and the browser will close.
    If we opened a fresh MCP connection for every single tool call, the Playwright browser
    would restart (and lose its page/state) each time. Instead we open the connections ONCE,
    keep the subprocesses and their async context managers alive for the whole Sidekick 
    session, and tear them down only when Sidekick itself is done (see the cleanup() function in
    sidekick.py). Because stdio transport pipes are tied to the aysncio process that opened them,
    there has to be one dedicated background asyncio task, which in this case is the _run() task.
    """

    def __init__(self, Connections:dict):
        self.connections = Connections
        self.tools = [] ## Filled in with Langchain Tool objects once servers start
        ## Two asyncio Event flags coordinate the setting up and shutting down of servers
        ## The asyncio.Event() command implements Event objects. An event manages a flag 
        # that can be set to true with the set() method and reset to false with the clear() method. 
        # The wait() method blocks until the flag is true. The flag is initially false.
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._task = None # The background asyncio task running _run()

    async def _run(self):
        # This coroutine runs as its own background asyncio Task (started in # start(), below)
        # and lives for as long as the MCP servers should stay connected.
        Client = MultiServerMCPClient(self.connections)
        # AsyncExitStack lets us open a *variable* number of async context managers 
        # (one `client.session(name)` per server) and be sure they are all cleanly closed together, 
        # in reverse order, when the `async with` block exits -- which happens once `self._stop.wait()`
        # returns below.
        async with AsyncExitStack() as Stack:
            for name in self.connections:
                Session = await Stack.enter_async_context(Client.session(name))
                self.tools += await load_mcp_tools(Session, server_name=name)
            self._ready.set()
            # Block here -- keeping the `async with` (and therefore the subprocess connections) open
            # -- until someone calls stop().
            await self._stop.wait()

    async def start(self) -> list:
        """Launch the MCP servers in the background and wait till their tools are ready"""
        self._task = asyncio.create_task(self._run())
        Ready = asyncio.create_task(self._ready.wait())
        # Wait for whichever happens first: the servers finish starting (`_ready` gets set), 
        # OR the background task ends early because it crashed while starting up 
        # (e.g. `npx` failed, a server errored out).
        await asyncio.wait([Ready, self._task], return_when=asyncio.FIRST_COMPLETED)
        Ready.cancel() ## The role of the Ready task is done
        if self._task.done():
            self._task.result() ## The servers failed to start; 
            ## The error is trasmitted via the result which is then sent to whichever function called start()
        return self.tools

    def stop(self):
        """Signal the background task to shut the MCP servers down"""
        self._stop.set()
        ## This causes the whole async with Stack to exit, shutting down all servers
        ## and ending _run()

    
async def GetAllTools(Sandbox: str):
    """Return the full tool list (our tools plus the MCP Server tools) and the session holder"""
    Sessions = MCPSessions(MCPConnections(Sandbox))
    MCPTools = await Sessions.start()
    OverallTools = [Search, SendPushNotification,WikipediaLookup,RequestHumanHelp]
    return OverallTools + MCPTools, Sessions ## We need to return Sessions class instance
    ## since stop() will be called on it
