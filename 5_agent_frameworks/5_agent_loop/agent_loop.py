"""The agent loop: a Google ADK orchestrator agent that runs the whole week 5 team.

The orchestrator is itself an agent. Given the workers built across the week and a
language to teach, it authors a shared look, hands each framework's worker a game
to build, launches them in parallel against one shared board, watches that board fill
in live, then plays each finished game in a real browser to check it and sends a
builder back to fix any that do not work. Open the printed index.html to play.

    uv run agent_loop.py                    # A Spanish arcade from every worker we have
    uv run agent_loop.py --language French  # Any language
    uv run agent_loop.py --skip-agno        # Leave a framework out
    uv run agent_loop.py --dry-run          # Show the plan without running the agent
    uv run agent_loop.py --no-open          # Build it but do not open the browser at the end
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(override=True) # The orchestrator and its sub-agents make ADK calls, so they need the API keys
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE") # Use the Gemini API, not Vertex

import config # Imported after load_dotenv so it sees any model ids set in .env

Here = Path(__file__).resolve().parent
Site = Here / "site"
BoardPath = Site/"board.sqlite"

os.environ["BOARD_PATH"] = str(BoardPath)
os.environ["WORKER_MODEL"] = config.WORKER_MODEL

import catalog
import orchestrator
import qa_agent

def ParseArgs() -> argparse.Namespace:
    Parser = argparse.ArgumentParser(description="Build a language game arcade with the week 5 team")
    Parser.add_argument("--language", default="Spanish", help="The language to learn")
    Parser.add_argument("--skip", nargs="*", default =[], help="Worker keys to leave out")
    ## The nargs="*" tells argparse that --skip can take zero or more values, all collected into a list.
    Parser.add_argument("--dry-run", action="store_true", help="Show the plan; do not run the agent")
    Parser.add_argument("--no-open", action="store_true", help="Do not open the finished site in browser")
    return Parser.parse_args()

def main() -> None:
    Args = ParseArgs()
    ## In the below call, skip can be (), ("agno",), ("agno", "mastra") etc.
    Workers = catalog.Discover(skip=tuple(Args.skip))
    if not Workers:
        raise SystemExit("No worker files found. Build at least one framework's worker first")
    
    print (f"Assembling a {Args.language} arcade with {len(Workers)} builders")
    for Worker in Workers:
        print (f"  {Worker['name']:<28} -> folder {Worker['slug']}/ (game invented at runtime)")
    if Args.dry_run:
        print ("\nDry run: Stopping before the agent runs")
        return

    print (f"\n{config.ORCHESTRATOR_MODEL} is leading the team. Watch the board fill in:\n")
    orchestrator.run(Args.language, Workers, Site, BoardPath)

    ## A final deterministic check, so a game the agent missed is still surfaced
    print ("\n Final check:")
    for Worker in Workers:
        Slug = Worker['slug']
        Built = orchestrator.IsBuilt(Site/Slug)
        print (f"  {Worker['name']:<28} {'ok' if Built else 'INCOMPLETE'} ({Slug}/)")

    Index = Site/"index.html"
    print ("\nThe team has finished. Open this to play:")
    print (f"  {Index.resolve().as_uri()}")
    if not Args.no_open:
        qa_agent.OpenSite(Index)

if __name__ == "__main__":
    main()