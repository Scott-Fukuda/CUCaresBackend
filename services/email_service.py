## General emails (not carpool email)
from scheduler import schedule_form_email
from datetime import timedelta, timezone
import pytz

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