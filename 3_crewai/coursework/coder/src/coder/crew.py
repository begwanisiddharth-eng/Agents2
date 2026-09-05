from crewai import Agent, Task, Process, Crew
from crewai.project import agent, task, CrewBase, crew
from crewai.agents.agent_builder.base_agent import BaseAgent
from .tools.sandbox_tools import SandboxTools

@CrewBase
class Coder():
    """Coder crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def coder(self) -> Agent:
        return Agent(config=self.agents_config['coder'], verbose=True,
                    tools=SandboxTools)

    @task
    def coding_task(self) -> Task:
        return Task(config=self.tasks_config['coding_task'])

    @crew
    def crew(self) -> Crew:
        """Creates the Coder crew"""
        
        return Crew(agents=self.agents,tasks=self.tasks, process=Process.sequential,
                    tracing=True, verbose=True)
