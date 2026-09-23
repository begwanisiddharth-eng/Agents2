from .traders import Trader
from typing import List
import asyncio
from .tracers import LogTracer
from agents import add_trace_processor
from .market import IsMarketOpen
from dotenv import load_dotenv
import os

load_dotenv(override=True)

RUN_EVERY_N_MINUTES = float(os.getenv("RUN_EVERY_N_MINUTES","60"))
## float, not int: 90s = 1.5 minutes needs a fractional value, which int() cannot parse
RUN_EVEN_WHEN_MARKET_IS_CLOSED = (os.getenv("RUN_EVEN_WHEN_MARKET_IS_CLOSED", "false").strip().lower() == "true")
## USE_MANY_MODELS = os.getenv("USE_MANY_MODELS","false").strip().lower() == "true"
STAGGER_SECONDS = 120 ## Starting the traders together creates a rate limit error for OpenAI API; 
## each trader starts 2 minutes after the previous one

Names = ["Prashant","Rakesh","Madhu"]
LastNames = ["Patience", "Bold", "Systematic"]

ModelNames = ["gpt-5.4-nano"] * 3
ShortModelNames = ["GPT 5.4 Nano"] * 3

def CreateTraders() -> List[Trader]:
    Traders = []
    for Name, LastName, ModelName in zip(Names,LastNames,ModelNames):
        Traders.append(Trader(Name,LastName,ModelName))
    return Traders

async def RunEveryNMinutes():
    add_trace_processor(LogTracer())
    Traders = CreateTraders()
    while True:
        if RUN_EVEN_WHEN_MARKET_IS_CLOSED or IsMarketOpen():
            Tasks = []
            for Index, Trader in enumerate(Traders):
                if Index > 0:
                    await asyncio.sleep(STAGGER_SECONDS)
                Tasks.append(asyncio.create_task(Trader.Run()))
            await asyncio.gather(*Tasks)
        else:
            print ("Market is closed. Skipping run")
        await asyncio.sleep(RUN_EVERY_N_MINUTES*60)

if __name__ == "__main__":
    print (f"Starting scheduler to run every {RUN_EVERY_N_MINUTES} minutes")
    asyncio.run(RunEveryNMinutes())
