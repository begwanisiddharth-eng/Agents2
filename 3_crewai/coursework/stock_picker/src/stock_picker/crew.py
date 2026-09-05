from crewai import Agent, Task, Process, Crew
from crewai.project import task,agent, CrewBase, crew
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import SerperDevTool
from pydantic import BaseModel, Field
from .tools.push_tool import SendPushNotification


class TrendingCompany(BaseModel):
    """A company that is featuring prominently in the news"""
    name: str = Field(description="Name of the company")
    symbol: str = Field(description="Stock ticker symbol of the company")
    reason: str = Field(description="Reason for selecting the company")

class TrendingCompanyList(BaseModel):
    """A list of companies that are trending in the news"""
    companies: list[TrendingCompany] = Field(description="List of trending companies")

class TrendingCompanyResearch(BaseModel):
    """A comprehensive research undertaken on a company trending in the news"""
    name: str = Field(description="Name of the company")
    market_position: str = Field(description="Market strength and competitive analysis")
    growth_potential: str = Field(description="Future outlook and growth potential")
    investment_rationale: str = Field(description="Reason why this company makes for an attractive investment")

class TrendingCompanyResearchList(BaseModel):
    """A list of research reports on companies trending in the news"""
    research: list[TrendingCompanyResearch] = Field(description="List of research reports on trending companies")


@CrewBase
class StockPicker():
    """StockPicker crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def trending_company_finder(self) -> Agent:
        return Agent(config=self.agents_config['trending_company_finder'], tools=[SerperDevTool()], 
                     memory=True, verbose=True)

    @agent
    def financial_researcher(self) -> Agent:
        return Agent(config=self.agents_config['financial_researcher'], tools=[SerperDevTool()],verbose=True)

    @agent
    def stock_picker(self) -> Agent:
        return Agent(config=self.agents_config['stock_picker'], memory=True, tools=[SendPushNotification],
                     verbose=True)

    @task
    def find_trending_companies(self) -> Task:
        return Task(config=self.tasks_config['find_trending_companies'], output_pydantic=TrendingCompanyList)

    @task
    def research_trending_companies(self) -> Task:
        return Task(config=self.tasks_config['research_trending_companies'], output_pydantic=TrendingCompanyResearchList)

    @task
    def pick_best_company(self) -> Task:
        return Task(config=self.tasks_config['pick_best_company'])

    @crew
    def crew(self) -> Crew:
        """Creates the StockPicker crew"""

        manager = Agent(config = self.agents_config['manager'], allow_delegation=True)

        return Crew(
            agents=self.agents, tasks=self.tasks, process=Process.hierarchical,
            manager_agent = manager, verbose=True, tracing = True, memory = True
        )
