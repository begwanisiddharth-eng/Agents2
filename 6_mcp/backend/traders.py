from contextlib import AsyncExitStack
from .accounts_client import ReadAccountResource, ReadStrategyResource
from .tracers import MakeTraceId
from agents import Agent, Tool, Runner, trace
import json
from .templates import (
    ResearcherInstructions,
    TraderInstructions,
    TradeMessage,
    RebalanceMessage,
    ResearchTool
)

from .mcp_servers import TraderMCPServers, ResearcherMCPServers

MaxTurns = 30

async def GetResearcher(MCPServers,ModelName) -> Agent:
    Researcher = Agent(
        name="Researcher",
        instructions = ResearcherInstructions(),
        model = ModelName,
        mcp_servers = MCPServers
    )
    return Researcher


async def GetResearcherTool(MCPServers,ModelName) -> Tool:
    Researcher = await GetResearcher(MCPServers, ModelName)
    return Researcher.as_tool(tool_name="Researcher", tool_description=ResearchTool())

class Trader:

    def __init__(self, Name: str, LastName="Trader", ModelName="gpt-5.4-nano"):
        self.Name = Name
        self.LastName = LastName
        self.Agent = None
        self.ModelName = ModelName
        self.DoTrade = True

    async def CreateAgent(self,TraderMCPServers,ResearcherMCPServers) -> Agent:
        Tool = await GetResearcherTool(ResearcherMCPServers,self.ModelName)
        self.Agent = Agent(
            name = self.Name,
            instructions = TraderInstructions(self.Name),
            model =self.ModelName,
            tools = [Tool],
            mcp_servers = TraderMCPServers
        )
        return self.Agent

    async def GetAccountReport(self) -> str:
        AccountJSON = await ReadAccountResource(self.Name)
        AccountDict = json.loads(AccountJSON)
        AccountDict.pop("portfolio_value_time_series",None)
        ## AccountDict now holds the Account fields (name, balance, strategy, holdings, transactions) plus
        ## "total_portfolio_value" and "total_profit_loss". The time series is dropped because it grows on every
        ## Report() call, only the dashboard chart uses it, and it would otherwise be sent to the model as prompt text
        return json.dumps(AccountDict)

    async def RunAgent(self, TraderMCPServers, ResearcherMCPServers):
        self.Agent = await self.CreateAgent(TraderMCPServers, ResearcherMCPServers)
        AccountJSON = await self.GetAccountReport() ## This will be a string representation of a JSON object,
        ## and models are good at interpreting JSON
        AccountStrategy = await ReadStrategyResource(self.Name)
        Message = (
            TradeMessage(self.Name, AccountStrategy, AccountJSON) 
            if self.DoTrade
            else RebalanceMessage(self.Name, AccountStrategy, AccountJSON)
        )
        await Runner.run(self.Agent,Message,max_turns=MaxTurns)

    async def RunWithMCPServers(self):
        async with AsyncExitStack() as Stack:
            TraderServers = [await Stack.enter_async_context(Server) for Server in TraderMCPServers()]
            ResearcherServers = [await Stack.enter_async_context(Server) for Server in ResearcherMCPServers(self.Name)]
            await self.RunAgent(TraderServers,ResearcherServers)

    async def RunWithTrace(self):
        TraceName = f"{self.Name}-trading" if self.DoTrade else f"{self.Name}-rebalancing"
        TraceId = MakeTraceId(f"{self.Name.lower()}")
        with trace(TraceName, trace_id=TraceId):
            await self.RunWithMCPServers()

    async def Run(self):
        try:
            await self.RunWithTrace()
        except Exception as e:
            print (f"Error running trader {self.Name}: {e}")
        self.DoTrade = not self.DoTrade
