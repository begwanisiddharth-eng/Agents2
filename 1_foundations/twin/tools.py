import json
# import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

## NTFY setup
Topic = "ross919gain370"
URL = f"https://ntfy.sh/{Topic}"


# pushover_user = os.getenv("PUSHOVER_USER")
# pushover_token = os.getenv("PUSHOVER_TOKEN")
# pushover_url = "https://api.pushover.net/1/messages.json"


def Push(Message):
    print (f"Push: {Message}")
    requests.post(URL, data=Message.encode(encoding="utf-8"))


def RecordUserDetails(Email, Name="Name not provided", Notes="Not provided"):
    Push(f"Recording interest from {Name} with email {Email} and notes {Notes}")
    return {"recorded":"OK"}

def RecordUnknownQuestion(Question):
    Push(f"Recording {Question} asked that I couldn't answer")
    return {"recorded":"OK"}


RecordUserDetailsJSON = {
    "name": "RecordUserDetails",
    "description": "Record that the user is interested in being in touch and provided an email address",
    "parameters": {
        "type":"object",
        "properties": {
            "Email": {"type":"string", "description":"The email address of the user"},
            "Name": {"type":"string", "description": "The name of the user, if provided"},
            "Notes": {"type": "string", "description":"Any additional information about the user \
                                        that may be helpful, if provided"}
        },
        "required": ["Email"],
        "additionalProperties": False
    }
}

RecordUnknownQuestionJSON = {
    "name": "RecordUnknownQuestion",
    "description": "Record a question that you could not answer",
    "parameters": {
        "type":"object",
        "properties": {
            "Question": {"type":"string", "description": "The question that could not be answered"}
        },
        "required": ["Question"],
        "additionalProperties": False
    }
}

Tools = [{'type':"function", "function":RecordUserDetailsJSON},
         {"type":"function", "function":RecordUnknownQuestionJSON}]

ToolMap = {
    "RecordUserDetails": RecordUserDetails,
    "RecordUnknownQuestion": RecordUnknownQuestion
}

def HandleToolCalls(ToolCalls):
    Results = []
    for ToolCall in ToolCalls:
        ToolName = ToolCall.function.name
        Arguments = json.loads(ToolCall.function.arguments)
        print (f"Tool called: {ToolName}", flush=True)
        Tool = ToolMap.get(ToolName)
        Result = Tool(**Arguments) if Tool else "Unknown tool: "+ ToolName
        Results.append({"role":"tool", "content":json.dumps(Result), "tool_call_id":ToolCall.id})
    return Results
