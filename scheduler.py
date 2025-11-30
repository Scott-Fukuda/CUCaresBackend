import requests
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()

CLOUDFLARE_WORKER_URL = os.environ["CLOUDFLARE_WORKER_URL"]

def schedule_carpool_email(opportunity_id, event_dt):
    """
    Schedule the carpool email for a given opportunity via Cloudflare Workers.

    Parameters
    ----------
    opportunity_id : int
        The ID of the opportunity.
    event_dt : datetime.datetime
        The datetime of the event (can be naive or aware).
    """
    
    # dt_send_time = event_dt - timedelta(hours=7)
    iso = event_dt.isoformat()
    print(f"[INFO] Event date time: {event_dt.isoformat()}")
    print(f"[INFO] Event send time: {iso}")
    
    try:
        response = requests.post(
            f"{CLOUDFLARE_WORKER_URL}/api/schedule-email",
            json={
                "opportunity_id": opportunity_id,
                "event_datetime": iso,
                "email_type": "carpool"
            },
            timeout=10
        )
        
        response.raise_for_status()
        result = response.json()
        
        print(f"[SUCCESS] Scheduled email for opportunity {opportunity_id}")
        print(f"[DEBUG] Send time: {result.get('send_time')}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to schedule email: {str(e)}")
        raise


def cancel_scheduled_email(opportunity_id):
    """
    Cancel a scheduled email for a given opportunity.

    Parameters
    ----------
    opportunity_id : int
        The ID of the opportunity.
    """
    try:
        response = requests.delete(
            f"{CLOUDFLARE_WORKER_URL}/api/cancel-email",
            params={"opportunity_id": opportunity_id},
            timeout=10
        )
        
        response.raise_for_status()
        result = response.json()
        
        print(f"[SUCCESS] Cancelled email for opportunity {opportunity_id}")
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to cancel email: {str(e)}")
        raise