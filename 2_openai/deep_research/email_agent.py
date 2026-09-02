from dotenv import load_dotenv
from agents import Agent, function_tool
from agents.model_settings import ModelSettings
import sendgrid
from sendgrid.helpers.mail import Email, Mail, To, Content
import os

load_dotenv(override=True)
ModelName = "gpt-5.4-nano"

@function_tool
def SendEmail(Subject: str, HTMLBody: str):
    """ Send an email to a prospective client """
    SG = sendgrid.SendGridAPIClient(api_key = os.getenv("SENDGRID_API_KEY"))
    FromEmail = Email("spraybubble@gmail.com")
    ToEmail = To("spraybubble@gmail.com")
    content = Content("text/html",HTMLBody)
    mail = Mail(FromEmail, ToEmail, Subject, content).get()
    SG.client.mail.send.post(request_body=mail)
    return {"Mail sent":"OK"}

Instructions = """
               You are en email sender. You are given a research report in markdown format.
               Follow the below steps:
               1. Convert the report into a neatly formatted HTML email
               2. Come up with an appropriate subject line for the email
               3. Use the SendEmail tool to send the email

               Do not finish until you have sent the email using the SendEmail tool
               """

EmailAgent = Agent(name="EmailAgent", instructions=Instructions, model=ModelName,
                        tools = [SendEmail], model_settings=ModelSettings(tool_choice="required"))