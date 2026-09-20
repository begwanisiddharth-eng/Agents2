"""Share prices from the Tapetide market data API, or a simulator when no key is set.

Set TAPETIDE_TOKEN to use live data. Without it, prices come from market_simulator
so the whole trading floor still runs out of the box.
"""

from agents.mcp import MCPServerStreamableHttp
import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta, timezone

from dotenv import load_dotenv

from .market_simulator import SimulatedPrice

load_dotenv(override=True)

TapetideAPIKey = os.getenv("TAPETIDE_TOKEN")

TapetideURL = "https://mcp.tapetide.com/mcp"
Timeout = 60
IST = timezone(timedelta(hours=5, minutes=30))
Open, Close = time(9,15), time(15,30)

## FastMCP puts every logger at INFO, so each price lookup would print about 30 lines of HTTP and handshake detail
for Name in ("httpx", "mcp.client"):
    logging.getLogger(Name).setLevel(logging.WARNING)

async def CallTool(Tool: str, Args: dict) -> dict:
    """Call one Tapetide MCP tool in a short-lived session and return its parsed JSON"""
    Params = {
        "url":TapetideURL,
        "timeout":Timeout,
        "headers": {"Authorization":f"Bearer {TapetideAPIKey}"},
        "terminate_on_close": False  ## Tapetide answers 405 to the session DELETE, so skip it
    }
    async with MCPServerStreamableHttp(params=Params, client_session_timeout_seconds=Timeout) as Server:
        Result = await Server.call_tool(Tool,Args)
    Text = Result.content[0].text
    if Result.isError:
        raise ValueError(Text)
    return json.loads(Text)

async def GetSharePriceAsync(Symbol: str) -> float:
    """Return the current price for an NSE symbol from Tapetide, or a simulated price without a token or if the API fails"""
    if TapetideAPIKey:
        try:
            Quote = await CallTool("get_stock_quote", {"symbol": Symbol})
            return float(Quote["data"]["price"])
        except Exception as e:
            print(f"Tapetide API unavailable ({e}); using a simulated price")
    return SimulatedPrice(Symbol)

def GetSharePrice(Symbol: str) -> float:
    """Sync wrapper around GetSharePriceAsync. Runs in a worker thread so it also works inside a running event loop"""
    with ThreadPoolExecutor(max_workers=1) as Pool:
        return Pool.submit(asyncio.run, GetSharePriceAsync(Symbol)).result()

def IsMarketOpen() -> bool:
    """Whether NSE is open (Mon-Fri 09:15-15:30 IST, holidays ignored); always True on simulated data"""
    if not TapetideAPIKey:
        return True
    Now = datetime.now(IST)
    return Now.weekday() < 5 and Open <= Now.time() <= Close