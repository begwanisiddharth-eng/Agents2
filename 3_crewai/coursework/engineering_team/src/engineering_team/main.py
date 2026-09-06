import sys
import warnings

## Windows' console/file default encoding (cp1252) can't represent the emoji crewai
## writes to stdout/stderr in its own logging and tracing output, which crashes those
## writes. Forcing utf-8 on these streams fixes it without any global/env-var changes.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from engineering_team.crew import EngineeringTeam
import engineering_team.patch # noqa: F401 — applies CrewAI MCP monkey-patch on import
from .tools.sandbox_tools import ResetSandbox

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

Requirements = """
               A simple account management system that provides a simulation of a trading platform.
               The system should allow users to create an account, deposit funds or withdraw funds.
               The system should allow users to record that they have bought or sold shares, providing an amount.
               The system should calculate the total value of the user's portfolio, and the profit and loss from the initial deposit.
               The system should be able to report the holdings of the user at any point in time.
               The system should be able to report the profit and loss of the user at any point in time.
               The system should be able to list the transactions that the user has made over time.
               The system should prevent the user from withdrawing funds that will leave them with a negative balance. It should
               also prevent them from selling shares that they do not have, and prevent them from buying a quantity of a share that
               would leave them with a negative balance.
               Since this is a simulation, the system should have a function get_share_price(symbol) which returns the current
               price of a share - the symbol can be one of AAPL, TSLA or GOOGL and the function should return a fixed price for each symbol
               and this fixed price must be different for each of the 3 symbols.
               """
def run():
    """ Run the crew. """
    inputs = {'requirements': Requirements}

    try:
        ResetSandbox()
        EngineeringTeam().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")

