from .celery_app import celery
import requests
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
from collections import defaultdict
import os
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# sys.path.append("/app")

load_dotenv()

MAILGUN_API_KEY = os.getenv("MG_API_KEY")
DOMAIN = "mg.campuscares.us"

def format_datetime(dt_input):
    """
    Format a datetime from the database (assume UTC) to US/Eastern local time.
    """
    if isinstance(dt_input, str):
        dt = datetime.strptime(dt_input, '%Y-%m-%d %H:%M:%S')
        dt = dt.replace(tzinfo=pytz.UTC)  # mark it as UTC
    else:
        dt = dt_input

    eastern = pytz.timezone("US/Eastern")
    dt_display = dt.astimezone(eastern)  # converts correctly with DST

    short_format = dt_display.strftime('%-m/%-d/%y')  
    formal_format = dt_display.strftime('%B %-d, %Y, %-I:%M %p')  

    return {
        'short': short_format,
        'formal': formal_format,
        'datetime': dt_display.isoformat()
    }

def create_driver_email_body(ride, riders, opportunity, time_data):
    plain_body = f"""Hi {ride.driver.name},
    """
    body = f"""<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
<p>Hi {rider.driver.name},</p>
"""
    
    if not riders:
        plain_body += f"""
Thank you for signing up to volunteer for the upcoming CampusCares event, {opportunity.name}!

At this time, no volunteers signed up for your ride, so it will not be needed for this event.

Thank you for being willing to drive and support our volunteers. We appreciate your time and generosity.

Best regards,
CampusCares Team
"""
        body += f"""
    <p>Thank you for signing up to volunteer for the upcoming CampusCares event, {opportunity.name}!</p>
    <p>At this time, no volunteers signed up for your ride, so it will not be needed for this event.</p>
    <p>Thank you for being willing to drive and support our volunteers. We appreciate your time and generosity.</p>
<p>
    Best regards,<br>
    The CampusCares Team
</p>
</body>

</html>
"""
        
    else: 
        plain_body += f"""
Thank you for volunteering to drive for the upcoming CampusCares event! Here are the details for your carpool:

⭐️ RIDERS YOU'RE PICKING UP
"""

        riders_by_location = defaultdict(list)
        numbers = []
        for r in riders:
            riders_by_location[r.pickup_location].append({
                'name': r.user.name,
                'notes': r.notes,
                'phone': r.user.phone
            })
            numbers.append(r.user.phone)

        for location, rider_list in riders_by_location.items():
            plain_body += "\t📍 " + location + ": \n"
            for rider in rider_list:
                plain_body += "\t\t" + rider['name'] + " (" + rider['phone'] + ") "
                if rider['notes']:
                    plain_body += " | Rider note: " + rider['notes'] 
                plain_body += "\n"

        plain_body += f"""
    * 📲 Quick copy-and-paste to create a group chat with your riders: {', '.join(numbers)}

⭐️ EVENT INFORMATION 
Event: {opportunity.name}
Date/Time: {time_data['formal']}
Location: {opportunity.address}

Thank you for helping make this event a success! If you have any questions or issues, contact the CampusCares team at team@campuscares.us.

Safe driving,
CampusCares Team
        """

        body += f"""
<p>Thank you for volunteering to drive for the upcoming CampusCares event! Here are the details for your carpool:</p>

<hr style="border: none; border-top: 2px solid #e0e0e0; margin: 20px 0;">

<h3 style="color: #2c5aa0; margin-bottom: 10px;">🚗 RIDERS YOU'RE PICKING UP</h3>
<div style="margin-left: 20px;">
"""
        riders_by_location = defaultdict(list)
        numbers = []
        for r in riders:
            riders_by_location[r.pickup_location].append({
                'name': r.user.name,
                'notes': r.notes,
                'phone': r.user.phone
            })
            numbers.append(r.user.phone)

        for location, rider_list in riders_by_location.items():
            body += '<p style="margin-bottom: 5px;"><strong>📍 ' + location + '</strong></p>'
            body += '<ul style="list-style-type: none; padding-left: 20px; margin-top: 5px; margin-bottom: 15px;">'
            for rider in rider_list:
                body += '<li style="margin-bottom: 5px;">' + rider['name'] + " - (" + rider['phone'] + ") "
                if rider['notes']:
                    body += ' <em style="color: #666;">– Note: ' + rider['notes'] + '</em>'
                body += '</li>'
            body += '</ul>'
        
        body += f"""
    </div>

    <p style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; font-size: 12px;">
        📲 <em>Quick copy-and-paste to create a group chat with your riders:</em> {', '.join(numbers)}
    </p>

    <p style="background-color: #fff3cd; padding: 12px; border-left: 4px solid #ffc107; border-radius: 3px;">
        Please confirm your pickup schedule and any specific arrangements with your riders using the contact information above.
    </p>

    <hr style="border: none; border-top: 2px solid #e0e0e0; margin: 20px 0;">

    <h3 style="color: #2c5aa0; margin-bottom: 10px;">📅 EVENT DETAILS</h3>

    <p>
        <strong>Event:</strong> {opportunity.name}<br>
        <strong>Date & Time:</strong> {time_data['formal']}<br>
        <strong>Location:</strong> {opportunity.address}
    </p>

    <hr style="border: none; border-top: 2px solid #e0e0e0; margin: 20px 0;">

    <p>Thank you for helping make this event a success! If you have any questions or issues, contact the CampusCares team at
         <a href="mailto:team@campuscares.us" style="color: #2c5aa0;">team@campuscares.us</a>.</p>

    <p>
        Safe driving,<br>
        The CampusCares Team
    </p>
</body>

</html>
"""
    return body, plain_body

def create_rider_email_body(ride, rider, car, riders, opportunity, time_data):
    plain_body = f"""Hi {rider.user.name},

Thank you for signing up to volunteer for the upcoming CampusCares event! Here are the details for your carpool:

📅 EVENT INFORMATION
Event: {opportunity.name}
Date/Time: {time_data['formal']}
Location: {opportunity.address}

🚗 RIDE INFORMATION
Pickup Location: {rider.pickup_location} 
Driver Contact Information: 
    Name: {ride.driver.name}
    Email: {ride.driver.email}
    Phone Number: {ride.driver.phone}\n
    """

    if car and car.color:
        plain_body += f"Car Color: {car.color}\n"
    if car and car.model:
        plain_body += f"Car Model: {car.model}\n"
    if car and car.license_plate:
        plain_body += f"Last 4 Characters of License Plate: {car.license_plate}\n"

    other_riders = ', '.join([r.user.name for r in riders if r.id != rider.id])
    plain_body += f"""
Other Riders in Your Carpool: {other_riders}

Your driver may reach out to you with further information, but unless told otherwise, please arrive at the pickup location at least 20 minutes prior to the event's start time. 
Please don't hesitate to reach out to your driver if you have any questions or special requests. For any other inquiries, contact the CampusCares team at team@campuscares.us.

Thank you again for volunteering!

Best Regards,
CampusCares Team
    """

    body = f"""<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
    <p>Hi {rider.user.name},</p>

    <p>Thank you for signing up to volunteer for the upcoming CampusCares event! Below are your carpool details:</p>

    <hr style="border: none; border-top: 2px solid #e0e0e0; margin: 20px 0;">

    <h3 style="color: #2c5aa0; margin-bottom: 10px;">🚗 YOUR RIDE INFORMATION</h3>

    <p>
        <strong>Pickup Location:</strong> {rider.pickup_location}<br>
        <strong>Driver Contact:</strong><br>
        &nbsp;&nbsp;&nbsp;&nbsp;Name: {ride.driver.name}<br>
        &nbsp;&nbsp;&nbsp;&nbsp;Email: {ride.driver.email}<br>
        &nbsp;&nbsp;&nbsp;&nbsp;Phone: {ride.driver.phone}<br>
    </p>
"""
    if car and car.color:
        body += f"<strong>Car Color:</strong> {car.color}<br>"
    if car and car.model:
        body += f"<strong>Car Model:</strong> {car.model}<br>"
    if car and car.license_plate:
        body += f"<strong>Last 4 characters of license plate:</strong> {car.license_plate}<br>"

    body += f"""
    <p><strong>Other Riders in Your Carpool:</strong> {other_riders}</p>

    <hr style="border: none; border-top: 2px solid #e0e0e0; margin: 20px 0;">

    <h3 style="color: #2c5aa0; margin-bottom: 10px;">📅 EVENT DETAILS</h3>

    <p>
        <strong>Event:</strong> {opportunity.name}<br>
        <strong>Date & Time:</strong> {time_data['formal']}<br>
        <strong>Location:</strong> {opportunity.address}
    </p>

    <p style="background-color: #fff3cd; padding: 12px; border-left: 4px solid #ffc107; border-radius: 3px;">
        <strong>Important:</strong> Unless told otherwise, please arrive at your pickup location at least 20 minutes before the event start
        time.
    </p>

    <hr style="border: none; border-top: 2px solid #e0e0e0; margin: 20px 0;">

    <p>Your driver may reach out with additional information. If you have any questions or special requests, please
        contact your driver directly. For other questions or concerns, reach out to us at <a
            href="mailto:team@campuscares.us" style="color: #2c5aa0;">team@campuscares.us</a>.</p>

    <p>Thank you for volunteering with CampusCares!</p>

    <p>
        Best,<br>
        The CampusCares Team
    </p>
</body>

</html>
"""
    return body, plain_body
    

@celery.task(name="tasks.send_carpool_email")
def send_carpool_email(opportunity_id):
    # from app import app
    from shared import app, Opportunity, User, Carpool, Car, Ride, RideRider
    with app.app_context():
        """Send carpool info email via Mailgun"""
        try:
            print("[TASK] Running send_carpool_email")
            print(f"[TASK] opportunity_id = {opportunity_id}")
            opportunity = Opportunity.query.get(opportunity_id)
            time_data = format_datetime(opportunity.date)
            carpool = Carpool.query.filter_by(opportunity_id=opportunity_id).first()
            rides = Ride.query.filter_by(carpool_id=carpool.id).all()
            print(f"[TASK] Loaded opportunity: {opportunity}")
            print(f"[TASK] Loaded rides: {rides}")

            for ride in rides:
                car = Car.query.filter_by(user_id=ride.driver_id).first()
                riders = ride.ride_riders
                subject = f"[{time_data['short']}] Carpool Information for {opportunity.name}"

                body, plain_body = create_driver_email_body(ride, riders, opportunity, time_data)
                requests.post(
                    f"https://api.mailgun.net/v3/{DOMAIN}/messages",
                    auth=("api", MAILGUN_API_KEY),
                    data={
                        "from": f"CampusCares <postmaster@{DOMAIN}>",
                        "to": ride.driver.email,
                        "subject": subject,
                        "text": plain_body,
                        "html": body
                    }
                )

                for rider in riders:
                    body, plain_body = create_rider_email_body(ride, rider, car, riders, opportunity, time_data)
                    requests.post(
                        f"https://api.mailgun.net/v3/{DOMAIN}/messages",
                        auth=("api", MAILGUN_API_KEY),
                        data={
                            "from": f"CampusCares <postmaster@{DOMAIN}>",
                            "to": rider.user.email,
                            "subject": subject,
                            "text": plain_body,
                            "html": body
                        }
                    )
        except Exception as e:
            return "Failed to send email: " + str(e)
