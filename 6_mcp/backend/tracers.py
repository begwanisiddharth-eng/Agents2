"""tracers.py records what each trader's agent is doing into the logs table in SQLite. 
That table feeds the log panel on the dashboard.

- MakeTraceId(tag) builds a trace ID like trace_warren0k3f9…, always 32 characters after trace_.
That length is the ID format the Agents SDK expects. It puts the trader's name first, then a 0 as a separator, 
then random padding. The point is to carry the trader's name inside the ID.

- LogTracer is a TracingProcessor. The SDK calls its hooks whenever a trace or a span starts or ends. 
A span is one step of the run: an agent turn, an LLM generation, a tool call, a tool-list fetch. In each hook it:

    1. Calls GetName to pull the trader's name back out of the trace ID, taking everything before the first 0. 
       Traces without our ID format return None and are ignored.
    2. Calls WriteLog(name, type, message), with messages like "Started function BuyShares" or "Ended generation".
"""


from agents import TracingProcessor, Trace, Span
from .database import WriteLog
import secrets
import string

ALPHANUM = string.ascii_lowercase + string.digits

def MakeTraceId(Tag: str) -> str:
    """
    Return a string of the form 'trace_<tag><random>'
    where the total length after 'trace_' is 32 chars
    """
    Tag += "0"
    PadLength = 32 - len(Tag)
    RandomSuffix = ''.join(secrets.choice(ALPHANUM) for _ in range(PadLength))
    return f"trace_{Tag}{RandomSuffix}"

class LogTracer(TracingProcessor):

    def GetName(self,TraceOrSpan: Trace | Span) -> str | None:
        TraceId = TraceOrSpan.trace_id
        Name = TraceId.split("_")[1]
        if "0" in Name:
            return Name.split("0")[0]
        else:
            return None

    def on_trace_start(self, Trace) -> None:
        Name = self.GetName(Trace)
        if Name:
            WriteLog(Name, "trace", f"Started: {Trace.name}")

    def on_trace_end(self,Trace) -> None:
        Name = self.GetName(Trace)
        if Name:
            WriteLog(Name,"trace", f"Ended: {Trace.name}")

    def on_span_start(self, Span) -> None:
        Name = self.GetName(Span)
        ## Span.span_data.type is the kind of step: agent, function (a tool call), generation, response, mcp_tools, and so on 
        Type = Span.span_data.type if Span.span_data else "span"
        if Name:
            Message = "Started"
            if Span.span_data:
                if Span.span_data.type:
                    Message += f" {Span.span_data.type}"
                if hasattr(Span.span_data,"name") and Span.span_data.name:
                    Message += f" {Span.span_data.name}"
                if hasattr(Span.span_data, "server") and Span.span_data.server:
                    Message += f" {Span.span_data.server}"
            if Span.error:
                Message += f" {Span.error}"
            WriteLog(Name,Type,Message)

    def on_span_end(self,Span) -> None:
        Name = self.GetName(Span)
        Type = Span.span_data.type if Span.span_data else "span"
        if Name:
            Message = "Ended"
            if Span.span_data:
                if Span.span_data.type:
                    Message += f" {Span.span_data.type}"
                if hasattr(Span.span_data, "name") and Span.span_data.name:
                    Message += f" {Span.span_data.name}"
                if hasattr(Span.span_data, "server") and Span.span_data.server:
                    Message += f" {Span.span_data.server}"
            if Span.error:
                Message += f" {Span.error}"
            WriteLog(Name,Type, Message)

    def force_flush(self) -> None:
        pass

    def shutdown(self) -> None:
        pass