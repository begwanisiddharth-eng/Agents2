import gradio as gr
from dotenv import load_dotenv
from research_manager import ResearchManager
from styles import CSS, JS, EXAMPLES, HEADER_HTML

load_dotenv(override=True)

async def run(Query: str):
    async for Chunk in ResearchManager().Run(Query):
        yield Chunk

with gr.Blocks(title="Deep Research") as UI:
    gr.HTML(HEADER_HTML)

    with gr.Row(elem_classes="dr-query-row"):
        QueryTextbox = gr.Textbox(
            placeholder = "Type a research question...",
            show_label = False,
            container = False,
            autofocus = True,
            elem_id = "dr-query",
            scale=5
        )
        RunButton = gr.Button("Investigate", variant="primary", elem_id="dr-run", scale=1)

    gr.HTML('<div class="dr-examples-labels">Try one</div>')
    gr.Examples(examples=EXAMPLES, inputs=QueryTextbox, elem_id="dr-examples")

    Report = gr.Markdown(elem_id="dr-report")

    QueryTextbox.submit(fn=run, inputs=QueryTextbox, outputs=Report)
    RunButton.click(fn=run, inputs=QueryTextbox, outputs=Report)


if __name__=="__main__":
    UI.launch(css=CSS, js=JS, theme=gr.themes.Base())
