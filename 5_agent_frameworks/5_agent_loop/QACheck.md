# How `TestGame` checks a game, and how it handles failure

`TestGame` ([orchestrator.py:221-252](orchestrator.py#L221-L252)) is one of the tools the
orchestrator LLM agent can call (built in `MakeTools`). It is the orchestrator's only way
to judge whether a finished game actually works — it delegates the real browser-driving
work to `qa_agent.JudgeGame` and is mostly a thin, defensive wrapper around that call.

## What `TestGame` does, step by step

1. **Resolve the worker.** `team.BySlug.get(Slug)` — if the LLM passes a folder name that
   doesn't exist, this returns `None` and `TestGame` returns a plain string telling it so,
   without ever calling `qa_agent`.
2. **Check the game is actually built.** `team._built(Slug)` re-checks the three expected
   files (`game.html`, `game.css`, `game.js`) exist and are non-empty. If not, it returns a
   string listing what's missing — again, no call into `qa_agent` at all.
3. **Call `qa_agent.JudgeGame`, bounded by a timeout.**
   ```python
   Verdict = await asyncio.wait_for(
       qa_agent.JudgeGame(team.Language, team.Objectives.get(Slug, ""), URL),
       timeout = QATimeout
   )
   ```
   This is the one call that can actually fail in interesting ways (see below).
4. **Interpret the result.** A falsy `Verdict` (`None`) means "could not play it";
   a real `{"works": bool, "note": str}` dict is printed to the live console in the
   worker's colour (green for works, red for broken) and summarized in the string
   returned to the orchestrator LLM.

## What can go wrong inside `qa_agent.JudgeGame`

`JudgeGame` ([qa_agent.py:39-116](qa_agent.py#L39-L116)) builds a fresh, disposable
`LlmAgent` per game, equipped with a Playwright MCP browser tool and a `ReportGame` tool,
and runs it for up to `_MAX_CALLS` (25) LLM turns. Several distinct things can happen:

- **The agent reports normally.** It calls `ReportGame(works, note)`, which just writes
  into the closure variable `Verdict`. `JudgeGame` returns `Verdict` — the success path.
- **The agent never reports and just runs out of turns.** ADK raises
  `LlmCallsLimitExceededError` from inside `Runner.run_async`. This is the *one* exception
  `JudgeGame` catches explicitly (line 96). Rather than treating a silent agent as a
  failure, it assumes that since the agent was still making tool calls 25 turns in, the
  game was loading and responding, and synthesizes a passing verdict
  (`Verdict.setdefault("works", True)` with an explanatory note).
- **The agent never calls `ReportGame` at all**, and no exception is raised (e.g. it just
  stops). `Verdict` stays `{}`. The function's last line, `return Verdict or None`, turns
  an empty dict into `None` — `JudgeGame`'s documented way of saying "the game could not
  be reached or judged."
- **Anything else raises.** Nothing else inside the `try` is caught — a broken MCP
  connection (Chrome or `npx @playwright/mcp` not available/failing to start), a network
  or API error calling the LLM, a malformed tool response, an ADK-internal error, session
  creation failing, etc. all propagate straight out of `JudgeGame` as whatever exception
  type they naturally are.
- **The caller's own timeout fires.** `TestGame` wraps the whole call in
  `asyncio.wait_for(..., timeout=QATimeout)`. If a game hangs (a wedged browser, a model
  that keeps clicking around without ever finishing), `wait_for` cancels the `JudgeGame`
  coroutine, which raises `asyncio.CancelledError` at whatever `await` point it's
  currently sitting on; `wait_for` then re-raises this to the caller as
  `asyncio.TimeoutError`.

## Cleanup on every one of those paths

Regardless of which of the above happens, `JudgeGame`'s `finally` block (lines 103-116)
always runs — including on the cancellation path, since a `finally` still executes while
an `asyncio.CancelledError` is propagating. It closes the MCP browser toolset and the
runner, each individually bounded by its own `asyncio.wait_for(..., timeout=_CLOSE_TIMEOUT)`
(10s) with `except Exception: pass`. This exists specifically so that a *stuck* browser
can't turn a timeout into a hang: `TestGame`'s own timeout cancels `JudgeGame`, and
`JudgeGame`'s teardown is itself capped, so control reliably returns to `TestGame` within
`QATimeout + _CLOSE_TIMEOUT` seconds at the very most, not indefinitely.

## How `TestGame` turns all of that into something the orchestrator can use

`TestGame` puts the entire `qa_agent.JudgeGame` call inside one broad
`try: ... except Exception as Exc:` (lines 238-245). This single `except` catches every
failure mode described above uniformly — `asyncio.TimeoutError` from its own `wait_for`,
`LlmCallsLimitExceededError` (in the unlikely case it somehow escaped `JudgeGame`), and
any MCP/network/ADK error. In every case it:

1. Prints a short, dim status line naming the worker and the exception's class name, so a
   human watching the live board sees *that* a check failed and roughly why.
2. Returns a plain descriptive string to the calling LLM — `"Could not finish checking
   {Slug} (...); leave it as built"` — rather than letting the exception propagate.

The `Verdict is None` case (browser unavailable, nothing reported) is handled the same
way one level down: a dim status line plus a "leave it as built" string.

The effect is that **no failure inside QA checking can ever crash the orchestrator's own
agent loop.** Every outcome — success, timeout, MCP failure, silent agent — collapses into
a short string result that becomes the orchestrator LLM's next piece of context, and the
LLM itself decides what to do about it (usually: treat the game as already built and move
on, since a QA failure is about the *check*, not proof the game is actually broken).
