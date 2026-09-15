"""Run the Strands worker against the board as a plain subprocess

Run bare, it seeds and works its own Day 2 goal(Read notes.txt, translate to Hindi,
write hindi.txt): Plan the steps on the board, read the file through the Filesystem 
MCP server, translate to Hindi, write the Hindi translation back, and tick each
step off before closing the goal.

Given a task id and a shared board path, the same worker joins the Day 5 agent loop
instead. It points its board and file tools at the shared board and site, claims the
one task it has been given, builds what the task asks, and exits, leaving the rest
of the board alone.

    uv run strands_worker.py                            # Standalone Day 2 demo
    uv run strands_worker.py <TaskId> <boardPath>       # Day 5: Work one task on a shared board
"""

from __future__ import annotations

import sys
sys.stdout.reconfigure(encoding="utf-8") ## Because the computer's default encoding is cp1252

import asyncio
import os
import subprocess
from pathlib import Path

## Day 5 mode is "<TaskId> <boardPath>". Read it before importing board, because
## the board picks its file from BOARD_PATH at import. On Day 5, there will be 3 arguments
## in sys.argv, the first of which is the script name. On Day 2, there is just one argument,
## the script name
TaskId = int(sys.argv[1]) if len(sys.argv) > 2 else None
if TaskId is not None:
    os.environ.setdefault("BOARD_PATH", sys.argv[2])

from dotenv import load_dotenv
from strands import Agent, tool
from strands.models.openai import OpenAIModel
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters

import board

load_dotenv(override=True)

MODEL = os.environ.get("WORKER_MODEL", "gpt-5.4-nano")
Workspace = Path(__file__).resolve().parent/"workspace"
Goal = "Read notes.txt, translate its contents into Hindi, and write the Hindi translation to hindi.txt"
## Where the file tools may write: this worker's own workspace when standalone, or
## the shared site (the board file's folder) when working on Day 5 task
WorkDir = Workspace if TaskId is None else Path(sys.argv[2]).resolve().parent

Model = OpenAIModel(client_args={'api_key': os.environ["OPENAI_API_KEY"]}, model_id=MODEL)

@tool
def ShowTodos() -> list[dict]:
    """Lists every Todo on the board: A goal has parent_id None, while a step has parent_id set to its goal's id"""
    return board.ListTodos()

@tool
def PlanSteps(GoalId: int, Steps: list[str]) -> dict:
    """Break down a goal into an ordered checklist of steps on the board
    Args:
        GoalId: The id of the goal to break down
        Steps: The list of steps to be taken in order, with each step being described briefly
    """
    return {"goal_id":GoalId, "step_ids":[board.AddStep(GoalId,Step) for Step in Steps]}

@tool
def CompleteTask(TaskId: int, Result: str) -> dict:
    """Mark a Todo (a step or a goal) as done and record the result as a short summary
    
    Args:
        TaskId: The id of the Todo(goal or step) to mark as done
        Result: A short summary of the result of executing the Todo
    """
    board.CompleteTodo(TaskId,Result)
    return {"task_id": TaskId, "status": "done"}

Filesystem = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(
            command="npx",
            args = ["-y","@modelcontextprotocol/server-filesystem", str(WorkDir)],
            cwd = str(WorkDir) # Start the server in the Workspace as relative file names resolve there
        ),
        errlog = subprocess.DEVNULL
    ),
    startup_timeout=60
)

INSTRUCTIONS = """
               You are a meticulous worker who has access to a shared Todo board, and a list of tools
               to access the board, as well as a set of tools to read and write files in a specific directory.

               First, given the goal, plan a list of steps that need to be taken to accomplish the goal. The steps
               must be added to the board under the goal. Then start working on the steps in order. Once you
               have completed a step and ONLY when a step is complete, mark it as done on the board. Stop only when
               you have completed all the steps and marked them as done, and then marked the goal as done.

               To accomplish your work, you have access to a single directory where you can read and write files.
               """

def seed() -> int:
    """Reset the board, and then add the one goal"""
    board.ResetBoard()
    Workspace.mkdir(exist_ok=True)
    (Workspace/"hindi.txt").unlink(missing_ok=True)
    GoalId = board.AddGoal(Goal)
    board.ClaimTodo(GoalId)
    return GoalId

async def main() -> None:
    if TaskId is None: ## Standalone Day 2 demo
        GoalId = seed()
        print (f"Seeded goal {GoalId}: {Goal}\n")
        Message = "Please work on the pending goal on the board"
    else:
        board.ClaimTodo(TaskId) ## Pick up this one goal on the shared board
        Message = f"""You have claim task #{TaskId} on the shared board. Work only on that task and its steps
                   When the work has been completed and checked, mark task #{TaskId} done with CompleteTask tool,
                   and then stop"""
    
    Worker = Agent(
        model=Model,
        system_prompt = INSTRUCTIONS,
        tools = [ShowTodos, PlanSteps, CompleteTask, Filesystem]
    )

    await Worker.invoke_async(Message)

    if TaskId is None: ## Standalone mode, show the result. In shared mode, the orchestrator owns the console
        print ("\n Board after the run:")
        board.ShowBoard()
        Hindi = Workspace / "hindi.txt"
        if Hindi.exists():
            print ("\nhindi.txt :\n"+ Hindi.read_text(encoding="utf-8"))


if __name__ == "__main__":
    asyncio.run(main())
