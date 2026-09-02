from dotenv import load_dotenv
from agents import Agent
from pydantic import BaseModel, Field

load_dotenv(override=True)
ModelName = "gpt-5.4-nano"
NumSearches = 5

class WebSearchItem(BaseModel):
    reason: str = Field(description="The reason why this search term is likely to yield results helpful in answering the user query")
    search_term: str = Field(description="The search term to use for web search")

class WebSearchPlan(BaseModel):
    searches: list[WebSearchItem] = Field(description="The list of web searches to be performed to answer the user query")

Instructions = f"""
               Given a query provided by the user, you come up with {NumSearches} search terms, each of which
               will be used to search the web to fetch information pertinent to answering the query. 
               Output {NumSearches} search terms.
               """

PlannerAgent = Agent(name="Planner Agent", instructions=Instructions, model=ModelName,
                          output_type=WebSearchPlan)