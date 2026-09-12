"""The Sidekick: a create_agent worker wrapped in a homemade evaluator loop.

The worker is a single create_agent (Layer 3). Around it we run our own loop that checks
the worker's answer against the user's success criteria, and either accepts it, sends it
back for another attempt, or returns to the user with a question. Middleware gives the
worker a plan it shares with the UI, guardrails for PII and runaway costs, and a pause
for human approval before sensitive actions.

Big picture of the moving parts:
    - 'worker': a LangChain `create_agent` - the LLM + tools + a ReAct-style loop
                that decides which tools to call and produces a reply
    - 'evaluator': a second, separate LLM call that grades the worker's reply against
                   the user's success criteria
    - The Sidekick class glues the 'worker' and 'evaluator' into a retry loop (`_advance`),
      and also exposes `resume()` so a paused worker (waiting for human approval
      for a sensitive tool call) can be continued from outside
"""

import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents. middleware import (
    AgentMiddleware,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    PIIMiddleware,
    TodoListMiddleware
)

from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from sidekick_tools import GetAllTools

load_dotenv(override=True)
CurrentPath = os.path.dirname(os.path.abspath(__file__))
Sandbox = os.path.join(CurrentPath, "sandbox")
MaxAttempts = 3 # Cap on worker attempts / evaluator feedback cycles per turn

class EvaluatorOutput(BaseModel):
    feedback: str = Field(description="Feedback on the assistant's response")
    success_criteria_met: bool = Field(description="Whether the success criteria have been met")
    user_input_needed: bool = Field(
        description = "True if the assistant has a question, needs clarificattion, or is stuck and needs user input"
    )

WorkerPrompt = """You are Sidekick, a capable personal assistant who completes tasks for the user.
You have a real web browser, a sandbox filesystem, web search, Wikipedia and the ability to send push
notifications. When you use the browser, navigate to a page and read it with a snapshot rather than clicking
around unnecessarily. Dismiss cookie banners and popups yourself by clicking in the browser. If you reach
something only a human can do, like logging in, entering a captcha or two-factor authentication, use the
RequestHumanHelp tool to inform the user exactly what to do in the browser window, then carry on once they have
done it.
For flight searches, use Google Flights in your browser: go straight to https://www.google.com/travel/flights?q=...
with a natural language query like "Flights from New York to London leaving 14 July and returning 21 July".

Keep working on the task until the success criteria are met, or you genuinely need to ask the user a question. If
you have a question, ask it plainly.
When you are finished with the task, give your final answer clearly, saying what you activities you performed in a
succinct manner, what was generated and what were your findings and conclusion.
"""

class TolerateToolErrors(AgentMiddleware):
    """Hand tool errors back to the agent as a message so that it can recover, rather than
    crashing the run. Tools that invoke anything external to the system like a browser, can often
    fail once or twice before succeeding"""

    async def awrap_tool_call(self,Request, Handler):
        #'awrap_tool_call() is a middleware hook that LangChain's agent runtime wraps
        # around every tool call. Handler(Request) is what calls the tool. Any errors
        # are captured here itself and a ToolMessage is generated describing the error
        # and sending it back to the calling point, from where it can be decided whether
        # to retry the tool call, use a different tool, or explain the failure to the user.
        # This approach prevents the whole process from crashing because a particular tool
        # call failed
        try:
            return await Handler(Request)
        except Exception as Error:
            return ToolMessage(content=f"That tool raised an error {Error}. Please try another approach",
                               tool_call_id=Request.tool_call["id"])


class Sidekick:
    def __init__(self):
        self.sidekick_id = str(uuid.uuid4())
        ## A unique ID for this Sidekick instance. It also serves as the LangGraph's checkpointer thread_id
        self.Memory = InMemorySaver()
        ## LangGraph's checkpointer. It stores the worker agent's full state (Messages, Todos,
        ## in-flight interrupts) in memory and is keyed by thread_id. This means a paused run 
        ## can be resumed later on, exactly where it left off, and multi-turn conversations keep their history
        self.Tools = None
        self.Sessions = None
        self.Worker = None
        self.Evaluator = None
        self.Task = ""
        ## The current turn's raw user message, remembered for evaluate()
        self.SuccessCriteria = ""
        ## The current turn's success criteria text
        self.Attempts = 0
        ## How many worker calls have been made in this turn
        self.Paused = False
        ## True while the worker is stopped waiting for human approval
        self.PendingActions = 0
        ## How many tool calls are awaiting approval when paused
        self.Todos = []
        ## The worker's self-authored Todo list, used by the UI

    async def Setup(self):
        os.makedirs(Sandbox, exist_ok=True)
        self.Tools, self.Sessions = await GetAllTools(Sandbox)
        self.Worker = create_agent(
            model="gpt-5.4-nano",
            tools=self.Tools,
            system_prompt=f"{WorkerPrompt}\nToday is {datetime.now():%A %d %B %Y}",
            middleware = [
                ## Order matters for the listing of the middleware
                TolerateToolErrors(),
                TodoListMiddleware(),
                ## Gives the agent a 'write/update a todo list' ability. The list
                ## it maintains shows up in the state's "todos" key, which _advance()
                ## reads at every step so that the UI can display the agent's live plan
                PIIMiddleware("email"),
                ## Scans messages for PII and redacts emails it finds so that raw email
                ## addresses do not form part of the conversation state or get echoed
                ## back unnecessarily
                PIIMiddleware("credit_card", apply_to_tool_results=True),
                ## To prevent tools from capturing credit card numbers, for instance, while
                ## while scraping a web page
                ModelCallLimitMiddleware(run_limit=5),
                ## The underlying model cannot be called more than 5 times in one run
                HumanInTheLoopMiddleware(
                    interrupt_on={"SendPushNotification":True, "RequestHumanHelp":True}
                )
                ## Human-in-the-loop-gate: Whenever the agent tries to call either 
                ## SendPushNotification or RequestHumanHelp, the graph run is paused instead
                ## of the tool being called. The pause surfaces as result["__interrupt__"] in
                ## _advance() below, and the run only continues when resume() is called with
                ## an approval. This applies only to these two tools
            ],
            checkpointer = self.Memory
        )
        self.Evaluator = ChatOpenAI(model="gpt-5.4-nano").with_structured_output(EvaluatorOutput)

    async def Evaluate(self, Message:str, SuccessCriteria: str, LastReply: str, ToolsUsed: list[str]) -> EvaluatorOutput:
        """Ask the Evaluator LLM to grade one worker attempt"""
        ## The Evaluator only sees the original user message, the list of tools used (as a proxy
        ## for what the worker agent really did, "to check against hallucinations"), the success
        ## criteria, and the worker's latest reply. It does not see the history of the 
        ## conversation, or the worker's internal reasoning. This LLM call is cheap and focused
        Prompt = f"""
                 You decide whether an assistant has met the success criteria for a task.
                 The user's request was:
                 {Message}
                 The success criteria are:
                 {SuccessCriteria}
                 The tools the assistant used while working are (in order):
                 {", ".join(ToolsUsed) or "none"}
                 The assistant's most recent reply was:
                 {LastReply}

                 Decide whether the success criteria are met, using the tool calls as evidence of what was
                 actually done. Also decide whether the assistant needs more input from the user, either
                 because it asked a question, needs clarification, or seems stuck. Give brief, concrete
                 feedback.
                 """
        return await self.Evaluator.ainvoke(Prompt)

    async def RunTurn(self, Message: str, SuccessCriteria: str, History: list) -> list:
        """One turn of conversation: the worker attempts the task and the evaluator checks it,
        retrying with feedback up to MaxAttempts. If the worker pauses for approval, this
        function returns straightaway with paused set, and resume() continues the same turn.
        """
        ## Remember this turn's inputs in instance fields so that they do not need to be 
        ## passed around between functions
        self.Task = Message
        self.SuccessCriteria = SuccessCriteria or "The answer should be clear, concide and complete"
        self.Attempts = 0
        self.Todos = []
        ## The very first message sent to the worker graph. LangGraph agents take a "messages" list
        ## which is a list of dictionaries. The success criteria are baked into the user message
        Messages = [{"role":"user", "content":f"{Message}\n\n The success criteria for this task are {self.SuccessCriteria}"}]
        Payload = {"messages":Messages}
        ## History in the below call is for the UI transcript
        return await self._advance(Payload, History + [{"role":"user", "content":Message}])

    async def Resume(self, History: list) -> list:
        """Approve the actions the worker paused on, and resume the turn"""
        ## Command(resume=) is LangGraph's way of feeding a value into a graph that is currently
        ## suspended at an interrupt point. HumanInTheLoopMiddleware expects a list of one 
        ## decision per pending tool call. In this implementation, every pending action is approved
        Payload = Command(resume={"decisions": [{"type":"approve"}]*self.PendingActions})
        
        return await self._advance(Payload, History)
        ## The Resume() function's playload only needs to carry the answer to the pending interrupt (
        ## the approval decisions). When _advance() is called, the thread_id in config is what tells
        ## LangGraph which checkpointed state - including the complete message history - to resume into

    async def _advance(self, Payload, History: list) -> list:
        """
        User submits message
              │
              ▼
        run_turn()  -- builds the first payload, calls _advance(payload, history)
              │
              ▼
        _advance()  -- while True loop:
              │           1. streams the worker graph forward
              │           2. checks result for "__interrupt__"
              │
              +-- interrupt found --> sets self.paused=True, self.pending_actions=N,
              │                       RETURNS immediately (does not evaluate)
              │                              │
              │                              ▼
              │                    UI shows "waiting for approval", approve button appears
              │                              │
              │                              ▼
              │                    User clicks approve --> resume() called
              │                              │
              │                              ▼
              │                    resume() builds a Command(resume=...) payload,
              │                    calls _advance(payload, history) again
              │                              │
              │                              +--> back into the SAME while-loop above
              │
              +-- no interrupt --> self.paused=False, grabs reply + tools_used,
                                    calls evaluate() (a separate LLM grading call)
                                           │
                                           ▼
                           verdict good / needs user / attempts maxed?
                                │                              │
                               yes                             no
                                │                              │
                                ▼                              ▼
                      RETURN final reply          build "retry with feedback" payload,
                      to run_turn()/resume()      loop back to top of while-loop
                      caller (the UI)             (stays inside _advance, no return
                                                   to run_turn/resume yet)
        """
        Config = {"configurable": {"thread_id":self.sidekick_id}}
        while True:
            Result = None
            ## stream_mode="values" returns the entire graph state after each step (and not just the delta),
            ## so Result after the loop holds the final graph state after it stops advancing (because it
            ## finished, or hit an interrupt)
            async for Result in self.Worker.astream(Payload, config=Config, stream_mode="values"):
                ## Extract the Todo list to show a live plan of what the agent is doing
                ## at every step, rather than just at the end
                self.Todos = Result.get("todos", self.Todos)
            if "__interrupt__" in Result:
                ## Result has six keys in general (messages, jump_to, structured_response, todos,
                ## thread_model_call_count, run_model_call_count). When the agent is paused, LangGraph
                ## injects a seventh key "__interrupt__"
                Actions = Result["__interrupt__"][0].value["action_requests"]
                self.Paused = True
                self.PendingActions = len(Actions)
                Described = "\n".join(Action["description"] for Action in Actions)
                ## Return immediately without invoking the evaluator. The UI would display the message,
                ## get user approval and then call Resume
                return History + [{"role":"assistant", "content": f"Waiting for your approval: \n{Described}"}]

            ## No interrupt. The worker has run to completion
            self.Paused = False
            Reply = Result["messages"][-1].content
            ToolsUsed = [
                Call['name'] for m in Result["messages"] for Call in (getattr(m,"tool_calls",[]) or [])
            ]
            self.Attempts +=1
            Verdict = await self.Evaluate(self.Task, self.SuccessCriteria,Reply,ToolsUsed)
            if Verdict.success_criteria_met or Verdict.user_input_needed or self.Attempts >= MaxAttempts:
                return History + [
                    {"role":"assistant", "content":Reply},
                    {"role":"assistant", "content": f"Evaluator: {Verdict.feedback}"}
                ]
            Payload = {
                "messages": [
                    {
                        "role":"user",
                        "content": f"Your last response {Reply} was judged by the evaluator as not meeting the success criteria"+
                                   f" The evaluator feedback was {Verdict.feedback}" + 
                                   f" Please try again. If you are stuck or need user input, please say so"
                    }
                ]
            }
            
    def Cleanup(self):
        """Shut down the MCP servers; the browser windows closes"""
        if self.Sessions:
            self.Sessions.stop()
