from openai import OpenAI
from context import TwinSystemPrompt
from tools import Tools, HandleToolCalls
from styles import CSS, JS, EXAMPLES
from dotenv import load_dotenv
import gradio as gr

load_dotenv(override=True)

ModelName = "gpt-5.4-mini"
openAI = OpenAI()

def Chat(Message, History):
    History = [{"role":h["role"], "content":h["content"]} for h in History]
    Messages = [{"role":"system", "content":TwinSystemPrompt}] + History + [{"role":"user", "content":Message}]
    Response = openAI.chat.completions.create(model=ModelName, messages=Messages, tools=Tools)

    while Response.choices[0].finish_reason == "tool_calls":
        Message = Response.choices[0].message
        Messages.append(Message)
        Results = HandleToolCalls(Message.tool_calls)
        Messages.extend(Results)
        Response = openAI.chat.completions.create(model=ModelName, messages=Messages, tools=Tools)
    return Response.choices[0].message.content


if __name__ == "__main__":
    gr.ChatInterface(
        fn=Chat,
        examples=EXAMPLES,
        title = "Digital Twin",
        description = "Talk to my AI twin about my professional experience",
        chatbot = gr.Chatbot(show_label=False)
    ).launch(css=CSS, js=JS, theme = gr.themes.Base())

