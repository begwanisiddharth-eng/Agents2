from agents import Runner, trace, gen_trace_id
from search_agent import SearchAgent
from planner_agent import PlannerAgent, WebSearchItem, WebSearchPlan
from writer_agent import ReportAgent, ReportData
from email_agent import EmailAgent
import asyncio
from dotenv import load_dotenv

load_dotenv(override=True)

class ResearchManager:

    async def PlanSearches(self, Query:str) -> WebSearchPlan:
        """Plan the searches to be performed for this query"""
        Result = await Runner.run(PlannerAgent,f"Query: {Query}")
        return Result.final_output

    async def PerformSearches(self, SearchPlan:WebSearchPlan) -> list[str]:
        """Call Search() once for every query in the Search Plan"""
        Tasks = [asyncio.create_task(self.Search(SearchItem)) for SearchItem in SearchPlan.searches]
        Results = await asyncio.gather(*Tasks)
        return Results

    async def Search(self, SearchItem:WebSearchItem) -> str:
        """Perform the web search for the search item and return the summarized results"""
        Input = f"Query: {SearchItem.search_term}\nReason for searching: {SearchItem.reason}"
        Result = await Runner.run(SearchAgent, Input)
        return Result.final_output

    async def WriteReport(self, Query: str, SearchResults: list[str]) -> ReportData:
        """Compile a comprehensive report from the summarized search results"""
        Input = f"Query: {Query}\n" + "List of search results\n\n"
        Input += "\n\n".join([f"#Search Result {Index}:\n{Result}" for Index,Result in enumerate(SearchResults,1)])
        Result = await Runner.run(ReportAgent, Input)
        return Result.final_output

    async def SendReportViaEmail(self, Report:ReportData) -> None:
        """Send the final report via email"""
        await Runner.run(EmailAgent, Report.markdown_report)

    async def Run(self, Query:str)-> str:
        """Run the deep research process, yielding the status updates and the final report"""
        TraceID = gen_trace_id()
        with trace("Research trace", trace_id=TraceID):
            yield f"Starting research. Trace: https://platform.openai.com/traces/trace?trace_id={TraceID}"
            SearchPlan = await self.PlanSearches(Query)
            yield f"Searches planned, starting {len(SearchPlan.searches)}"
            SearchResults = await self.PerformSearches(SearchPlan)
            yield "Searches complete, writing report..."
            Report = await self.WriteReport(Query,SearchResults)
            yield "Report written, sending email..."
            await self.SendReportViaEmail(Report)
            yield "Email sent, research complete..."
            yield Report.markdown_report

   
