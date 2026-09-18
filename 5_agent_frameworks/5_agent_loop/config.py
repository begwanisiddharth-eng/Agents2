""" The two models the agent loop uses, kept in one place so they are easy to use.
The orchestrator (Google ADK) authors the shared look and the hub page; the five
workers build the games.
"""

import os
ORCHESTRATOR_MODEL = os.environ.get("ORCHESTRATOR_MODEL", "gpt-5.4-nano")
WORKER_MODEL = os.environ.get("WORKER_MODEL", "gpt-5.4-mini")
