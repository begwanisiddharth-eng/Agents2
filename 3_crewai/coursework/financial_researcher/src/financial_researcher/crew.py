from crewai import Agent, Task, Process, Crew
from crewai.project import agent, task, CrewBase, crew
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import SerperDevTool

@CrewBase
class FinancialResearcher():
    """FinancialResearcher crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def researcher(self) -> Agent:
        return Agent(config=self.agents_config['researcher'], verbose=True, tools=[SerperDevTool()])

    @agent
    def analyst(self) -> Agent:
        return Agent(config=self.agents_config['analyst'], verbose=True)

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config['research_task'])

    @task
    def analysis_task(self) -> Task:
        return Task(config=self.tasks_config['analysis_task'])
    
    @crew
    def crew(self) -> Crew:
        """Creates the crew for financial research"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
