import os
from pathlib import Path
from dotenv import load_dotenv
from agents.mcp import MCPServer, MCPServerStreamableHttp, MCPServerStdio, create_static_tool_filter
from .market import TapetideAPIKey

load_dotenv(override=True)

TapetideURL = "https://mcp.tapetide.com/mcp"
ProjectDir = str(Path(__file__).resolve().parent.parent)
TavilyEnv = {"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY")}
Timeout = 120
TapetideTools = ["search_stocks", "get_stock_quote", "get_batch_quotes", "get_company_profile",
                    "get_financials", "get_forecasts", "get_shareholding", "get_price_history",
                    "get_stock_events", "get_market_news", "get_market_pulse", "get_trending_stocks",
                    "get_market_data", "screen_stocks", "screen_stocks_technical", "get_screener_ratios"]

## ---------------------------------------------------------------------------------------------------------
## Who uses which price path
## ---------------------------------------------------------------------------------------------------------
## 1. The model looking up a quote to decide
##      Who asks        : The LLM
##      Code path       : Tapetide server attached in mcp_servers.py (or, without a token, market_server.py)
##      Used with token : Tapetide directly
##
## 2. Executing a trade (BuyShares, SellShares)
##      Who asks        : accounts.py
##      Code path       : GetSharePrice in market.py
##      Used with token : Yes
##
## 3. Valuing holdings (Report(), CalculatePortfolioValue)
##      Who asks        : accounts.py
##      Code path       : GetSharePrice in market.py
##      Used with token : Yes
##
## 4. The dashboard and the API
##      Who asks        : demo/ui.py, api.py
##      Code path       : Through accounts.py and market.py
##      Used with token : Yes
##
## So when we switch to Tapetide, the model's own lookups stop using market.py. Everything the program itself
## prices still does. The original Massive setup worked the same way. With a key, the agent got Massive's
## server, while market.py still called the Massive API for trades and reports.
##
## Why the program can't use the model's lookup
## The model never supplies a price. BuyShares takes Name, Symbol, Quantity and Rationale, and accounts.py
## fetches the price itself. That keeps the execution price in trusted code, so the model can't be talked
## into buying at a made-up price. Valuation also has to work when no LLM is running: the dashboard,
## Report() at the start of every run, and the API.
##
## What market_server.py is for
## It is the fallback for the no-token case. In the code below, the else branch launches backend.market_server,
## so the agent still has a price tool when Tapetide is not available. With a token and Tapetide attached
## directly, that file is never launched.
## ---------------------------------------------------------------------------------------------------------

## The market data server for the trader
## With a key, hand the agent Tapetide's market data server
## Without one, use our market server, which serves simulated prices


if TapetideAPIKey:
    MarketParams = {
        "url":TapetideURL,
        "timeout":Timeout,
        "headers": {"Authorization":f"Bearer {TapetideAPIKey}"},
        "terminate_on_close": False  ## Tapetide answers 405 to the session DELETE, so skip it
    }
else:
    MarketParams = {"command":"uv", "args": ["run", "-m", "backend.market_server"], "cwd":ProjectDir}


def TraderMCPServers() -> list[MCPServer]:
    """The trader's MCP servers: Our Accounts server, Push Notification and Market data"""
    Params = [
        {"command": "uv", "args": ["run","-m", "backend.accounts_server"], "cwd":ProjectDir},
        {"command": "uv", "args": ["run", "-m", "backend.push_server"], "cwd":ProjectDir},
    ]
    ServerList = [MCPServerStdio(Param, client_session_timeout_seconds=Timeout) for Param in Params]
    if TapetideAPIKey:
        ServerList += [MCPServerStreamableHttp(MarketParams, client_session_timeout_seconds=Timeout,
                       tool_filter=create_static_tool_filter(allowed_tool_names=TapetideTools))]
    else:
        ServerList += [MCPServerStdio(MarketParams, client_session_timeout_seconds=Timeout)]
    return ServerList

def ResearcherMCPServers(Name: str) -> list[MCPServerStdio]:
    """The researcher's MCP servers: Fetch, Tavily web search and Memory.
    
    Tavily's server offers several tools; we restrict it to web search so the researcher
    reaches for plain search rather than its heavier crawl or deep-research tools."""

    Fetch = MCPServerStdio(
        {"command":"uvx", "args": ["--with", "mcp<2", "mcp-server-fetch"]},
        client_session_timeout_seconds=Timeout
    )
    Search = MCPServerStdio(
        {"command":"npx", "args": ["-y","tavily-mcp@latest"], "env":TavilyEnv},
        client_session_timeout_seconds=Timeout,
        tool_filter=create_static_tool_filter(allowed_tool_names=["tavily_search"])
    )
    Memory = MCPServerStdio(
        {
            "command": "npx",
            "args": ["-y","mcp-memory-libsql"],
            "env": {"LIBSQL_URL": f"file:./memory/{Name}.db"}
        },
        client_session_timeout_seconds=Timeout
    )
    return [Fetch, Search, Memory]
