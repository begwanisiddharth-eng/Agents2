""" A tiny SQLite Todo board: The shared substrate every Week 5 worker uses.

A worker is handed one goal. To reach it, the worker writes its own step Todos
under that goal, ticks each one off as it finishes, and marks the goal done once
the steps are complete. Days 1 to 4 each run their own little board like this;
Day 5 the same idea grows into a shared board that coordinates a whole team. The
board is a single file with one table, so it needs no server and behaves the same
on Mac and Windows. WAL mode plus a busy timeout lets several agents read and write
at once without tripping over each other.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from rich.console import Console

BoardPath = Path(os.environ.get("BOARD_PATH", Path(__file__).resolve().parent/"board.sqlite"))

def _connect(path: Path=BoardPath) -> sqlite3.Connection:
    Conn = sqlite3.connect(path)
    ## By default, sqlite3 returns each row as a plain tuple, so you'd access fields positionally: 
    ## row[0], row[1], etc. — you have to remember that column 2 is task and column 3 is status.
    ## Setting conn.row_factory = sqlite3.Row changes what a fetched row looks like. 
    ## Instead of a plain tuple, each row becomes a sqlite3.Row object that supports:
    ## Access by column name: row["task"], row["status"] — same values, but readable by name instead of a fragile index.
    ## Conversion to a plain dict: dict(row) works directly on a sqlite3.Row, giving you {"id": 1, "task": "...",...}
    Conn.row_factory = sqlite3.Row
    Conn.execute("PRAGMA journal_mode=WAL") ## Read and write can be done simultaneously
    ## In case of collision, retry for 5 seconds instead of immediately raising "database is locked"
    Conn.execute("PRAGMA busy_timeout=5000")
    return Conn

def ResetBoard(path: Path = BoardPath) -> None:
    """Create a fresh, empty board, dropping anything already there"""
    ## The with _connect(Path) acts as a context manager, committing on success and rolling back on failure 
    with _connect(path) as Conn:
        Conn.execute("DROP TABLE IF EXISTS Todos")
        Conn.execute(
            """
            CREATE TABLE Todos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER, 
                task TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT NOT NULL DEFAULT ''
            )
            """
        )
        ## Single table models both goals and steps. Goals have parent_id as NULL
        ## status moves through 'pending' -> 'in_progress' -> 'done'
        ## result holds the text the worker records on completion

def AddGoal(Task: str, path=BoardPath) -> int:
    """Add a top-level goal to the board and return its id"""
    with _connect(path) as Conn:
        Cursor = Conn.execute("INSERT INTO Todos (task) VALUES (?)", (Task,))
        return Cursor.lastrowid

def AddStep(GoalId: int, Task: str, path: Path = BoardPath) -> int:
    """Add a step under a goal and return its id"""
    with _connect(path) as Conn:
        Cursor = Conn.execute("INSERT INTO Todos (parent_id, task) VALUES (?,?)", (GoalId,Task))
        return Cursor.lastrowid

def ListTodos(path: Path = BoardPath) -> list[dict]:
    """Return every Todo on the board, goals and steps, oldest first"""
    with _connect(path) as Conn:
        Rows = Conn.execute(
            "SELECT id, parent_id, task, status, result from Todos ORDER BY id"
        ).fetchall()
        return [dict(Row) for Row in Rows]


def ClaimTodo(TaskId: int, path: Path = BoardPath) -> None:
    """Mark a Todo as in_progress, so a worker can show it has picked it up"""
    with _connect(path) as Conn:
        Conn.execute("UPDATE Todos SET status='in_progress' WHERE id = ?", (TaskId,))


def CompleteTodo(TaskId: int, Result: str, path: Path = BoardPath) -> None:
    """Mark a Todo as done and record its result"""
    with _connect(path) as Conn:
        Conn.execute("UPDATE Todos SET status ='done', result=? WHERE id=?", (Result,TaskId))

def ShowBoard(path: Path = BoardPath) -> None:
    """Print the board for a human: each goal with its steps indented beneath,
    done Todos struck through in green and anything in progress in yellow. This
    is just a pretty view; the agent's ShowTodos tool still gets plain dicts.
    """

    Todos = ListTodos(path)
    Lines = []
    for Goal in [Todo for Todo in Todos if Todo["parent_id"] is None]:
        Lines.append(_format(Goal, "Goal", ""))
        for Step in [Todo for Todo in Todos if Todo["parent_id"]==Goal["id"]]:
            Lines.append(_format(Step,"Step", "  "))
    if Lines:
        ## Print the whole board in one go. Printing line by line makes a Jupyter
        ## kernel emit a separate block per line, which creates gaps between lines; 
        ## soft_wrap keeps a long goal line from wrapping
        Console().print("\n".join(Lines), soft_wrap=True)

def _format(Todo:dict, Kind:str, Indent: str) -> str:
    Label = f"{Indent}{Kind} #{Todo['id']}: {Todo['task']}"
    if Todo["status"] == "done":
        Line = f"[green][strike]{Label}[/strike][/green]"
        if Todo["result"]:
            Line += f"  [dim]{Todo['result']}[/dim]"
        return Line
    if Todo["status"] == "in_progress":
        return f"[yellow]{Label}[/yellow]"
    return Label
