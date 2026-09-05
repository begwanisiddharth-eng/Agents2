#!/usr/bin/env python
import warnings
from datetime import datetime
from stock_picker.crew import StockPicker
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def run():
    """
    Run the crew.
    """
    Inputs = {
        'sector': 'FMCG',
        'current_date': datetime.now().strftime("%d-%b-%Y")
    }

    try:
        StockPicker().crew().kickoff(inputs=Inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")

