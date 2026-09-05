from crewai.tools import tool
import requests

@tool("Send Push Notification")
def SendPushNotification(message: str) -> str:
    """ Use this tool to send a push notification to the user.
    Args:
        message: The message to be sent as a push notification to the user
    Returns:
        A string indicating the status of the push notification
    """
    Topic = "ross919gain370"
    URL = f"https://ntfy.sh/{Topic}"
    Result = requests.post(URL, data=message.encode(encoding="utf-8")).status_code
    return f"Push notification sent with API response code: {Result}"
