from __future__ import print_function
import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from livekit.agents import function_tool, Agent, RunContext

# Scopes بتدي صلاحيات للـ API
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def main():
    creds = None
    # لو فيه token محفوظ قبل كده
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)

    # نضيف اجتماع تجريبي دلوقتي
    start = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat() + "Z"
    end = (datetime.datetime.utcnow() + datetime.timedelta(hours=2)).isoformat() + "Z"

    event = {
        "summary": "Meeting Test",
        "location": "Online",
        "description": "Testing Google Calendar API integration",
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
    }

    created_event = service.events().insert(calendarId="primary", body=event).execute()
    print("✅ Event created:", created_event.get("htmlLink"))


@function_tool()
def add_event_to_calendar(title, description, start_time, end_time, timezone="Africa/Cairo"):
    """
    Adds a new event to the user's Google Calendar.

    Input Parameters:
        - title (string, required): The title of the event (e.g., "Team Meeting").
        - description (string, optional): Additional details about the event 
          (e.g., "Discuss project roadmap").
        - start_time (string, required): Start time of the event in ISO 8601 format 
          (e.g., "2025-08-23T15:00:00").
        - end_time (string, required): End time of the event in ISO 8601 format 
          (e.g., "2025-08-23T16:00:00").
        - timezone (string, optional, default="Africa/Cairo"): Timezone of the event 
          (e.g., "UTC", "America/New_York").

    Output:
        - (string): A Google Calendar event link (htmlLink) that allows the user to 
          view the created event directly.
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import os

    SCOPES = ["https://www.googleapis.com/auth/calendar"]

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_time, "timeZone": timezone},
        "end": {"dateTime": end_time, "timeZone": timezone},
    }

    created_event = service.events().insert(calendarId="primary", body=event).execute()
    return created_event.get("htmlLink")



if __name__ == "__main__":
    add_event_to_calendar("Test Meeting", "This is a test event", "2024-06-30T10:00:00+02:00", "2024-06-30T11:00:00+02:00")
