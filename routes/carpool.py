from flask import Blueprint, request, jsonify
from services.carpool_service import create_driver_email_body, create_rider_email_body
from utils.auth import require_api_key
import requests
from utils.helper import format_datetime
import os

MAILGUN_API_KEY = os.environ["MG_API_KEY"]
DOMAIN = "mg.campuscares.us"

carpool_bp = Blueprint("carpool", __name__)

@carpool_bp.route('/api/send-carpool-email', methods=['POST'])
@require_api_key
def send_carpool_email_endpoint():
    """
    HTTP endpoint that Cloudflare Worker calls to send emails.
    This keeps your Fly.io app active only when needed.
    """
    try:
        data = request.get_json()
        opportunity_id = data.get('opportunity_id')
        
        if not opportunity_id:
            return jsonify({'error': 'Missing opportunity_id'}), 400
        
        # Convert to int explicitly
        try:
            opportunity_id = int(opportunity_id)
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid opportunity_id format'}), 400
        
        # Import your models
        from shared import Opportunity, Carpool, Ride, Car
        
        opportunity = Opportunity.query.get(opportunity_id)
        if not opportunity:
            return jsonify({'error': 'Opportunity not found'}), 404
        
        time_data = format_datetime(opportunity.date, opportunity.multiopp_id)
        print(f"OPP: {opportunity}")
        print(f"MULTIOPP ID: {opportunity.multiopp_id}")
        carpool = Carpool.query.filter_by(opportunity_id=opportunity_id).first()
        
        if not carpool:
            return jsonify({'error': 'No carpool found'}), 404
        
        rides = Ride.query.filter_by(carpool_id=carpool.id).all()
        
        emails_sent = 0
        
        for ride in rides:
            car = Car.query.filter_by(user_id=ride.driver_id).first()
            riders = ride.ride_riders
            subject = f"[{time_data['short']}] Carpool Information for {opportunity.name}"

            # Send driver email
            body, plain_body = create_driver_email_body(ride, riders, opportunity, time_data)
            response = requests.post(
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
            
            if response.status_code == 200:
                emails_sent += 1

            # Send rider emails
            for rider in riders:
                body, plain_body = create_rider_email_body(ride, rider, car, riders, opportunity, time_data)
                response = requests.post(
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
                
                if response.status_code == 200:
                    emails_sent += 1
        
        return jsonify({
            'success': True,
            'emails_sent': emails_sent,
            'opportunity_id': opportunity_id
        }), 200
        
    except Exception as e:
        print(f"Error sending carpool email: {str(e)}")
        return jsonify({'error': str(e)}), 500

