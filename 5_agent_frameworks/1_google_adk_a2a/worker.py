"""Run the Day 1 worker against the board as a plain subprocess

Seeds one goal(e.g. "Read notes.txt, translate to Spanish, write spanish.txt"),
then lets the ADK agent loop work it; read the board, read the file through the
Filesystem MCP server, translate, write the Spanish back, and mark the task
done. This is exactly how a worker runs on Day 5, just with one goal

    uv run worker.py                # Seed a fresh goal and run the agent
    uv run worker.py --seed-only    # Just seed, then drive is from 'adk web'
"""



from __future__ import annotations

import sys
sys.stdout.reconfigure(encoding="utf-8") ## Because the computer's default encoding is cp1252

import argparse
import asyncio
from quiet import silence

silence()

import board
from google.adk.runners import InMemoryRunner
from task_worker.agent import Workspace, root_agent
from google.genai import types

Goal = """"Read notes.txt, translate its contents into natural Hindi, and write the Hindi to hindi.txt. 
Then send a push notification to the user"""

def seed() -> int:
    """Reset the board, put notes.txt in place, and add the one goal"""
    board.ResetBoard()
    Workspace.mkdir(exist_ok=True)
    ## Deletes the hindi.txt if it exists, but does not raise an error if the file does not exist
    (Workspace/"hindi.txt").unlink(missing_ok=True)
    return board.AddGoal(Goal)

async def run() -> None:
    # Runner = InMemoryRunner(agent=root_agent)
    # await Runner.run_debug("Please work the pending task on the board.", verbose=True)

    Runner = InMemoryRunner(agent=root_agent)
    Session = await Runner.session_service.create_session(app_name=Runner.app_name, user_id="Siddharth")

    async for Event in Runner.run_async(
        user_id="Siddharth",
        session_id = Session.id,
        new_message = types.UserContent("Please work the pending goal on the board")
    ):
        for Call in Event.get_function_calls():
            print (f"Tool: {Call.name}({Call.args})")
        if any(r.name in ("PlanSteps","CompleteTask") for r in Event.get_function_responses()):
            board.ShowBoard()
        if Event.is_final_response():
            print (Event.content.parts[0].text)

def main() -> None:
    ## seed-only lets us seed a goal here, then drive the agent from 'adk web'
    ## instead of this script, so the two entry points share the same setup
    Parser = argparse.ArgumentParser(description="Run the Day 1 ADK board worker")
    Parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Seed a fresh task without running the agent (for the adk web demo)"
    )
    Args = Parser.parse_args()

    GoalId = seed()
    print (f"Seeded goal {GoalId}: {Goal}")
    ## Please note that Args.seed_only is True if and only if the script is invoked with the --seed-only
    ## flag, i.e. it is invoked as `uv run worker.py --seed-only`. If the flag is not provided, then
    ## Args.seed_only will be False
    if Args.seed_only:
        ## Stop here: The goal is on the board, 'uv run adk web' will run the agent loop instead
        print ("Board is ready. Run `uv run adk web` and ask the worker to work the board")
        return

    board.ClaimTodo(GoalId)
    asyncio.run(run())

    print ("\nBoard after the run")
    board.ShowBoard()

    ## Print the translated file the agent should have written, if it is there
    Hindi = Workspace/"hindi.txt"
    if Hindi.exists():
        print("\nhindi.txt:\n" + Hindi.read_text(encoding="utf-8"))

if __name__ == "__main__":
    main()
