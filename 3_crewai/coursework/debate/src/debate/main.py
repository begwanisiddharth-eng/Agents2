#!/usr/bin/env python
import warnings
from debate.crew import Debate
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew.
    """
    Motion = input("Provide the topic for the motion")
    Inputs = {"motion": Motion}

    try:
        Debate().crew().kickoff(inputs=Inputs)
    except Exception as e:
        raise Exception(f"An error occured while running the crew: {e}")
