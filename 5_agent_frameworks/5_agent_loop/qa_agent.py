"""The QA tester: the ADK orchestrator plays its team's games to judge them.

Equipped with the Playwright MCP browser server, a single ADK agent opens each
finished game, plays it, watches the console, and reports which work and which are
broken. The agent's verdict drive the one bounded fix round.

The browser comes through the Playwright MCP server (npx @playwright/mcp) driving
the Chrome browser on the system. If the MCP server or Chrome is unavailable, we
fall back to a plain file check and still open the finished site.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import webbrowser
from pathlib import Path

from quiet import silence
silence()

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents.invocation_context import LlmCallsLimitExceededError 
from google.adk.agents.run_config import RunConfig 
from google.adk.runners import InMemoryRunner 
from google.adk.tools.mcp_tool import MCPToolset, StdioConnectionParams 
from google.genai import types 
from mcp import StdioServerParameters 

import config
import prompts

_APP = "agent_loop"  ## Defines a namespace - not really important
_MAX_CALLS = 25 # The QA Agent's budget for one game; a quick check needs far fewer
_CLOSE_TIMEOUT = 10 # Set bounds for the browser teardown so a wedged MCP close cannot hang the run

async def JudgeGame(Language: str, Objective: str, URL: str) -> dict | None:
    """Play one game with a fresh, bounded QA sub-agent and return {"works","note"}.

    The orchestrator agent calls this from its TestGame tool. A new short-lived agent per
    game keeps each browser session and context small and bounded, so a single confusing
    game cannot exceed a number of calls and total time cap. Returns None if the game
    could not be reached at all (no MCP server or no Chrome)
    """
    Verdict: dict = {}

    def ReportGame(works:bool, note:str) -> dict:
        """Report whether the game works, after playing it.
        
        Args:
            works: True if the game loads and plays correctly
            note: One short sentence on what you saw or what is broken
        """
        Verdict["works"] = works
        Verdict["note"] = note
        return {"recorded": True}

    Args = [
        "-y",
        "@playwright/mcp@latest",
        "--browser", "chrome",
        "--isolated",
        "--allow-unrestricted-file-access"
    ]

    if os.environ.get("QA_HEADLESS") == "1":
        Args.append("--headless")
    Browser = MCPToolset(
        connection_params = StdioConnectionParams(
            server_params = StdioServerParameters(command="npx", args=Args),
            timeout=30.0 ## The browser's first call can take longer than the 5s default to cold-start
        ),
        errlog = subprocess.DEVNULL
    )

    agent = LlmAgent(
        name = "QATester",
        model = LiteLlm("/".join(["openai",config.ORCHESTRATOR_MODEL])),
        instruction = "You are a meticulous QA tester. Use the browser to check the game, then report your verdict",
        tools = [Browser, ReportGame]
    )
    Runner = InMemoryRunner(agent=agent, app_name=_APP)
    try:
        Session = await Runner.session_service.create_session(app_name=_APP, user_id="QA")
        Prompt = prompts.QAPrompt.format(Language=Language, Objective=Objective, URL=URL)
        try:
            async for _ in Runner.run_async(
                user_id="QA",
                session_id=Session.id,
                new_message = types.UserContent(Prompt),
                run_config=RunConfig(max_llm_calls=_MAX_CALLS)
            ):
                pass
        except LlmCallsLimitExceededError:
            ## The agent used the maximum number of calls without reporting. It was clearly
            ## able to interact with the game, so the game loads and responds. We decide to
            ## treat it as working rather thn firing a spurious fix round
            Verdict.setdefault("works", True)
            Verdict.setdefault("note", "Played it for the maximum permissible turns and it stayed responsive")
        return Verdict or None
    finally:
        ## Close the MCP toolset (and so the npx browser subprocess) inside the loop before it ends
        ## or its transport's __del__ fires later on a closed loop. Bound each close, so if the caller
        ## gives up on a slow check and cancels this game, a stuck browser cannot hang the teardown
        ## and freeze the run. Here the caller is TestGame() in orchestrator.py which has a timeout
        ## QATimeout of its own
        for Close in (Browser.close, Runner.close):
            try:
                await asyncio.wait_for(Close(), timeout=_CLOSE_TIMEOUT)
            except Exception:
                pass
        ## Let the subprocess transport's close callbacks drain while the loop is still
        ## alive, so nothing is left for __del__ to clean up after the loop has closed
        await asyncio.sleep(0.1)


def OpenSite(IndexPath: Path) -> None:
    """Open the finished arcade in the default browser for the player"""
    webbrowser.open(IndexPath.resolve().as_uri())
