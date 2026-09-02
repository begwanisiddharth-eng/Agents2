import os
from tavily import TavilyClient
from agents import Agent, function_tool
from agents.model_settings import ModelSettings
from dotenv import load_dotenv

load_dotenv(override=True)
ModelName = "gpt-5.4-nano"
NumSearches = 5

TavilyClient = TavilyClient(api_key = os.getenv("TAVILY_API_KEY"))

@function_tool
async def TavilySearch(SearchTerm: str) -> str:
    """ You search the web given a search term and return the results """
    Results = TavilyClient.search(SearchTerm, search_depth="advanced", max_results=NumSearches)
    SearchResults = Results.get("results", [])
    ## Format the search results
    FormattedResults = "\n\n".join([f"Title: {r['title']}\nURL: r['url]\nContent:{r['content']}" for r in SearchResults])
    if FormattedResults is not None:
        return FormattedResults
    else:
        return "No results found"

Instructions = """
               You specialize in web search. You are given a search term, and you must use 
               your TavilySearch tool to search the web for that term and return return the
               summarized result. The TavilySearch tool will give you 5 results for each search
               term. You must summarize these results. Aim for no more than 500-600 words of
               content. Your output will be used by a research assistant to draft a report, so
               it is important to be concise and include important points only. There is no
               need to focus heavily on grammar and producing complete sentence.
               Do not finish till you have produced the summarized result. You must only
               use the results returned by the TavilySearch tool to generate the summary.
               """

SearchAgent = Agent(name="Search Agent", instructions=Instructions, model=ModelName,
                        tools = [TavilySearch], model_settings=ModelSettings(tool_choice="required"))