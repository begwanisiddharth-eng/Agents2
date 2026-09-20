from dotenv import load_dotenv
import requests
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

load_dotenv(override=True)

mcp = FastMCP("push_server")

class PushModelArgs(BaseModel):
    Message: str = Field(description="A brief message to push")

@mcp.tool()
def Push(args: PushModelArgs):
    """Send a push notification with this brief message"""
    Topic = "ross919gain370"
    URL = f"https://ntfy.sh/{Topic}"
    Result = requests.post(URL, data=args.Message.encode(encoding="utf-8"), timeout=10)
    return f"Push message sent with API status code: {Result.status_code}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
