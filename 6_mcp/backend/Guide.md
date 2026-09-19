# Backend Reading Guide

The backend is a simulated trading floor. Four LLM traders (Warren, George, Ray, Cathie) research the market, buy and sell shares, and log what they do. Everything is stored in one SQLite file, `accounts.db`.

## 1. The map

Arrows point from the file that uses something to the thing it uses. Everything runs from the `6_mcp` folder.

```
  RUN THESE (entry points)
  reset.py        trading_floor.py            api.py              app.py -> demo/ui.py
     |                  |                       |                         |
     |                  v                       |                         |
     |      +------------------------+          |                         |
     |      |  AGENT LAYER           |          |                         |
     |      |  traders.py            |          |                         |
     |      |   |- templates.py      |          |                         |
     |      |   |- tracers.py -------|--+       |                         |
     |      |   |- accounts_client.py|  |       |                         |
     |      |   '- mcp_servers.py    |  |       |                         |
     |      +-----+-------+----------+  |       |                         |
     |            |       |             |       |                         |
     |     spawns |       | spawns      |       |                         |
     |            v       v             |       |                         |
     |      +----------------------+    |       |                         |
     |      | MCP SERVERS          |    |       |                         |
     |      | accounts_server.py   |    |       |                         |
     |      | market_server.py     |    |       |                         |
     |      | push_server.py       |    |       |                         |
     |      +---+--------+---------+    |       |                         |
     |          |        |              |       |                         |
     v          v        v              v       v                         v
  +--------------------------------------------------------------------------------+
  | CORE   accounts.py --> market.py --> market_simulator.py                       |
  |            |                                                                   |
  |            +--> database.py --> accounts.db (SQLite)                           |
  +--------------------------------------------------------------------------------+
```

Three kinds of link are not fully drawn:

- **Subprocess links.** `traders.py` never imports the MCP server files. `mcp_servers.py` and `accounts_client.py` start them as child processes (`uv run -m backend.accounts_server`) and talk to them over stdio.
- **Minor imports.** `templates.py` and `mcp_servers.py` import `market.massive_api_key` to see whether a live data key exists. `trading_floor.py` imports `market.is_market_open`.
- **Roster imports.** `api.py` and `demo/ui.py` import the trader names from `trading_floor.py`. Both also read `accounts.py` and `database.py` directly.

## 2. Three ideas to hold in mind

1. **MCP (Model Context Protocol).** Tools are not Python functions handed to the agent. They live in separate server processes (`*_server.py`). The agent, via `mcp_servers.py`, launches those processes and calls their tools over stdio.
2. **Agent as a tool.** Each trader is an OpenAI Agents SDK `Agent`. Its research ability is another `Agent` (the Researcher) wrapped with `.as_tool()`.
3. **The database is the message bus.** Traders, the tracer, the API and the dashboard never call each other. They read and write `accounts.db`, so the UI can be a separate process.

## 3. Reading order

Go bottom-up, following the dependencies. Each file then only uses things you have already read. Steps 1 to 4 need no LLM knowledge at all.

| Step | File | Lines | Why here |
|------|------|-------|----------|
| 1 | `database.py` | 80 | The bottom layer, with no local imports |
| 2 | `market_simulator.py` | 60 | Self-contained maths |
| 3 | `market.py` | 70 | Builds on step 2 |
| 4 | `accounts.py` | 175 | The core business logic |
| 5 | `accounts_server.py`, `market_server.py`, `push_server.py` | 15 to 70 | Thin MCP wrappers over steps 3 and 4 |
| 6 | `accounts_client.py` | 50 | How code (not an LLM) calls an MCP server |
| 7 | `templates.py` | 90 | The prompts the traders receive |
| 8 | `mcp_servers.py` | 60 | Which servers each agent gets |
| 9 | `tracers.py` | 75 | Turns agent activity into log rows |
| 10 | `traders.py` | 125 | Where everything comes together |
| 11 | `trading_floor.py` | 55 | The scheduler loop |
| 12 | `reset.py`, `api.py` | 50, 115 | Utilities and the read-only HTTP layer |
| 13 | `../app.py`, `../demo/` | | The Gradio dashboard, outside `backend/` |

## 4. What each file contains

### Foundation

**`database.py`** contains two SQLite tables and four functions.
- `accounts` holds one JSON blob per trader. `logs` holds timestamped activity lines.
- `write_account` / `read_account` upsert and fetch that JSON. `write_log` / `read_log` append and read log rows.
- Look for: the tables are created at import time. `DB = "accounts.db"` is a relative path, so it depends on the working directory. That is why every subprocess is launched with `cwd=PROJECT_DIR`.

**`market_simulator.py`** contains `simulated_price(ticker, when)`.
- It hashes the ticker into a seed and sums several octaves of smooth noise. The same ticker and time always give the same price, and prices drift like a real stock.
- Look for: there is no randomness and no state. It is fully deterministic.

**`market.py`** contains `get_share_price(symbol)`.
- With `MASSIVE_API_KEY` set it uses the Massive API. Without one it uses the simulator.
- Massive access is tiered: last trade, then snapshot, then previous close. The module remembers the first tier your plan allows (`plan_tier`).
- `is_market_open()` reports market status, and is always True on simulated data.

**`accounts.py`** is the heart of the domain.
- `Transaction` and `Account` are Pydantic models. `Account.get(name)` loads from the database, or creates a fresh account with $10,000.
- `buy_shares` and `sell_shares` apply a 0.2% spread, update holdings, record a `Transaction` (sells have negative quantity), and save.
- `report()` returns the account as JSON with portfolio value and profit/loss. It also appends to the value time series.
- `change_strategy` lets a trader rewrite its own strategy.
- Look for: every mutation ends in `self.save()` and usually a `write_log`.

### MCP layer

**`accounts_server.py`** exposes `Account` as an MCP server (FastMCP).
- The tools are `get_balance`, `get_holdings`, `buy_shares`, `sell_shares` and `change_strategy`.
- Two resources are `accounts://accounts_server/{name}` (the report) and `accounts://strategy/{name}` (the strategy).
- Look for: the docstrings. The LLM reads them as the tool descriptions.

**`market_server.py`** exposes one tool, `lookup_share_price`. It is used only when there is no Massive key.

**`push_server.py`** exposes one tool, `push`, which sends a Pushover phone notification. It is the only file that does not touch accounts or market data.

**`accounts_client.py`** is a plain MCP client.
- `read_accounts_resource` and `read_strategy_resource` start `accounts_server` as a subprocess, read one resource and return the text.
- The Windows/Jupyter block at the top only works around a stderr limitation. Skip it on a first read.

### Agent layer

**`templates.py`** holds all the prompt text.
- `trader_instructions` is the system prompt. `trade_message` (find opportunities) and `rebalance_message` (review holdings) are the per-run user prompts.
- `researcher_instructions` and `research_tool` describe the Researcher.
- `note` changes depending on whether live market tools exist.

**`mcp_servers.py`** decides which tool servers each agent gets.
- `trader_mcp_servers()` returns the accounts, push and market servers.
- `researcher_mcp_servers(name)` returns Fetch, Tavily search (restricted to `tavily_search`) and a per-trader Memory database.
- Each one is an `MCPServerStdio` from the Agents SDK.

**`tracers.py`** is how the dashboard's log panel gets its lines.
- `make_trace_id` embeds the trader's name in the trace id (`trace_<name>0<random>`).
- `LogTracer` receives every trace and span event. `get_name` recovers the trader name from the id, and `write_log` stores the line.
- Look for: the name is encoded in the id because a tracing callback has no other way to know which trader it belongs to.

**`traders.py`** is the most important file for the LLM side.
- `get_model` picks the client for the model name: OpenRouter, DeepSeek, Grok, Gemini or the default OpenAI.
- `Trader.create_agent` builds the Researcher tool, then the trader `Agent`.
- The call chain is `run` > `run_with_trace` > `run_with_mcp_servers` > `run_agent`. `run_with_trace` wraps the run in a named trace. `run_with_mcp_servers` starts all servers with an `AsyncExitStack`, which guarantees they shut down. `run_agent` fetches the account and strategy, builds the prompt and calls `Runner.run`.
- `run` flips `do_trade` afterwards, so runs alternate between trading and rebalancing.

**`trading_floor.py`** is the entry point.
- It reads `.env` settings: `RUN_EVERY_N_MINUTES`, `RUN_EVEN_WHEN_MARKET_IS_CLOSED` and `USE_MANY_MODELS`.
- It defines the four names and models, and `create_traders()`.
- `run_every_n_minutes` registers `LogTracer`, then loops: run all traders concurrently with `asyncio.gather`, sleep, repeat.

### Utilities and views

**`reset.py`** holds the four strategy prompts. `reset_traders()` wipes each account to $10,000 with its strategy.

**`api.py`** is a read-only FastAPI app. It has endpoints for the trader list, market status, one trader's full state and a trader's logs. It computes per-holding average cost and unrealised profit itself.

**`__init__.py`** only marks `backend` as a package. The relative imports (`from .market import ...`) depend on it.

## 5. How to read effectively

Do these on each file in order:

1. Read the docstrings and function names first, then the bodies. This codebase is short enough to read in full.
2. Ask two questions: what does this file import, and who imports it? The map in section 1 answers both.
3. Run a small experiment before moving on.

Safe experiments, from `6_mcp`:

```
uv run python -c "from backend.market_simulator import simulated_price as p; print(p('AAPL'))"
uv run python -c "from backend.market import get_share_price as g; print(g('AAPL'))"
```

Then the whole system, one entry point at a time. Importing `database.py` creates `accounts.db`, and accounts stay empty until `reset` has run:

```
uv run -m backend.reset                        # fill the four accounts
uv run -m backend.trading_floor                # start the trader loop (uses LLM calls)
uv run app.py                                  # dashboard in a browser
uv run uvicorn backend.api:app --port 8000     # optional JSON API
```

## 6. One trading cycle, end to end

Trace this once you have read `traders.py`:

1. `trading_floor.run_every_n_minutes` wakes and calls `trader.run()` for all four traders in parallel.
2. `run_with_trace` opens a trace named `<Name>-trading`, and `LogTracer` starts writing log rows.
3. `run_with_mcp_servers` launches three trader servers and three researcher servers as subprocesses.
4. `run_agent` reads the account and strategy through `accounts_client`, then builds the prompt with `templates`.
5. `Runner.run` lets the LLM call tools. Researcher tools search the web. `accounts_server` runs `Account.buy_shares` or `sell_shares`, which prices the trade through `market.py` and saves through `database.py`. `push_server` sends the summary notification.
6. The servers shut down, `do_trade` flips, and the loop sleeps.
7. The dashboard or API reads `accounts.db` and shows the result. It never talks to the traders directly.

## 7. Things to notice

- `Account.get_profit_loss()` calls `calculate_profit_loss()` without its required argument. Nothing calls it, but it would raise if used. `report()` and `api.py` call `calculate_profit_loss` correctly.
- Errors in a trader run are caught and printed in `Trader.run`, so one failing trader does not stop the other three.
- Tool docstrings in the `*_server.py` files and the text in `templates.py` are both part of the LLM's prompt. Editing them changes agent behaviour without changing any logic.
