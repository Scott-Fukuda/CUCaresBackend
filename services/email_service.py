## General emails (not carpool email)
from scheduler import schedule_form_email
from datetime import datetime, timedelta, timezone
import logging
import requests
import os

logger = logging.getLogger(__name__)

LATE_UNREGISTER_NOTIFY_HOURS = 7

MAILGUN_API_KEY = os.environ["MG_API_KEY"]
DOMAIN = "mg.campuscares.us"


def opportunity_date_as_utc(dt):
    """
    Normalize opportunity.date for comparisons and display.

    API-created rows store US/Eastern interpreted as UTC (see create_opportunity); the DB
    often returns naive datetimes for those UTC instants — treat naive as UTC, same as
    send_gcal_invite / add_email. If the value is timezone-aware, convert to UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=timezone.utc)

def add_email(opportunity):
    """Schedule email in redis"""
    event_dt = opportunity.date

    if event_dt.tzinfo is None:
        event_dt = event_dt.replace(tzinfo=timezone.utc)

    duration_minutes = opportunity.duration  
    end_dt = event_dt + timedelta(minutes=int(duration_minutes))

    try: 
        schedule_form_email(opportunity.id, end_dt)
    except Exception as e:
        print("Error:", e)

def send_approve_opp_email(host, opportunity):
    """Send direct email through mailgun"""
    try:
      admin_emails = ["ejm376@cornell.edu", "sdf72@cornell.edu", "lpb42@cornell.edu"]

      body, plain_body = create_approve_opp_email(host, opportunity)

      for email in admin_emails:
        response = requests.post(
            f"https://api.mailgun.net/v3/{DOMAIN}/messages",
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": f"CampusCares <postmaster@{DOMAIN}>",
                "to": email,
                "subject": "New Event Pending Your Approval",
                "text": plain_body,
                "html": body
            }
        )

        response.raise_for_status()
        result = response.json()
        
        print(f"[SUCCESS] Sent email to approve for for opportunity {opportunity.id}")
        
        return result

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to send approval email: {str(e)}")
        raise
        

def create_approve_opp_email(host, opportunity):
    plain_body = f"""Hi,

A new event, {opportunity.name}, has been submitted by {host.name} and is waiting for your approval.

Please log in to the admin page to review and approve or reject the event.

[Review Event →]
https://www.campuscares.us/admin

Thank you!
"""
    body = f"""
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
    <p>Hi,</p>

    <p>
      A new event, {opportunity.name}, has been submitted by {host.name} and is waiting for your approval.
    </p>

    <p>
      Please log in to the admin page to review and approve or reject the event.
    </p>

    <a href="https://www.campuscares.us/admin">
      <b>[Review Event →]</b>
    </a>

    <p>
      Thank you!
    </p>
  </body>
</html>
"""
    return body, plain_body


def should_notify_host_late_unregister(opportunity_date):
    """True if event has not started and begins within LATE_UNREGISTER_NOTIFY_HOURS."""
    start = opportunity_date_as_utc(opportunity_date)
    if start is None:
        return False
    now = datetime.now(timezone.utc)
    if now >= start:
        return False
    return (start - now) <= timedelta(hours=LATE_UNREGISTER_NOTIFY_HOURS)


def send_host_late_unregister_email(host, opportunity, volunteer_user):
    """Notify host via Mailgun that a volunteer unregistered close to event time."""
    body, plain_body = create_host_late_unregister_email(host, opportunity, volunteer_user)
    response = requests.post(
        f"https://api.mailgun.net/v3/{DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data={
            "from": f"CampusCares <postmaster@{DOMAIN}>",
            "to": host.email,
            "subject": f'Volunteer unregistered: "{opportunity.name}"',
            "text": plain_body,
            "html": body,
        },
    )
    response.raise_for_status()
    logger.info(
        "Sent late unregister notice to host for opportunity %s", opportunity.id
    )
    return response.json()


def create_host_late_unregister_email(host, opportunity, volunteer_user):
    start = opportunity_date_as_utc(opportunity.date)
    when = (
        start.strftime("%B %d, %Y at %H:%M UTC") if start else "(time unavailable)"
    )
    hn = (host.name or "").strip()
    host_greeting = hn.split()[0] if hn else "there"
    plain_body = f"""Hi {host_greeting},

{volunteer_user.name} ({volunteer_user.email}) has unregistered from your event "{opportunity.name}".

The event is scheduled for {when}.

Thank you,
CampusCares
"""
    body = f"""
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
    <p>Hi {host_greeting},</p>
    <p>
      <strong>{volunteer_user.name}</strong> ({volunteer_user.email}) has unregistered from your event
      <strong>{opportunity.name}</strong>.
    </p>
    <p>(This email was automatically sent because the user unregistered within {LATE_UNREGISTER_NOTIFY_HOURS} hours of the event start time.)</p>
    <p>Thank you,<br/>CampusCares</p>
  </body>
</html>
"""
    return body, plain_body


def create_feedback_email_body(user, opportunity):
    first_name = user.name.split(" ")[0]

    plain_body = f"""Hi {first_name},

Thank you so much for volunteering at {opportunity.name}! We truly appreciate the time, energy, and heart you put into serving.

To help us improve future events and better support our volunteers, we’d love for you to take a few minutes to complete a short feedback form. Your input makes a real difference.

Please fill it out here:
https://docs.google.com/forms/d/e/1FAIpQLSfzXwAYa8VTK74VoihBSf66rfEWMskYlBQeQ7UIUMKXPCxk7A/viewform

The form should only take about 3–5 minutes to complete. We’re grateful for your honest thoughts and suggestions.

Thank you again for being part of this event — we couldn’t have done it without you!

With appreciation,
CampusCares Team
""" 
    
    body = f"""
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
    
    <p>Hi {user.name},</p>

    <p>
      Thank you so much for volunteering at {opportunity.name}! We truly appreciate the time, energy, and heart you put into serving.
    </p>

    <p>
      To help us improve future events and better support our volunteers, we’d love for you to take a few minutes to complete a short feedback form. 
      Your input makes a real difference.
    </p>

    <p>
      Please fill it out here:<br>
      <a href="https://docs.google.com/forms/d/e/1FAIpQLSfzXwAYa8VTK74VoihBSf66rfEWMskYlBQeQ7UIUMKXPCxk7A/viewform">
        <b>Feedback Form</b>
      </a>
    </p>

    <p>
      The form should only take about 3–5 minutes to complete. We’re grateful for your honest thoughts and suggestions.
    </p>

    <p>
      Thank you again for being part of this event — we couldn’t have done it without you!
    </p>

    <p>
      With appreciation,<br>
      CampusCares Team
    </p>

  </body>
</html>
"""
    return body, plain_body