import gradio as gr
from dotenv import load_dotenv
from research_manager import ResearchManager

load_dotenv(override=True)

async def run(Query: str):
    async for Chunk in ResearchManager().Run(Query):
        yield Chunk


with gr.Blocks() as UI:
    gr.Markdown("#Deep research agent")
    QueryTextbox = gr.Textbox(label="Enter your search query here", lines=3)
    RunButton = gr.Button("Run", variant="primary")
    Report = gr.Markdown(label="Report")

    QueryTextbox.submit(fn=run, inputs=QueryTextbox, outputs=Report)
    RunButton.click(fn=run, inputs=QueryTextbox, outputs=Report)

UI.launch(theme=gr.themes.Default(primary_hue="sky"), inbrowser=True)