"""The worker manifest: which framework builds which game, how to launch it, and the
color it uses on the live board.
Discovery is just "is the file there". The launch paths are the only place the cross-folder
layout is written down, so a folder rename is a one-line fix here.
"""

from __future__ import annotations

import shutil
from pathlib import Path

Here = Path(__file__).resolve().parent

## One record per framework. key is also the slug, the folder its game is built into
## file is relative to this folder. colour is a rich colour for the live board;
## runner picks the launcher (uv run vs npx tsx)

Workers = [
    {"key": "strands", "name":"AWS Strands", "colour":"cyan", "file": "../2_strands_pydantic/strands_worker.py", "runner":"python"},
    {"key": "pydantic", "name":"Pydantic AI", "colour":"green", "file": "../2_strands_pydantic/pydantic_worker.py", "runner":"python"},
    {"key": "maf", "name":"Microsoft Agent Framework", "colour":"magenta", "file": "../3_maf_agno/maf_worker.py", "runner":"python"},
    {"key": "agno", "name":"Agno", "colour":"yellow", "file": "../3_maf_agno/agno_worker.py", "runner":"python"},
    {"key": "mastra", "name": "Mastra", "colour": "blue", "file": "../4_mastra/worker.ts", "runner": "node"}
]

def Discover(skip: tuple[str, ...]=()) -> list[dict]:
    """The workers whose files exist on disk, minus any skipped by key. Each result
    is its manifest record with slug set to its key (the folder the game builds into);
    the game itself is invented at runtime, so it is not fixed here"""
    Found = []
    for Worker in Workers:
        if Worker["key"] in skip:
            continue
        if (Here/Worker["file"]).exists():
            Found.append({**Worker, "slug": Worker["key"]})
        ## To provide an example of what the above if statement does, assume "strands" is not in skip.
        ## Worker = {"key": "strands", "name": "AWS Strands", "colour": "cyan", 
        ## "file": "../2_strands_pydantic/strands_worker.py", "runner": "python"}
        ## Here / Worker["file"] → D:\Python\Agents2\5_agent_frameworks\5_agent_loop\..\2_strands_pydantic\strands_worker.py, 
        ## which resolves to D:\Python\Agents2\5_agent_frameworks\2_strands_pydantic\strands_worker.py
        ## That file exists on disk, so the if is true, and Found gets: {"key": "strands", "name": "AWS Strands", "colour": "cyan",
        ## "file": "../2_strands_pydantic/strands_worker.py", "runner": "python", "slug": "strands"}
    return Found

def LaunchArgv(Worker:dict, TaskId: int, BoardPath: Path) -> list[str]:
    """The subprocess argv that runs a worker in Day 5 mode against the shared board.
    The launcher (uv or npx) is resolved to its full path with shutil.which. On Windows,
    a bare "npx" is not found by subprocess.Popen, because npx is a .cmd shim and Popen
    does not consult PATHEXT; resolving it first is what the MCP libraries do to spawn
    npx, and on Mac and Linux which returns the same plain path.
    """
    path = str((Here/Worker["file"]).resolve())
    if Worker["runner"] == "python":
        return [shutil.which("uv") or "uv", "run", path, str(TaskId), str(BoardPath)]
    return [shutil.which("npx") or "npx", "tsx", path, str(TaskId), str(BoardPath)]
