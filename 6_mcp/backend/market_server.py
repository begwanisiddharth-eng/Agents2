from mcp.server.fastmcp import FastMCP
from .market import GetSharePriceAsync

mcp = FastMCP("market_server", log_level="WARNING")

@mcp.tool()
async def LookupSharePrice(Symbol: str) -> float:
    """This tool provides the current prices of the given stock symbol

    Args:
        Symbol: The symbol of the stock
    """
    return await GetSharePriceAsync(Symbol)

if __name__=="__main__":
    mcp.run(transport='stdio')
