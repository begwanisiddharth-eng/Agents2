"""The orchestrator: A Google ADK agent that runs the whole Week 5 team as a loop.

The orchestrator is not a Python loop that calls the workers. It is itself an ADK
agent, given a goal (build a language arcade with this team) and tools for the 
mechanical parts; author the shared look, kick off each framework's builder, wait
for the team, play each finished game in a real browser to check it, and send a 
builder back once to fix a game that does not work. The agent owns the decisions;
the tools own the mechanics.

The whole run lives on one event loop. The launch and wait tools spawn workers
with plain subprocess.Popen(no asyncio transports to outlive the loop), and the
browser QA closes its MCP toolset in-loop, so that there is no "event loop is closed"
teardown.
"""
from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from quiet import silence
silence()

from google.adk.agents import LlmAgent 
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig 
from google.adk.runners import InMemoryRunner 
from google.genai import types 
from rich.live import Live

import board
import catalog
import config
import css_agent
import live_board
import prompts
import qa_agent

_APP = "agent_loop"
_MAX_TURNS = 80 ## Upper bound on the outer loop
GameFiles = {"game.html", "game.css", "game.js"}
WorkerTimeout = int(os.environ.get("WORKER_TIMEOUT_S", "300")) ## A worker hung past this is stopped so the run does not stall
QATimeout = int(os.environ.get("QA_TIMEOUT_S", "150")) ## If the browser QA runs past this, it is given up so the run does not stall
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

def _read_title(GameHTML: Path) -> str:
    """ The title the builder gave its game, read from game.html (empty if not found) """
    try:
        Match = _TITLE_RE.search(GameHTML.read_text(encoding="utf-8"))
    except OSError:
        return ""
    return Match.group(1).strip() if Match else ""


def IsBuilt(Folder:Path) -> bool:
    """True if all three game files exist in the folder and are non-empty"""
    return all((Folder/file).exists() and (Folder/file).stat().st_size for file in GameFiles)


def _launch(GoalId: int, Worker: dict, BoardPath: Path) -> subprocess.Popen:
    """Start one worker as a subprocess against the shared board

    stdout and stderr go to DEVNULL: a worker's framework banner would otherwise
    tear the live board, and the worker communicates only through the board. On POSIX,
    start_new_session puts the worker and its uv/npx/MCP tree in their own session so
    a timeout can stop the whole tree at once; on Windows, the same job is done by
    taskkill /T in _terminate, so no new group is needed at launch.
    """
    Argv = catalog.LaunchArgv(Worker, GoalId, BoardPath)
    cwd = str((catalog.Here/Worker["file"]).resolve().parent)
    ## Here, each worker gets launched with it own home folder as its working directory, not 5_agent_loop
    ## The board's database is shared via an environmental variable, but each worker gets its own copy of 
    ## the board code as it imports board
    Group = {} if sys.platform == "win32" else {"start_new_session":True}
    return subprocess.Popen(Argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=cwd,**Group)
    ## subprocess.Popen(...) — actually starts the worker: runs Argv, in directory cwd, with stdout/stderr 
    ## both discarded (DEVNULL) so the worker's own console output can't corrupt the live rich board display — 
    ## the worker only communicates back through the shared SQLite board. **Group splices in the platform-specific kwarg.
    ## The Popen object is returned immediately (non-blocking); 
    ## orchestrator.py's LaunchWorker tool appends it to team.pending, and WaitForTeam is what actually waits on it later.

def _terminate(Process: subprocess.Popen) -> None:
    """Stop a worker and its uv/npx/MCP child tree (used only when a worker overruns its
    timeout). On Windows taskkill /T kills the whole tree by PID; on POSIX, a SIGTERM to
    the process group does the same"""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(Process.pid)],
                stdout = subprocess.DEVNULL,
                stderr = subprocess.DEVNULL
            )
        else:
            os.killpg(os.getpgid(Process.pid), signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass

class Team:
    """ The orchestrator's working state: the discovered workers and what has been
    launched so far. The tools read and mutate this; the agent never sees it. """

    def __init__(self, Language: str, Workers: list[dict], SiteDir: Path, BoardPath: Path) -> None:
        self.Language = Language
        self.Workers = Workers
        self.SiteDir = SiteDir
        self.BoardPath = BoardPath
        self.ByKey = {Worker["key"]: Worker for Worker in Workers}
        self.BySlug = {Worker["slug"]: Worker for Worker in Workers}
        self.Objectives: dict[str, str] = {} # Slug -> the objective the orchestrator assigned
        self.Registry: dict[int, str] = {} # GoalId -> Worker (with its objective), colours the live board
        self.Pending: list[subprocess.Popen] = [] # Launched but not yet waited for
        self.Fixed: set[str] = set() # Slugs that have had their one fix

    def _built(self, Slug:str) -> bool:
        return IsBuilt(self.SiteDir/Slug)

    def Status(self) -> str:
        Lines = []
        for Worker in self.Workers:
            Slug = Worker["slug"]
            Objective = self.Objectives.get(Slug)
            Who = f"{Worker["name"]} ({Objective})" if Objective else Worker["name"]
            Lines.append(f"  {Who} [{Slug}/]: {'built' if self._built(Slug) else 'NOT built'}")
        return "Team status:\n" + "\n".join(Lines)

    def FinishedGames(self) -> list[dict]:
        """The built games as [{label, slug}], each labeled by the title its builder gave it"""
        Games = []
        for Worker in self.Workers:
            Slug = Worker["slug"]
            if not self._built(Slug):
                continue
            Label = _read_title(self.SiteDir/Slug/"game.html") or self.Objectives.get(Slug) or Worker["name"]
            Games.append({"label":Label, "slug": Slug})
        return Games


def MakeTools(team: Team) -> list:
    """Build the orchestrator agent's tools as closures over the team state"""
    ##  each of these inner functions is a closure — it references team (the parameter MakeTools was called with) 
    ## from its enclosing scope. Python keeps the specific variables a closure actually uses alive 
    ## (via what's internally called a "cell") for as long as the closure itself is alive. The closure is kept
    ## alive as long as there is a reference to it alive somewhere, even though the parent function may have exited 

    async def AuthorStyle() -> str:
        """Author the arcade's shared house style (common.css). Do this once, before the builders start"""
        await css_agent.author_style(team.Language, team.SiteDir)
        return "Authored common.css, the shared house style for the arcade"

    def LaunchWorker(Framework: str, Objective: str) -> str:
        """Start one framework's builder, giving it a learning objective to build a game for.
        The builder invents the game itself. Returns immediately; it works in the background.
        Start all the builders, then call WaitForTeam
        
        Args:
            Framework: The Framework key, one of strands, pydantic, maf, agno, mastra
            Objective: The language learning objective this builder's game teaches, e.g.
                "greetings" or "common verbs". Give each builder a different name
        """
        Worker = team.ByKey.get(Framework)
        if Worker is None:
            return f" No builder named '{Framework}'. Your team is: {', '.join(team.ByKey)}"
        Slug = Worker["slug"]
        if Slug in team.Objectives:
            return f"{Worker['name']} is already building a game on {team.Objectives[Slug]}"
        team.Objectives[Slug] = Objective
        (team.SiteDir/Slug).mkdir(parents=True, exist_ok=True)
        Task = prompts.GameTask.format(Language=team.Language, Objective=Objective, Slug=Slug)
        GoalId = board.AddGoal(Task)
        team.Registry[GoalId] = {**Worker, "objective": Objective}
        team.Pending.append(_launch(GoalId, Worker, team.BoardPath))
        return f"Launched {Worker['name']} to invent a {team.Language} game teaching {Objective} (folder {Slug}/)"

    async def WaitForTeam() -> str:
        """Wait until every builder you have started has finished, watching the shared board
        fill in while they work. Return which games are now built"""
        Processes = team.Pending
        team.Pending = []
        if not Processes:
            return team.Status()
        Started = time.monotonic()
        ## time.monotonic() returns a floating-point number of seconds from some arbitrary, fixed starting point
        ## (not tied to the wall clock / calendar time — the starting point isn't specified and can differ between 
        ## processes). Its defining property is that it's guaranteed never to go backwards, unlike time.time(), 
        ## which reads the system clock and can jump — backwards or forwards — if the OS clock is adjusted
        Stopped = False
        ## Live is a context manager from rich. Entering it (with ... as live) takes over that region of the terminal 
        ## and switches it into "live update" mode: instead of each print/render scrolling the terminal, Live redraws
        ## the same spot in place. as live binds the live-display handle so the loop below can push new frames into it 
        ## via live.update(...). When the with block exits (the while loop finishes), Live's context manager cleanly 
        ## hands the terminal back to normal scrolling mode — that teardown is what with guarantees happens, even if 
        ## something inside raised an exception.
        ## Stopped — a one-shot flag. Once the elapsed wait time passes WorkerTimeout, the code force-kills every 
        ## still-running worker with _terminate. Without Stopped, that kill code would run again on every remaining pass
        ## through the while loop (up to ~6-7 times a second) until the killed processes actually finish exiting — 
        ## wastefully re-issuing kill signals to processes that are already dying. 
        
        with Live(live_board.Render(team.Registry), console=live_board.console, refresh_per_second=8) as live:
            ## Process.poll() is a subprocess.Popen method: it checks whether that process has exited without blocking,
            ## returning None if it's still running, or the exit code if it has finished. 
            while any(Process.poll() is None for Process in Processes):
                live.update(live_board.Render(team.Registry))
                if not Stopped and time.monotonic() - Started > WorkerTimeout:
                    for Process in Processes:
                        if Process.poll() is None:
                            _terminate(Process)
                    Stopped=True
                ## asyncio.sleep(0.15) controls how often this loop checks Process.poll(), 
                ## re-renders the board from the database, and calls live.update() — roughly 6.7 times a second.
                await asyncio.sleep(0.15)
            live.update(live_board.Render(team.Registry))
        return team.Status()


    async def TestGame(Slug:str) -> list:
        """Open one finished game in a real browser and play it to judge whether it works.
        Watch the browser to see the game being played.
        
        Args:
            Slug: The builder's folder name, which is its framework key, e.g. strands
        """

        Worker = team.BySlug.get(Slug)
        if Worker is None:
            return f"No game in folder '{Slug}'. Folders: {', '.join(team.BySlug)}"
        if not team._built(Slug):
            Missing = [ file for file in GameFiles if not (team.SiteDir/Slug/file).exists() or not
                        (team.SiteDir/Slug/file).stat().st_size]
            return f"{Slug} is not built yet. Missing or empty: {', '.join(Missing)}. Wait for the team, or fix it."
        URL = (team.SiteDir/Slug/"game.html").resolve().as_uri()
        live_board.console.print (f"Playing '{Worker['name']}'s game to check it", style=Worker["colour"])
        try:
            Verdict = await asyncio.wait_for(
                qa_agent.JudgeGame(team.Language, team.Objectives.get(Slug, ""), URL),
                timeout = QATimeout
            )
        ## The below will catch any exception raised inside try block in qa_agent which is not of type LlmCallsLimitExceededError
        ## as it will propagate upwards to the calling code. It will also catch the QATimeout exception specified in the line above 
        except Exception as Exc:
            live_board.console.print(f"  Could not finish checking {Worker['name']} ({type(Exc).__name__})", style="dim")
            return f"Could not finish checking {Slug} ({type(Exc).__name__}); leave it as built"
        ## The below if clause is reached only when the qa_agent ran successfully but somehow did not call ReportGame
        ## A better message to return would be "leave it as built (the QA agent finished without reporting a verdict)"
        if not Verdict:
            live_board.console.print(f"  Could not play {Worker['name']} (browser unavailable)", style="dim")
            return f"Could not play {Slug} (the browser may be unavailable); leave it as built."
        Works = bool(Verdict.get("works"))
        Note = Verdict.get("note", "")
        live_board.console.print(f"  {Worker['name']}: {'WORKS' if Works else 'BROKEN'}. {Note}", style="green" if Works else "red")
        return f"{Slug}: {'WORKS' if Works else 'BROKEN'}. {Note}"

    def RelaunchWorker(Framework: str, Problem: str) -> str:
        """Send a framework's builder back to fix its game, once. Returns immediately.
        Call WaitForTeam afterwards. Each game gets at most one fix attempt.
        
        Args:
            Framework: The framework key whose game is broken
            Problem: One short sentence describing what is broken
        """
        Worker = team.ByKey.get(Framework)
        if Worker is None:
            return f"No builder named '{Framework}'"
        Slug = Worker["slug"]
        if Slug in team.Fixed:
            return f"{Worker['name']} has already had its one fix; leaving the game as is."
        team.Fixed.add(Slug)
        Objective = team.Objectives.get(Slug, "")
        Task = prompts.FixTask.format(Language=team.Language, Slug=Slug, Objective=Objective, Symptom=Problem)
        GoalId = board.AddGoal(Task)
        team.Registry[GoalId] = {**Worker, "objective":Objective}
        team.Pending.append(_launch(GoalId, Worker,team.BoardPath))
        return f"Sent {Worker['name']} back to fix its game (folder {Slug}/)."        

    async def BuildHub() -> str:
        """Author the themed home page (index.html) linking every finished game. Call
        this once, after the games are built and checked."""
        Games = team.FinishedGames()
        if not Games:
            return "No finished games to link yet; build some first"
        await css_agent.build_hub(team.Language, Games, team.SiteDir)
        return f"Authored index.html linking {len(Games)} game(s): {', '.join(Game['label'] for Game in Games)}"

    return [AuthorStyle, LaunchWorker, WaitForTeam, TestGame, RelaunchWorker, BuildHub]

def BuildAgent(team:Team) -> LlmAgent:
    TeamLines = "\n".join(
        f"- {Worker['name']} (Framework key: {Worker['key']}, folder: {Worker['slug']}/)" for Worker in team.Workers
    )
    Instructions = prompts.OrchestratorPrompt.format(Language=team.Language, Team=TeamLines)
    return LlmAgent(name="Orchestrator", model=LiteLlm(model="/".join(["openai",config.ORCHESTRATOR_MODEL])),
                    instruction=Instructions, tools=MakeTools(team))

async def _run(team: Team) -> None:
    Runner = InMemoryRunner(agent=BuildAgent(team), app_name=_APP)
    try:
        Session = await Runner.session_service.create_session(app_name=_APP, user_id="Orchestrator")
        async for Event in Runner.run_async(
            user_id="Orchestrator",
            session_id = Session.id,
            new_message = types.UserContent(
                """Design and build the arcade with your team. Give each builder an objective, get the games
                built and working, then assemble the home page"""
            ),
            run_config=RunConfig(max_llm_calls=_MAX_TURNS)
        ):
            if Event.content and Event.content.parts:
                for Part in Event.content.parts:
                    if Part.text and Part.text.strip():
                        live_board.console.print(Part.text.strip(), style="dim italic")
    except LlmCallsLimitExceededError:
        ## The orchestrator used its whole budget of LLM calls. Stop cleanly and let
        ## the safety net below finish the site. The games it did build are still on disk
        print (f"\n NOTE: The orchestrator reached its {_MAX_TURNS}-step budget; wrapping up with what is built.")
    except Exception as Exc:
        ## A transient model or network error (a DNS blip, a 5xx from the API, etc.) on the
        ## orchestrator's own call would otherwise crash the whole run with a traceback.
        ## The games are already built on disk, so stop cleanly and let the safety net function
        ## defined below finish the hub. The type is printed so a real fault is still visible.
        print (f"\n NOTE: The orchestrator stopped early after an error ({type(Exc).__name__}); wrapping up with what is built")
    finally:
        try:
            await Runner.close()
        except Exception:
            pass

def _ensure_site(team:Team) -> None:
    """A non-LLM safety net so the site always has a look and a front door, even if the orchestrator
    stopped before authoring them. Only fills in what is missing."""
    if not (team.SiteDir/"common.css").exists():
        css_agent.write_template_style(team.SiteDir)
    if not (team.SiteDir/"index.html").exists():
        css_agent.write_template_hub(team.Language, team.FinishedGames(), team.SiteDir)
        print ("  NOTE: the orchestrator did not author index.html; wrote the plain template instead")

def run(Language: str, Workers: list[dict], SiteDir: Path, BoardPath: Path) -> Team:
    """Reset the shared board, then let the orchestrator agent build and check the arcade"""
    SiteDir.mkdir(parents=True, exist_ok=True)
    board.ResetBoard()
    team = Team(Language, Workers, SiteDir, BoardPath)
    asyncio.run(_run(team))
    _ensure_site(team)
    return team
