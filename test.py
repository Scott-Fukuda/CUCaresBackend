from scheduler import schedule_carpool_email
from datetime import datetime, timedelta
import pytz

s = "2025-11-30 21:00:00"

# Parse into a datetime object
dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

dt_utc = pytz.utc.localize(dt)
print(f"utc: {dt_utc}")

eastern = pytz.timezone('US/Eastern')
dt_eastern = dt_utc.astimezone(eastern)

formal_format = dt_eastern.strftime('%B %-d, %Y, %-I:%M %p')  
print(f"formal: {formal_format}")

# Convert to ISO format
iso_string = dt_utc.isoformat()
print(f"iso: {iso_string}")

# dt_converted = dt - timedelta(hours=5)
# print("est", dt_converted)

# # Convert to ISO format
# iso = dt_converted.isoformat()

# print("iso", iso)