from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL")
redis_connection=redis_url+"/0?ssl_cert_reqs=CERT_NONE"

celery = Celery(
    "tasks",
    broker=redis_connection,
    backend=redis_connection
)

# Optional: make sure Celery retries lost connections gracefully
celery.conf.broker_transport_options = {"visibility_timeout": 3600}
