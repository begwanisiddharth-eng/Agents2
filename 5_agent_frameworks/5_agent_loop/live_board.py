"""The live board: a rich.Live view of the shared board while the team works.

Each game is drawn in its owner's colour, with the steps that worker writes
for itself indented beneath in the same colour. Done items are dimmed and struck
through, the one in progress is bold, pending is plain. A small legend maps colour
to framework. The colour comes from the orchestrators's registry (GoalId->Worker),
so the board schema and the workers stay untouched; a worker never needs to know
its own colour.
"""


from __future__ import annotations

from rich.console import Console, Group
from rich.text import Text

import board
console = Console()

def _line(Todo: dict, Colour: str, Label:str, Indent: str = "") -> Text:
    text = Text(Indent)
    if Todo["status"] == "done":
        text.append(Label, style=f"{Colour} dim strike")
        if Todo["result"]:
            text.append(f"   {Todo['result']}", style="dim")
    elif Todo["status"] == "in_progress":
        text.append(Label, style=f"bold {Colour}")
    else:
        text.append(Label, style=Colour)
    return text

def Render(Registry: dict[int,dict]) -> Group:
    """Build the whole board as one renderable from the current board state"""
    Todos = board.ListTodos()
    ## The following is a type hint for readability. It declares Children as an empty dict
    ## whose keys are either an int or None (a task's Id, or None for "this is a top level goal")
    ## and whose values are list of dicts (the Todo rows themselves). It is a type hint and is not
    ## enforced at runtime.
    Children: dict[int | None, list[dict]] = {}
    for Todo in Todos:
        ## Children.setdefault(Todo["parent_id"], []).append(Todo)
        ## dict.setdefault(key, default) means: "if key is already in the dict, return its existing value; 
        ## otherwise, insert key: default into the dict and return that default." 
        ## Either way you get back a list you can immediately .append(...) to.
        ## This is written in a simpler way below:
        if Todo["parent_id"] is None:
            if None not in Children:
                Children[None] = [Todo]
            else:
                Children[None].append(Todo)
        elif Todo["parent_id"] not in Children:
            Children[Todo["parent_id"]] = [Todo]
        else:
            Children[Todo["parent_id"]].append(Todo)
    Lines: list[Text] = []
    for Goal in Children.get(None, []):
        Worker = Registry.get(Goal["id"])
        Colour = Worker["colour"] if Worker else "white"
        if Worker:
            Objective = Worker.get("objective")
            Label = f"{Worker['name']}: {Objective}" if Objective else Worker["name"]
        else:
            Label = Goal["task"][:48]
        Lines.append(_line(Goal, Colour, Label))
        for Step in Children.get(Goal["id"],[]):
            Lines.append(_line(Step, Colour, Step["task"], Indent="    "))
    
    Legend = Text("\n")
    Seen = set()
    ## The below piece of code is required because for the Team class, the Registry
    ## object is a dictionary whose key is an integer (goal id) and whose values is
    ## the dictionary of the worker who has been assigned that goal plus the objective
    ## key. A single worker can own two goal ids over the course of a run — one from its original 
    ## LaunchWorker call, and a second one if RelaunchWorker sends it back to fix a broken game. 
    ## Each of those creates its own separate {**worker, "objective": objective} dict and stores it 
    ## under its own goal id key. So registry.values() will yield that worker's dict twice in that case
    for Worker in Registry.values(): ## Effectively a list of dictionaries
        if Worker['name'] in Seen:
            continue
        Seen.add(Worker['name'])
        Legend.append(f"{Worker['name']}  ", style=Worker["colour"])
    Lines.append(Legend)
    return Group(*Lines)
