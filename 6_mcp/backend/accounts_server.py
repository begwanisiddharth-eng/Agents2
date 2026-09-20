from mcp.server.fastmcp import FastMCP
from .accounts import Account

mcp = FastMCP("accounts_server", log_level="WARNING")

## Since we have defined the MCP variable name as mcp, the tool decorator becomes @mcp.tool
## If we defined MyServer = FastMCP("accounts_server"), then the tool decorator would be @MyServer.tool

@mcp.tool()
async def GetBalance(Name:str) -> float:
    """Get the cash balance of the given account name.

    Args:
        Name: The name of the account holder    
    """
    return Account.Get(Name).balance

@mcp.tool()
async def GetHoldings(Name: str) -> dict[str,int]:
    """Get the holdings of the given account name.

    Args:
        Name: The name of the account holder
    """
    return Account.Get(Name).holdings

@mcp.tool()
async def BuyShares(Name: str, Symbol: str, Quantity: int, Rationale: str) -> str:
    """Buy shares of a stock
    
    Args:
        Name: The name of the account holder
        Symbol: The symbol of the stock
        Quantity: The quantity of shares to buy
        Rationale: The rationale for the purchase and fit with the account's strategy    
    """
    return Account.Get(Name).BuyShares(Symbol,Quantity,Rationale)

@mcp.tool()
async def SellShares(Name: str, Symbol: str, Quantity: int, Rationale: str) -> str:
    """Sell shares of a stock
    
    Args:
        Name: The name of the account holder
        Symbol: The symbol of the stock
        Quantity: The quantity of shares to sell
        Rationale: The rationale for the sale and fit with the account's strategy    
    """
    return Account.Get(Name).SellShares(Symbol,Quantity,Rationale)

@mcp.tool()
async def ChangeStrategy(Name: str, Strategy: str) -> str:
    """At your discretion, if you choose to, call this to change your investment strategy for the future
    
    Args:
        Name: The name of the account holder
        Strategy: The new strategy for the account
    """
    return Account.Get(Name).ChangeStrategy(Strategy)


## In the below code, "accounts://accounts_server" is just a scheme and a path. accounts_server has nothing to do
## with the MCP server name. The name part is an argument whose name must match the argument supplied to the function
## it decorates. For instance, we could change "accounts://accounts_server" to "acc://acc_ser/{Name}" Then the place from
## where this resource is called would have to use syntax like read_resource(f"acc://acc_ser/{Name}"). 
## The scheme and path are just an agreed address. The server says "I answer requests for this address", and the client 
## says "I want what is at this address". 

@mcp.resource("accounts://accounts_server/{Name}")
async def ReadAccountResource(Name:str) -> str:
    account = Account.Get(Name.lower())
    return account.Report()

@mcp.resource("accounts://strategy/{Name}")
async def ReadStrategyResource(Name:str) -> str:
    account = Account.Get(Name.lower())
    return account.GetStrategy()


if __name__ == "__main__":
    mcp.run(transport='stdio')