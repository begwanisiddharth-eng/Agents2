from crewai import Agent, Task, Process, Crew
from crewai.project import agent, task, crew, CrewBase
from crewai.agents.agent_builder.base_agent import BaseAgent
from .tools.sandbox_tools import SandboxTools

@CrewBase
class EngineeringTeam():
    """EngineeringTeam crew"""

    agents: list[BaseAgent]
    tasks: list[Task]
    
    @agent
    def engineering_lead(self) -> Agent:
        return Agent(config=self.agents_config['engineering_lead'], verbose=True,
                     mcps=["https://mcp.context7.com/mcp"])

    @agent
    def backend_engineer(self) -> Agent:
        return Agent(config=self.agents_config['backend_engineer'], verbose=True,
                     tools=SandboxTools)
    
    @agent
    def frontend_engineer(self) -> Agent:
        return Agent(config=self.agents_config['frontend_engineer'], verbose=True,
                     tools = SandboxTools, mcps=["https://mcp.context7.com/mcp"])

    @agent
    def test_engineer(self) -> Agent:
        return Agent(config=self.agents_config['test_engineer'], verbose=True, tools=SandboxTools)

    @task
    def design_task(self) -> Task:
        return Task(config=self.tasks_config['design_task'])

    @task
    def code_task(self) -> Task:
        return Task(config=self.tasks_config['code_task'])

    @task
    def frontend_task(self) -> Task:
        return Task(config=self.tasks_config['frontend_task'])

    @task
    def test_task(self) -> Task:
        return Task(config=self.tasks_config['test_task'])

    @crew
    def crew(self) -> Crew:
        """Creates the EngineeringTeam crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential,
                    tracing=True, verbose=True)
