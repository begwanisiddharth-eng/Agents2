"""The Day 1 worker agent: one LlmAgent that works the SQLite board.

The same agent runs three ways: visually with `adk web`, in the terminal with
`adk run`, or driven from worker.py as a plain subprocess. The board tools give
it its task, the filesystem MCP server gives it files, and the agent loop does
the rest. Days 2 to 4 rebuild this exact contract in a different framework.
"""

from __future__ import annotations

import os
import requests
import subprocess
from pathlib import Path
from dotenv import load_dotenv

from quiet import silence
silence()

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI","FALSE")
load_dotenv(override=True)

import board

Model = LiteLlm("openai/gpt-5.4-nano")
Workspace = Path(__file__).resolve().parent/"workspace"
Workspace.mkdir(exist_ok=True)

## DEFINE TOOLs
## Set of tools including MCP servers

def ShowTodos() -> list[dict]:
    """List every Todo on the board. A goal has parent_id None.
    A step has parent_id set to its goal's id"""
    return board.ListTodos()

def PlanSteps(GoalId: int, Steps: list[str]) -> dict:
    """Break a goal into an ordered checklist of steps on the board. Pass the goal's id
    and a short list of step descriptions"""
    return {"goal_id":GoalId, "step_ids": [board.AddStep(GoalId,Step) for Step in Steps]}

def CompleteTask(TaskId: int, Result: str) -> dict:
    """Mark a Todo (goal or a step) as done and record a short result summary"""
    board.CompleteTodo(TaskId,Result)
    return {"task_id": TaskId, "status":"done"}

def SendPushNotification(Message: str) -> str:
    """Send a short push notification to report that a job is done or to report a result"""
    Topic = "ross919gain370"
    URL = f"https://ntfy.sh/{Topic}"
    Response = requests.post(URL, data=Message.encode(encoding="utf-8"))
    return f"Push notification sent with API return code {Response.status_code}"

Filesystem = McpToolset(
    connection_params=StdioConnectionParams(
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", str(Workspace)],
            cwd = str(Workspace) ## Start the server in the workspace so relative file names resolve there
        ),
        timeout=60
    ),
    errlog=subprocess.DEVNULL
)

## END DEFINTION OF TOOLS
INSTRUCTIONS = """
               You are a careful worker with a shared Todo board and a set of file tools.
               Take the pending goal and see it through. Begin by laying out a short plan.
               This plan comprises of the set of concrete steps the work breaks down into.
               Then put these steps into the board under the goal, and start working on these
               steps. Update the status of the steps using the tools you have. You also have a 
               tool to read and write files to a location. Once you have finished all the tasks,
               close the associated goal on the board and send a push notification to the user
               stating in 2-3 sentences what was accomplished.
               """

## The agent has to be named root_agent
## ADK's CLI (adk web / adk run) discovers an agent by importing task_worker.agent and checking 
## hasattr(module, "root_agent")

root_agent = LlmAgent(
    model=Model, 
    name="TaskWorker",
    description="Works one goal from the SQLite board using its files",
    instruction=INSTRUCTIONS,
    tools=[ShowTodos,CompleteTask,PlanSteps,Filesystem,SendPushNotification]
)
