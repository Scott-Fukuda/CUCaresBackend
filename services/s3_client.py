import os 
import boto3

# S3 configuration (with fallback for development)
try:
    S3_BUCKET = os.environ.get("S3_BUCKET")
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_DEFAULT_REGION = os.environ.get("AWS_DEFAULT_REGION")
    
    if all([S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION]):
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_DEFAULT_REGION
        )
        print("S3 client initialized successfully")
    else:
        s3 = None
        print("Warning: S3 environment variables not set. S3 functionality will be disabled.")
except Exception as e:
    s3 = None
    print(f"Warning: S3 client initialization failed: {e}")
    print("S3 functionality will be disabled.")