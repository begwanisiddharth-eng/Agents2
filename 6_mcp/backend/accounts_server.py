from mcp.server.fastmcp import FastMCP
from .accounts import Account

mcp = FastMCP("accounts_server")

## Since we have defined the MCP variable name as mcp, the tool decorator becomes @mcp.tool
## If we defined MyServer = FastMCP("accounts_server"), then the tool decorator would be @MyServer.tool


@mcp.tool()
async def get_balance(name:str) -> float:
    """Get the cash balance of the given account name.

    Args:
        name: The name of the account holder    
    """
    return Account.get(name).balance

@mcp.tool()
async def get_holdings(name: str) -> dict[str,int]:
    """Get the holdings od the given account name.

    Args:
        name: The name of the account holder
    """
    return Account.get(name).holdings

@mcp.tool()
async def buy_shares(name: str, symbol: str, quantity: int, rationale: str) -> float:
    """Buy shares of a stock
    
    Args:
        name: The name of the account holder
        symbol: The symbol of the stock
        quantity: The quantity of shares to buy
        rationale: The rationale for the purchase and fit with the account's strategy    
    """
    return Account.get(name).buy_shares(symbol,quantity,rationale)

@mcp.tool()
async def sell_shares(name: str, symbol: str, quantity: int, rationale: str) -> float:
    """Sell shares of a stock
    
    Args:
        name: The name of the account holder
        symbol: The symbol of the stock
        quantity: The quantity of shares to sell
        rationale: The rationale for the sale and fit with the account's strategy    
    """
    return Account.get(name).sell_shares(symbol,quantity,rationale)

@mcp.tool()
async def change_strategy(name: str, strategy: str) -> str:
    """At your discretion, if you choose to, call this to change your investment strategy for the future
    
    Args:
        name: The name of the account holder
        strategy: The new strategy for the account
    """
    return Account.get(name).change_strategy(strategy)


## In the below code, "accounts/accounts_server" is just a scheme and a path. accounts_server has nothing to do
## with the MCP server name. The name part is an argument whose name must match the argument suppplied to the function
## it decorates. For instance, we could change "accounts/accounts_server" to "acc://acc_ser/{name}" Then the place from
## where this resource is called would have to use syntax like read_resource(f"acc://acc_ser/{name}"). 
##The scheme and path are just an agreed address. The server says "I answer requests for this address", and the client 
## says "I want what is at this address". 

@mcp.resource("accounts://accounts_server/{name}")
async def read_account_resource(name:str) -> str:
    account = Account.get(name.lower())
    return account.report()

@mcp.resource("accounts://strategy/{name}")
async def read_strategy_resource(name:str) -> str:
    account = Account.get(name.lower())
    return account.get_strategy()


if __name__ == "__main__":
    mcp.run(transport='stdio')