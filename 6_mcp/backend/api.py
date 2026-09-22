""" HTTP API over the trading floor, for a separate frontend to consume.

The Gradio dashboard in demo/ reads accounts.db in-process. This serves the same
data as JSON so a decoupled web front-end can render it. All functions in this 
file are read-only; the trading floor writes the database in a separate process.

Run this file from the 6_mcp directory so it shares the engine's accounts.db:

    uv run uvicorn backend.api:app --port 8000
"""
from fastapi import FastAPI, HTTPException

from backend import market
from backend.accounts import Account
from backend.database import ReadLog
from backend.trading_floor import Names, LastNames, ShortModelNames

## Every response below is built fresh from accounts.db and the market module on each
## request. Nothing here is cached

## Mirrors the log colours in demo/ so the frontend reproduces the same panel.

LOG_COLORS = {
    "trace": "#87CEEB",
    "agent": "#00dddd",
    "function": "#00dd00",
    "generation": "#dddd00",
    "response": "#aa00dd",
    "account":  "#dd0000"
}
DEFAULT_LOG_COLOR = "#87CEEB"

## The roster is the fixed list of traders (Name, LastName, Model) from trading_floor.py.
## It is built once at import time, not per request, since it never changes while the process runs.
## RosterByName indexes it by lowercase name for fast, case-insensitive lookups.

Roster = [
    {'name':Name, "lastname":LastName, "model_name":ModelName}
    for Name, LastName, ModelName in zip(Names,LastNames,ShortModelNames)
]

RosterByName = {Trader["name"].lower(): Trader for Trader in Roster}

app = FastAPI(title="Trading Floor")

def AverageCost(account:Account, Symbol:str) -> float:
    """Average price paid across this symbol's buys, for per-holding profit"""
    ## Only buys (quantity>0) count towards cost basis; sells don't change the average
    ## price of what is still held. This is a simple average, not FIFO/LIFO lot tracking.
    Spend = sum([T.price*T.quantity for T in account.transactions if T.symbol==Symbol and T.quantity >0])
    TotalQuantityBought = sum([T.quantity for T in account.transactions if T.symbol==Symbol and T.quantity >0])
    return Spend/TotalQuantityBought if TotalQuantityBought else 0.0

def HoldingsDetails(account:Account) -> list[dict]:
    """Current holdings with price, average cost, market value and unrealized PnL added"""
    Details = []
    for Symbol, Quantity in account.holdings.items():
        Price = market.GetSharePrice(Symbol)
        Cost = AverageCost(account,Symbol)
        Details.append(
            {
                "symbol":Symbol,
                "quantity": Quantity,
                "price": Price,
                "avg_cost": Cost,
                "market_value": Price*Quantity,
                "unrealized_pnl": (Price-Cost)*Quantity
            }
        )
    return Details

def RequireTrader(Name: str) -> dict:
    ## Shared 404 guard; every endpoint that takes a trader name calls this first,
    ## so an unknown name always fails the same way instead of each route re-checking
    Trader = RosterByName.get(Name.lower())
    if not Trader:
        raise HTTPException(status_code=404, detail=f"Unknown trader {Name}")
    return Trader

@app.get("/api/traders")
def GetTraders() -> list[dict]:
    """The three traders on the floor"""
    ## Consumed by frontend/src/main.ts (getTraders) to build one panel per trader
    ## on startup. Just the roster; no prices or database reads happen here
    return Roster

@app.get("/api/market")
def GetMarket() -> dict:
    """Whether price source is live, and whether the market is open"""
    ## Consumed once at startup by frontend/src/main.ts (loadMarket) to set the
    ## market badge in the header. Not polled again after that
    Source = "Tapetide" if market.TapetideAPIKey else "Simulator"
    return {"source": Source, "is_market_open":market.IsMarketOpen()}


@app.get("/api/traders/{Name}")
def GetTrader(Name: str) -> dict:
    """The full details of the trader: value, strategy, holdings, transactions, pnl and history"""
    ## Consumed by frontend/src/main.ts (pollData, every DATA_POLL_MS) for each trader
    ## in parallel, and rendered by panel.ts (value/pnl/strategy), heatmap.ts (holdings),
    ## chart.ts (time_series) and transactions.ts (transactions)
    Trader = RequireTrader(Name)
    account = Account.Get(Name)
    Holdings = HoldingsDetails(account)
    ## Portfolio value = Cash still in the account + current market value of holdings
    PortfolioValue = account.balance + sum(h["market_value"] for h in Holdings)
    return {
        "name": Trader["name"],
        "lastname": Trader["lastname"],
        "model_name": Trader["model_name"],
        "balance": account.balance,
        "strategy": account.strategy,
        "portfolio_value": PortfolioValue,
        "pnl": account.CalculateProfitLoss(PortfolioValue),
        "holdings": Holdings,
        "transactions": account.ListTransactions(),
        ## Sent in full on every poll; the chart in state.ts only uses this once, to seed
        ## itself, then grows its own line client-side from later portfolio_value values
        "time_series": [{"datetime":ts, "value":value} for ts, value in account.portfolio_value_time_series]
    }

@app.get("/api/traders/{Name}/logs")
def GetTraderLogs(Name: str, last_n: int =13) -> list[dict]:
    """Recent trace and account log lines, oldest first, with their panel colour"""
    ## Consumed by frontend/src/main.ts (pollLogs, every LOG_POLL_MS) and rendered by
    ## log.ts. ReadLog only touches SQLite, so this endpoint makes no market data calls,
    ## unlike GetTrader() above
    RequireTrader(Name)
    Rows = list(ReadLog(Name,last_n))
    return [
        {"datetime": ts, "type": kind, "message": message, "color": LOG_COLORS.get(kind,DEFAULT_LOG_COLOR)}
        for ts, kind, message in Rows
    ]

