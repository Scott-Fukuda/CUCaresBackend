import firebase_admin
from firebase_admin import auth, credentials, initialize_app
import os 

def init_firebase():
    try:
        # Check if Firebase service account JSON is provided as environment variable
        if "FIREBASE_SERVICE_ACCOUNT" in os.environ:
            # Use the JSON content directly from environment variable
            import json
            service_account_info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
            print("Firebase Admin SDK initialized successfully with environment variable")
        elif "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
            # Get the path to the service account file
            service_account_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
            
            # If it's a relative path, make it absolute
            if not os.path.isabs(service_account_path):
                service_account_path = os.path.join(os.getcwd(), service_account_path)
            
            # Check if the file exists
            if os.path.exists(service_account_path):
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                print(f"Firebase Admin SDK initialized successfully with: {service_account_path}")
            else:
                print(f"Warning: Service account file not found at: {service_account_path}")
                firebase_admin.initialize_app()
        else:
            print("Warning: Firebase credentials not found")
            print("Set FIREBASE_SERVICE_ACCOUNT environment variable with JSON content")
            print("Or set GOOGLE_APPLICATION_CREDENTIALS to point to service account file")
            # Initialize with default app (for development/testing)
            firebase_admin.initialize_app()
    except Exception as e:
        print(f"Warning: Firebase Admin SDK initialization failed: {e}")
        print("Firebase authentication endpoints will not work")
