from datetime import datetime, timedelta, timezone
import uuid
import requests
import os 

MAILGUN_DOMAIN = os.getenv("MG_DOMAIN")
MAILGUN_API_KEY = os.getenv("MG_API_KEY")

def generate_ics(
    event_title,
    start_dt,  # datetime (timezone-aware or naive UTC)
    end_dt,
    description,
    location,
    organizer_email,
    attendee_email
):
    uid = str(uuid.uuid4())

    def fmt(dt):
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//PPAC//Volunteer Events//EN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{fmt(datetime.now(timezone.utc))}
DTSTART:{fmt(start_dt)}
DTEND:{fmt(end_dt)}
SUMMARY:{event_title}
DESCRIPTION:{description}
LOCATION:{location}
ORGANIZER:mailto:{organizer_email}
ATTENDEE;CN=Volunteer;RSVP=TRUE:mailto:{attendee_email}
END:VEVENT
END:VCALENDAR
"""
    return ics

def send_calendar_invite(
    to_email,
    subject,
    body_text,
    ics_content
):
    return requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        files=[
            ("attachment", ("event.ics", ics_content, "text/calendar"))
        ],
        data={
            "from": "CampusCares <postmaster@mg.campuscares.us>",
            "to": [to_email],
            "subject": subject,
            "text": body_text,
        },
    )