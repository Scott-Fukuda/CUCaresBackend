from dotenv import load_dotenv
import os
import requests
from collections import defaultdict
from app import app, db
from db import Opportunity, User, Carpool, Car, Ride, RideRider

load_dotenv()
MG_API_KEY=os.getenv('MG_API_KEY')
DOMAIN="mg.campuscares.us"

with app.app_context():
	ride = Ride.query.filter_by(carpool_id=37).first()
	riders = ride.ride_riders

	body = """Hi Grace,

Thank you for signing up to volunteer for the upcoming CampusCares event! Here are the details for your carpool:

⭐️ RIDE INFORMATION
Pickup Location: Balch
Driver Name: fdsa
Driver Contact Information: 
	Email: hi@gmail.com
	Phone Number: 3431498
Other Riders in Your Carpool: brad, chad

⭐️ YOUR RIDERS
"""
	# rows = [["chad", "rpcc", "hi hi hi hi", "3604672846"], ["brad", "balch", "", "71384019"]]

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
		body += "\t📍 " + location + ": \n"
		for rider in rider_list:
			body += "\t\t" + rider['name'] + " (" + rider['phone'] + ") "
			if rider['notes']:
				body += " | Rider note: " + rider['notes'] 
			body += "\n"

	body += f"""
	* 📲 Quick copy-and-paste to create a group chat with your riders: {', '.join(numbers)}

⭐️ Event Information: 
Event: asda
Date/Time: Nov 14, 11 PM
Location: fdfs

Your driver may reach out to you with further information, but unless told otherwise, please arrive at the pickup location atleast 20 minutes prior to the event's start time. 
Please don't hesitate to reach out to your driver if you have any questions or special requests. If you have any other questions or issues, contact the CampusCares team at team@campuscares.us.

Thank you again for volunteering!

Best Regards,
CampusCares Team"""
	
	htmlbody = """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
    <p>Hi Grace,</p>
    
    <p>Thank you for signing up to volunteer for the upcoming CampusCares event! Below are your carpool details:</p>
    
    <hr style="border: none; border-top: 2px solid #e0e0e0; margin: 20px 0;">
    
    <h3 style="color: #2c5aa0; margin-bottom: 10px;">🚗 YOUR RIDE INFORMATION</h3>
    
    <p>
        <strong>Pickup Location:</strong> Balch<br>
        <strong>Driver:</strong> fdsa<br>
        <strong>Driver Contact:</strong><br>
        &nbsp;&nbsp;&nbsp;&nbsp;Email: hi@gmail.com<br>
        &nbsp;&nbsp;&nbsp;&nbsp;Phone: 3431498
    </p>
    
    <p><strong>Other Riders in Your Carpool:</strong> brad, chad</p>
    
    <hr style="border: none; border-top: 2px solid #e0e0e0; margin: 20px 0;">
    
    <h3 style="color: #2c5aa0; margin-bottom: 10px;">👥 RIDERS YOU'RE PICKING UP</h3>
    
    <ul style="list-style-type: none; padding-left: 0;">
        <li style="margin-bottom: 8px;"><strong>Carmen Lee</strong> – RPCC – (555-8765)</li>
        <li style="margin-bottom: 8px;"><strong>Brian Smith</strong> – Balch – (555-5678) – <em>Note: hehe</em></li>
    </ul>
    
    <p style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; font-size: 14px;">
        <em>Quick copy-and-paste for group chat:</em> 555-8765, 555-5678
    </p>
    
    <hr style="border: none; border-top: 2px solid #e0e0e0; margin: 20px 0;">
    
    <h3 style="color: #2c5aa0; margin-bottom: 10px;">📅 EVENT DETAILS</h3>
    
    <p>
        <strong>Event:</strong> asda<br>
        <strong>Date & Time:</strong> Nov 14, 11 PM<br>
        <strong>Location:</strong> fdfs
    </p>
    
    <p style="background-color: #fff3cd; padding: 12px; border-left: 4px solid #ffc107; border-radius: 3px;">
        <strong>Important:</strong> Please arrive at your pickup location at least 20 minutes before the event start time.
    </p>
    
    <hr style="border: none; border-top: 2px solid #e0e0e0; margin: 20px 0;">
    
    <p>Your driver may reach out with additional information. If you have any questions or special requests, please contact your driver directly. For other questions or concerns, reach out to us at <a href="mailto:team@campuscares.us" style="color: #2c5aa0;">team@campuscares.us</a>.</p>
    
    <p>Thank you for volunteering with CampusCares!</p>
    
    <p>
        Best,<br>
        The CampusCares Team
    </p>
</body>
</html>
"""

	def send_test_message():
		return requests.post(
		"https://api.mailgun.net/v3/mg.campuscares.us/messages",
		auth=("api", os.getenv('MG_API_KEY', 'MG_API_KEY')),
			data={"from": "Mailgun Sandbox <postmaster@mg.campuscares.us>",
				"to": "Grace Matsuoka <graciematsuoka@gmail.com>",
				"subject": "Hello Grace Matsuoka",
				"text": body,
				"html": htmlbody
				})
      

if __name__ == "__main__":
	# print("BODY", body)
    response = send_test_message()
    print("Status code:", response.status_code)
    print("Response body:", response.text)