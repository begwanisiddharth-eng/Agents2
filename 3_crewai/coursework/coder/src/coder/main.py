#!/usr/bin/env python
import warnings
from coder.crew import Coder
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

Assignment = """
             Compute the sum of the first 100,000 terms of the series: 1-1/3+1/5-1/7+1/9+...
             Then multiply the sum calculated by 4.
             """

def run():
    """ Run the crew. """
    Inputs = {'assignment': Assignment}
    try:
        Coder().crew().kickoff(inputs=Inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")
