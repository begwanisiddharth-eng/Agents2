#!/usr/bin/env python
import warnings
from datetime import datetime
from financial_researcher.crew import FinancialResearcher

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def run():
    """Run the crew"""
    Inputs = {'company':'ITC Ltd.', 'current_date':datetime.now().strftime("%d-%b-%Y")}
    try:
        FinancialResearcher().crew().kickoff(inputs=Inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


