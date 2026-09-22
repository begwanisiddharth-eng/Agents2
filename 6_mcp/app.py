import warnings
import gradio as gr
from demo.ui import CreateUI
from demo.util import css, js

## Gradio 6.14 reads a Starlette status constant that newer Starlette has renamed, so it warns on
## every request. We silence that upstream deprecation so that the dashboard console stays clean.

warnings.filterwarnings("ignore",message=".*HTTP_422_UNPROCESSABLE_ENTITY.*")

if __name__ == "__main__":
    UI = CreateUI()
    UI.launch(theme = gr.themes.Default(primary_hue="sky"),css=css, js=js, inbrowser=True)
