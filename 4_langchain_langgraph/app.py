"""Gradio app for the Sidekick. Run with: uv run app.py"""

import html
import gradio as gr
import styles
from sidekick import Sidekick

LAUNCH_STYLE = {"theme": styles.THEME, "css": styles.CSS, "head": styles.JS}

## Raw HTML rendered once at the top of the page via `gr.HTML(HEADER)`. This is
## just static branding, not tied to any Sidekick state.
HEADER = """
<div id="header">
    <div class="context-label">Your personal co-worker</div>
    <h1>Sidekick</h1>
    <div class="brand-bar"></div>
</div>
"""

def RenderTodos(Todos):
    """Turn the Sidekick's list of Todo dicts into HTML shown in the Plan panel"""
    if not Todos:
        ## This condition will arise at initial loading of the UI or after a reset
        Items = '<div class="placeholder">The Sidekick will write its plan here as it works</div>'
    else:
        ## Each dict in sidekick.Todos list has exactly two keys: `content', which is the todo's text
        ## written by the agent and can contain characters from a sraped web page and hence is run
        ## through html.escape, and `status`, which can take exactly one of three string values, 
        ## "pending", "in-progress" or "completed"
        Items = "<ul>" + "".join(
            f'<li class="{Todo["status"]}"><span class="mark"></span>{html.escape(Todo["content"])}</li>'
             for Todo in Todos
        ) + "</ul>"
    return f"<h3>Plan</h3>{Items}"


def WatchTodos(sidekick):
    """ This is called by the timer once every second. The timer is exclusively responsible
    for updating the plan panel. This is because if any long-running event owned the panel, live
    updates would not render. This is because Gradio locks an event's declared outputs while the 
    event is still running"""
    return RenderTodos(sidekick.Todos) if sidekick else RenderTodos([])



async def Setup():
    sidekick = Sidekick()
    await sidekick.Setup()
    return sidekick, gr.update(interactive=True)

async def ProcessMessage(sidekick,Message,SuccessCriteria,History):
    if sidekick is None: ## The user clicked before Setup launched the MCP servers
        return History, gr.update(visible=False), sidekick
    Result = await sidekick.RunTurn(Message, SuccessCriteria, History)
    return Result, gr.update(visible=sidekick.Paused), sidekick

async def Approve(sidekick,History):
    Result = await sidekick.Resume(History)
    return Result, gr.update(visible=sidekick.Paused), sidekick


async def Reset(sidekick):
    if sidekick:
        sidekick.Cleanup()
    NewSidekick = Sidekick()
    await NewSidekick.Setup()
    return "", "", None, gr.update(visible=False), NewSidekick


def FreeResources(sidekick):
    if sidekick:
        sidekick.Cleanup()


with gr.Blocks(title="Sidekick") as UI:
    gr.HTML(HEADER)
    ## gr.State is a special Gradio component that is not rendered on the page at all.
    ## It just holds an arbitrary Python object, (in this case the per-session Sidekick
    ## instance), alive across callbacks for as long as this browser tab's session lasts.
    ## The delete_callback argument specifies what function to run when the session ends
    sidekick = gr.State(delete_callback=FreeResources)

    with gr.Row():
        Chatbot = gr.Chatbot(label="Sidekick", height=320, scale=3, elem_id="chat")
        with gr.Column(scale=1):
            ## The live "Plan" panel, kept up to date by WatchTodos() via a timer.
            ## This not updated by any button/textbox event
            TodosPanel = gr.HTML(RenderTodos([]), elem_id="plan-panel")
    with gr.Group(elem_id="ask-panel"):
        with gr.Row():
            Message = gr.Textbox(show_label=False, placeholder="Your request to the sidekick")
        with gr.Row():
            SuccessCriteria = gr.Textbox(show_label=False,placeholder="What are your success criteria?")
    with gr.Row():
        ResetButton = gr.Button("Reset", elem_id="reset-button")
        ## The Approve button is hidden by default; and is only shown when a human-in-the-loop
        ## approval is required (see process_message/approve above, and sidekick.Paused=True)
        ApproveButton = gr.Button("Approve and continue", visible=False, elem_id="approve-button")
        ## This is disabled till Setup() brings up the MCP servers, so that the user cannot
        ## start a turn before the servers actually exist
        GoButton = gr.Button("Go!", elem_id="go-button", interactive=False)
    
    Timer = gr.Timer(1)
    ## The timer fires WatchTodos() once every second for the lifetime of the page,
    ## purely to keep the plan panel live. 

    UI.load(Setup, [], [sidekick, GoButton])
    Timer.tick(WatchTodos, [sidekick], [TodosPanel], show_progress="hidden")
    Message.submit(ProcessMessage, [sidekick, Message, SuccessCriteria, Chatbot],
                                   [Chatbot,ApproveButton,sidekick])
    SuccessCriteria.submit(ProcessMessage, [sidekick,Message,SuccessCriteria,Chatbot],
                                           [Chatbot,ApproveButton, sidekick])
    GoButton.click(ProcessMessage, [sidekick, Message, SuccessCriteria, Chatbot],
                                   [Chatbot, ApproveButton, sidekick])
    ApproveButton.click(Approve, [sidekick, Chatbot], [Chatbot,ApproveButton,sidekick])
    ResetButton.click(Reset, [sidekick], [Message, SuccessCriteria, Chatbot, ApproveButton, sidekick])

if __name__ == "__main__":
    UI.launch(inbrowser=True, **LAUNCH_STYLE)

