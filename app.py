import json
import os
import uuid
from flask import Flask, request, jsonify, send_from_directory, make_response, session
from db import db, User, Organization, Opportunity, UserOpportunity, Friendship, ApprovedEmail, MultiOpportunity
from sqlalchemy import select

from datetime import datetime, timedelta, timezone
from flask_cors import CORS
from werkzeug.utils import secure_filename
import firebase_admin
from firebase_admin import auth, credentials, initialize_app
from dotenv import load_dotenv
import boto3
from flask_migrate import Migrate
import random
import redis
from celery import Celery
import csv, io
from functools import wraps
import traceback
from config import StagingConfig

# define db filename
db_filename = "cucares.db"
app = Flask(__name__, static_folder='build', static_url_path='')

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Load environment variables from .env file
load_dotenv()

app.secret_key = os.environ["FLASK_SECRET_KEY"]

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

env = os.environ.get("FLASK_ENV", "production")

# restrict API access to requests from secure origin
if env == "staging":
    CORS(app, origins=["http://localhost:5173", "https://campuscares.us", "https://www.campuscares.us"], supports_credentials=True)
else: 
    CORS(app, origins=["https://campuscares.us", "https://www.campuscares.us"], supports_credentials=True)

# CORS(app, origins=["https://campuscares.us", "https://www.campuscares.us", "http://localhost:5173"], supports_credentials=True)

# Initialize Firebase Admin SDK
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

if env == "staging":
    app.config.from_object(StagingConfig)

# setup config
database_url = os.environ.get('DATABASE_URL', f"sqlite:///{db_filename}")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = os.environ.get('FLASK_ENV') == 'development'
from sqlalchemy import create_engine
engine = create_engine(database_url)
print("trying")
print(database_url)
conn = engine.connect()
print("Connected!")
# initialize app
db.init_app(app)
migrate = Migrate(app, db)

# with app.app_context():
    # For app migrations don't create all tables
    # db.create_all()

    # NOTE: DON'T UNCOMMENT UNLESS YOU WANT TO DELETE TABLES
    # User.__table__.drop(db.engine)
    # Opportunity.__table__.drop(db.engine)
    # Organization.__table__.drop(db.engine)
    # UserOpportunity.__table__.drop(db.engine)
    # Friendship.__table__.drop(db.engine)


# Helper function to handle pagination
def paginate(query, page=1, per_page=20):
    return query.paginate(page=page, per_page=per_page, error_out=False)

# Authentication middleware function
def require_auth(f):
    """Decorator to require Firebase authentication for endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == "OPTIONS":
            return '', 200
        try:
            # Get the Authorization header
            auth_header = request.headers.get('Authorization')
            
            if not auth_header:
                return jsonify({
                    'error': 'Authorization header is required',
                    'message': 'Please provide a valid Firebase ID token'
                }), 401
            
            # Check if it's a Bearer token
            if not auth_header.startswith('Bearer '):
                return jsonify({
                    'error': 'Invalid authorization format',
                    'message': 'Authorization header must be in format: Bearer <token>'
                }), 401
            
            # Extract the token
            token = auth_header.split('Bearer ')[1]
            
            if not token:
                return jsonify({
                    'error': 'Token is required',
                    'message': 'Please provide a valid Firebase ID token'
                }), 401
            
            # Verify the token
            verification_result = verify_firebase_token(token)
            
            if not verification_result['success']:
                return jsonify({
                    'error': 'Invalid token',
                    'message': 'The provided token is invalid or expired',
                    'details': verification_result.get('error', 'Unknown error')
                }), 401
            
            # Attach user info to request
            request.user = {
                'uid': verification_result['user_id'],
                'email': verification_result['email'],
                'name': verification_result['name'],
                'picture': verification_result['picture']
            }
            
            return f(*args, **kwargs)
            
        except Exception as e:
            return jsonify({
                'error': 'Authentication failed',
                'message': 'An error occurred during authentication',
                'details': str(e)
            }), 500
    
    # Preserve the original function name for debugging
    decorated_function.__name__ = f.__name__
    return decorated_function

# Helper functions for file uploads
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_user_image(file, email):
    """Save user image to S3 with email-based filename"""
    if file and allowed_file(file.filename):
        # Get file extension
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        
        # Create filename: original_filename_email.extension
        original_filename = secure_filename(file.filename.rsplit('.', 1)[0])
        filename = f"{original_filename}_{email}.{file_extension}"
        
        # Upload to S3
        s3.upload_fileobj(
            file,
            S3_BUCKET,
            filename,
            ExtraArgs={"ContentType": file.content_type}
        )
        
        # Return the S3 URL
        return f"https://{S3_BUCKET}.s3.amazonaws.com/{filename}"
    
    return None

def save_opportunity_image(file, opportunity_id):
    """Save opportunity image to S3 with opportunity_id-based filename"""
    if file and allowed_file(file.filename):
        # Get file extension
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        
        # Create filename: image_{opportunity_id}.extension
        filename = f"image_{opportunity_id}.{file_extension}"
        
        # Upload to S3
        s3.upload_fileobj(
            file,
            S3_BUCKET,
            filename,
            ExtraArgs={"ContentType": file.content_type}
        )
        
        # Return the S3 URL
        return f"https://{S3_BUCKET}.s3.amazonaws.com/{filename}"
    
    return None

def verify_firebase_token(token):
    """Verify Firebase ID token and return user info"""
    try:
        # Verify the token
        decoded_token = auth.verify_id_token(token)
        return {
            'success': True,
            'user_id': decoded_token['uid'],
            'email': decoded_token.get('email'),
            'name': decoded_token.get('name'),
            'picture': decoded_token.get('picture')
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
    
# ROUTES
@app.route('/api/hi')
def hello():
    return {"message": "Hello from flask :)"}

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    # If the request matches a static file, serve it
    file_path = os.path.join(app.static_folder, path)
    if path != "" and os.path.exists(file_path):
        return send_from_directory(app.static_folder, path)
    # Otherwise, serve index.html for React Router
    return send_from_directory(app.static_folder, 'index.html')

# Staging Endpoints
if env == "staging":
    @app.route("/api/login-test/<int:user_id>")
    def login_test(user_id):
        user = User.query.get(user_id)
        if user: 
            session["user_id"] = user.id
            print(f"Logged in test user {user.name}")
            return jsonify(user.serialize()), 200
        print("User not found")
        return "User not found", 404

# Special Endpoints
@app.route('/api/register-opp', methods=['POST'])
@require_auth
def register_user_for_opportunity():
    data = request.get_json()
    user_id = data.get('user_id')
    opportunity_id = data.get('opportunity_id')
    driving = data.get('driving', False)  # Default to False if not provided

    if not user_id or not opportunity_id:
        return jsonify({"error": "user_id and opportunity_id are required"}), 400

    # Check if entry already exists
    existing = UserOpportunity.query.filter_by(user_id=user_id, opportunity_id=opportunity_id).first()
    if existing:
        return jsonify({"message": "User already registered"}), 200

    try:
        user_opportunity = UserOpportunity(
            user_id=user_id,
            opportunity_id=opportunity_id,
            registered=True,
            attended=False,  # default
            driving=driving
        )
        db.session.add(user_opportunity)
        db.session.commit()
        return jsonify({"message": "Registration successful"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/unregister-opp', methods=['POST'])
@require_auth
def unregister_user_from_opportunity():
    """Unregister a user from an opportunity"""
    data = request.get_json()
    user_id = data.get('user_id')
    opportunity_id = data.get('opportunity_id')

    if not user_id or not opportunity_id:
        return jsonify({"error": "user_id and opportunity_id are required"}), 400

    # Check if user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({
            "message": "User does not exist",
            "error": f"User with ID {user_id} not found"
        }), 404

    # Check if opportunity exists
    opportunity = Opportunity.query.get(opportunity_id)
    if not opportunity:
        return jsonify({
            "message": "Opportunity does not exist",
            "error": f"Opportunity with ID {opportunity_id} not found"
        }), 404

    # Check if user is registered with the opportunity
    existing = UserOpportunity.query.filter_by(user_id=user_id, opportunity_id=opportunity_id).first()
    if not existing:
        return jsonify({
            "message": "User not registered with this opportunity",
            "error": f"User {user_id} is not registered for opportunity {opportunity_id}"
        }), 404

    try:
        # Remove the association
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"message": "Unregistration successful"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/register-org', methods=['POST'])
@require_auth
def register_user_for_organization():
    data = request.get_json()
    user_id = data.get('user_id')
    organization_id = data.get('organization_id')

    if not user_id or not organization_id:
        return jsonify({"error": "user_id and organization_id are required"}), 400

    user = User.query.get(user_id)
    organization = Organization.query.get(organization_id)

    if not user or not organization:
        return jsonify({"error": "Invalid user_id or organization_id"}), 404

    # Check if entry already exists
    if organization in user.organizations:
        return jsonify({"message": "User already registered"}), 200

    try:
        user.organizations.append(organization)
        organization.member_count += 1
        db.session.commit()
        return jsonify({"message": "Registration successful"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/unregister-org', methods=['POST'])
@require_auth
def unregister_user_from_organization():
    """Unregister a user from an organization"""
    data = request.get_json()
    user_id = data.get('user_id')
    organization_id = data.get('organization_id')

    if not user_id or not organization_id:
        return jsonify({"error": "user_id and organization_id are required"}), 400

    user = User.query.get(user_id)
    organization = Organization.query.get(organization_id)

    if not user or not organization:
        return jsonify({"error": "Invalid user_id or organization_id"}), 404

    # Check if user is registered with the organization
    if organization not in user.organizations:
        return jsonify({"message": "User not registered with this organization"}), 200

    try:
        # Remove the relationship
        user.organizations.remove(organization)
        organization.member_count = max(0, organization.member_count - 1)  # Prevent negative count
        db.session.commit()
        return jsonify({"message": "Unregistration successful"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/attendance', methods=['PUT'])
@require_auth
def marked_as_attended():
    data = request.get_json()
    user_ids = data.get('user_ids')
    opportunity_id = data.get('opportunity_id')
    duration = data.get('duration')
    driving = data.get('driving', False)

    if not user_ids or not opportunity_id:
        return jsonify({"error": "user_ids and opportunity_id are required"}), 400

    messages = []
    try:
        opp = Opportunity.query.get(opportunity_id)
        if not opp:
            return jsonify({"error": "Invalid opportunity_id"}), 404

        # Fetch existing registrations for these users
        user_opps = UserOpportunity.query.filter(
            UserOpportunity.user_id.in_(user_ids),
            UserOpportunity.opportunity_id == opportunity_id
        ).all()

        # Map by user_id for O(1) lookup
        user_opp_map = {uo.user_id: uo for uo in user_opps}

        first_user = True
        for user_id in user_ids:
            uo = user_opp_map.get(user_id)

            if first_user:
                uo.user.points += 5 # bonus points
                first_user = False

            if not uo:
                # Not registered -> skip
                messages.append({"user_id": user_id, "error": "User not registered for this opportunity"})
                continue

            if not uo.attended:
                uo.attended = True
                uo.driving = driving
                uo.user.points += duration  # Award points to the User
                messages.append({"user_id": user_id, "message": "Attendance updated & points awarded"})
            else:
                messages.append({"user_id": user_id, "message": "User already marked as attended"})

        # Update opportunity metadata
        opp.actual_runtime = duration
        opp.attendance_marked = True

        db.session.commit()
        return jsonify({"results": messages}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# User Endpoints
@app.route('/api/users', methods=['POST'])
@require_auth
def create_user():
    """Create a new user with optional file upload"""
    try:
        # Access authenticated user information
        # request.user contains: {'uid': 'firebase_uid', 'email': 'user@example.com', 'name': 'User Name', 'picture': 'profile_url'}
        authenticated_user = request.user
        print(f"Authenticated user: {authenticated_user}")
        
        # Check if this is a multipart form (file upload) or JSON
        # Check if this is a multipart form (file upload) or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file upload
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            points = request.form.get('points', 0)
            car_seats = request.form.get('car_seats', 0)
            interests = request.form.get('interests', '[]')  # Default to empty JSON array string
            
            # Validate required fields
            if not name or not email or not phone:
                return jsonify({
                    'message': 'Missing required fields',
                    'required': ['name', 'email', 'phone']
                }), 400
            
            # Handle image upload
            image_path = None
            if 'image' in request.files:
                file = request.files['image']
                image_path = save_user_image(file, email)
            
            # Parse interests from JSON string to list
            try:
                import json
                interests_list = json.loads(interests) if interests else []
            except (json.JSONDecodeError, TypeError):
                interests_list = []
            
            data = {
                'name': name,
                'email': email,
                'phone': phone,
                'points': points,
                'interests': interests_list,
                'profile_image': image_path,
                'admin': request.form.get('admin', False),
                'gender': request.form.get('gender'),
                'graduation_year': request.form.get('graduation_year'),
                'academic_level': request.form.get('academic_level'),
                'major': request.form.get('major'),
                'birthday': request.form.get('birthday'),
                'car_seats': car_seats,
                'bio': request.form.get('bio')
            }
        else:
            # Handle JSON data
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['name', 'email']
            if not all(field in data for field in required_fields):
                return jsonify({
                    'message': 'Missing required fields',
                    'required': required_fields
                }), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({
                'message': 'Email already registered'
            }), 400
        
        # Parse birthday if provided
        birthday = None
        if data.get('birthday'):
            try:
                birthday = datetime.strptime(data['birthday'], '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                try:
                    birthday = datetime.strptime(data['birthday'], '%Y-%m-%d')
                except ValueError:
                    return jsonify({
                        'message': 'Invalid birthday format. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS'
                    }), 400
        
        # Check if user should be admin based on email
        is_admin = data.get('admin', False)
        default_admin_emails = os.environ.get('DEFAULT_ADMIN_EMAILS', '')
        if default_admin_emails:
            try:
                # Try to parse as JSON first (in case it's a JSON array string)
                import json
                try:
                    admin_email_list = json.loads(default_admin_emails)
                except json.JSONDecodeError:
                    # If not JSON, parse as hyphen-separated list
                    admin_email_list = [email.strip() for email in default_admin_emails.split('-')]
                
                if data['email'] in admin_email_list:
                    is_admin = True
                print(f"DEBUG: Admin email list = {admin_email_list}, User email = {data['email']}, is_admin = {is_admin}")
            except Exception as e:
                print(f"Warning: Error parsing DEFAULT_ADMIN_EMAILS: {e}")
        
        # Create new user
        new_user = User(
            profile_image=data.get('profile_image'),
            name=data['name'],
            email=data['email'],
            phone=data.get('phone'),
            points=data.get('points', 0),
            interests=data.get('interests', []),
            admin=is_admin,
            gender=data.get('gender'),
            graduation_year=data.get('graduation_year'),
            academic_level=data.get('academic_level'),
            major=data.get('major'),
            birthday=birthday,
            bio=data.get('bio')
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify(new_user.serialize()), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to create user',
            'error': str(e)
        }), 500

@app.route('/api/users/emails', methods=['GET'])
@require_auth
def get_user_emails():
    """Get all user emails"""
    try:
        users = User.query.all()
        return jsonify([user.email for user in users])
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch user emails',
            'error': str(e)
        }), 500

@app.route('/api/users', methods=['GET'])
@require_auth
def get_users():
    """Get all users with full details - requires authentication"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        users = User.query.order_by(User.id.desc())
        paginated_users = paginate(users, page, per_page)
        
        return jsonify({
            'users': [user.serialize() for user in paginated_users.items],
            'pagination': {
                'page': paginated_users.page,
                'per_page': paginated_users.per_page,
                'total': paginated_users.total
            }
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch users',
            'error': str(e)
        }), 500

@app.route('/api/users/<int:user_id>', methods=['GET'])
@require_auth
def get_user(user_id):
    """Get a single user"""
    try:
        user = User.query.get_or_404(user_id)
        print('user', user.serialize())
        return jsonify(user.serialize())
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch user',
            'error': str(e)
        }), 500

@app.route('/api/users/check/<email>', methods=['GET'])
def check_user_exists(email):
    """Get user by email - Login only: Quick check if user exists with minimal data"""
    try:
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({
                'message': 'User does not exist',
                'exists': False
            }), 200
        
        # Return minimal user data for authentication
        return jsonify({
            'exists': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'admin': user.admin,
            }
        }), 200
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch user by email',
            'error': str(e)
        }), 500
    
@app.route('/api/users/email/<email>', methods=['GET'])
@require_auth
def get_user_by_email(email):
    """Get user by email - Login only: Quick check if user exists with minimal data"""
    try:
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({
                'message': 'User does not exist',
            }), 404
        
        # Return minimal user data for authentication
        return jsonify(user.serialize()), 200
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch user by email',
            'error': str(e)
        }), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@require_auth
def update_user(user_id):
    """Update a user with optional file upload"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Check if this is a multipart form (file upload) or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file upload
            data = {}
            for field in ['name', 'car_seats', 'email', 'phone', 'points', 'admin', 'gender', 'graduation_year', 'academic_level', 'major', 'birthday', 'bio']:
                if field in request.form:
                    data[field] = request.form[field]
            
            # Handle interests field from form
            if 'interests' in request.form:
                try:
                    import json
                    interests_list = json.loads(request.form['interests']) if request.form['interests'] else []
                    data['interests'] = interests_list
                except (json.JSONDecodeError, TypeError):
                    data['interests'] = []
            
            # Handle profile image upload
            if 'profile_image' in request.files:
                file = request.files['profile_image']
                image_path = save_user_image(file, user.email)
                if image_path:
                    data['profile_image'] = image_path
        else:
            # Handle JSON data
            data = request.get_json()
        
        # Only update fields that exist in the model
        valid_fields = ['profile_image', 'name', 'email', 'phone', 'points', 'interests', 'admin', 'gender', 'graduation_year', 'academic_level', 'major', 'birthday', 'bio', 'car_seats']
        for field in valid_fields:
            if field in data:
                if field == 'birthday':
                    # Parse birthday if provided
                    birthday = None
                    if data['birthday']:
                        try:
                            birthday = datetime.strptime(data['birthday'], '%Y-%m-%dT%H:%M:%S')
                        except ValueError:
                            try:
                                birthday = datetime.strptime(data['birthday'], '%Y-%m-%d')
                            except ValueError:
                                return jsonify({
                                    'message': 'Invalid birthday format. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS'
                                }), 400
                    setattr(user, field, birthday)
                else:
                    setattr(user, field, data[field])
        
        db.session.commit()
        return jsonify(user.serialize())
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to update user',
            'error': str(e)
        }), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@require_auth
def delete_user(user_id):
    """Delete a user"""
    try:
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return jsonify({
            'message': 'User deleted successfully'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to delete user',
            'error': str(e)
        }), 500

# Organization Endpoints
@app.route('/api/orgs', methods=['POST'])
@require_auth
def create_organization():
    """Create a new organization"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'host_user_id']
        if not all(field in data for field in required_fields):
            return jsonify({
                'message': 'Missing required fields',
                'required': required_fields
            }), 400
        
        if not User.query.get(data['host_user_id']):
            return jsonify({
                'message': 'Host user does not exist'
            })        
        
        # Check if organization name already exists
        existing_org = Organization.query.filter_by(name=data['name']).first()
        if existing_org:
            return jsonify({
                'message': 'Organization name already exists'
            }), 400
        
        # Create new organization
        new_org = Organization(
            name=data['name'],
            description=data.get('description', ''),
            member_count=data.get('member_count', 0),
            points=data.get('points', 0),
            type=data.get('type'),
            # auto approve orgs
            # approved=data.get('approved', False),
            approved=True,
            host_user_id=data['host_user_id'],
            date_created=data.get('date_created', '')
        )
        
        db.session.add(new_org)
        db.session.commit()
        
        return jsonify(new_org.serialize()), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to create organization',
            'error': str(e)
        }), 500

@app.route('/api/orgs', methods=['GET'])
@require_auth
def get_organizations():
    """Get all organizations with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        organizations = Organization.query.order_by(Organization.id.desc())
        paginated_orgs = paginate(organizations, page, per_page)
        
        return jsonify({
            'organizations': [org.serialize() for org in paginated_orgs.items],
            'pagination': {
                'page': paginated_orgs.page,
                'per_page': paginated_orgs.per_page,
                'total': paginated_orgs.total
            }
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch organizations',
            'error': str(e)
        }), 500

@app.route('/api/orgs/approved', methods=['GET'])
@require_auth
def get_approved_organizations():
    """Get all approved organizations with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        organizations = Organization.query.filter_by(approved=True).order_by(Organization.id.desc())
        paginated_orgs = paginate(organizations, page, per_page)
        
        return jsonify({
            'organizations': [org.serialize() for org in paginated_orgs.items],
            'pagination': {
                'page': paginated_orgs.page,
                'per_page': paginated_orgs.per_page,
                'total': paginated_orgs.total
            }
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch organizations',
            'error': str(e)
        }), 500


@app.route('/api/orgs/unapproved', methods=['GET'])
@require_auth
def get_unapproved_organizations():
    """Get all unapproved organizations with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        organizations = Organization.query.filter_by(approved=False).order_by(Organization.id.desc())
        paginated_orgs = paginate(organizations, page, per_page)
        
        return jsonify({
            'organizations': [org.serialize() for org in paginated_orgs.items],
            'pagination': {
                'page': paginated_orgs.page,
                'per_page': paginated_orgs.per_page,
                'total': paginated_orgs.total
            }
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch organizations',
            'error': str(e)
        }), 500

@app.route('/api/orgs/<int:org_id>', methods=['GET'])
@require_auth
def get_organization(org_id):
    """Get a single organization"""
    try:
        org = Organization.query.get_or_404(org_id)
        return jsonify(org.serialize())
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch organization',
            'error': str(e)
        }), 500

@app.route('/api/orgs/<int:org_id>', methods=['PUT'])
@require_auth
def update_organization(org_id):
    """Update an organization"""
    try:
        org = Organization.query.get_or_404(org_id)
        data = request.get_json()
        
        # Only update fields that exist in the model
        valid_fields = ['name', 'description', 'member_count', 'points', 'type', 'host_user_id', 'approved', 'date_created']
        for field in valid_fields:
            if field in data:
                setattr(org, field, data[field])
        
        db.session.commit()
        return jsonify(org.serialize())
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to update organization',
            'error': str(e)
        }), 500

@app.route('/api/orgs/<int:org_id>', methods=['DELETE'])
@require_auth
def delete_organization(org_id):
    """Delete an organization"""
    try:
        org = Organization.query.get_or_404(org_id)
        db.session.delete(org)
        db.session.commit()
        return jsonify({
            'message': 'Organization deleted successfully'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to delete organization',
            'error': str(e)
        }), 500

# Opportunity Endpoints
@app.route('/api/opps', methods=['POST'])
@require_auth
def create_opportunity():
    """Create a new opportunity with optional file upload"""
    try:
        # Check if this is a multipart form (file upload) or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file upload
            data = {}
            for field in ['name', 'host_org_id', 'host_user_id', 'date', 'causes', 'tags', 'duration', 'description', 'address', 'nonprofit', 'total_slots', 'image', 'approved', 'host_org_name', 'comments', 'qualifications', 'recurring', 'visibility', 'attendance_marked', 'redirect_url', 'actual_runtime']:
                if field in request.form:
                    if field == 'visibility':
                        data[field] = json.loads(request.form["visibility"])

                    else: 
                        data[field] = request.form[field]
            
        else:
            # Handle JSON data
            data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'host_org_id', 'host_user_id', 'date', 'duration']
        if not all(field in data for field in required_fields):
            return jsonify({
                'message': 'Missing required fields',
                'required': required_fields
            }), 400
        
        # Check if host user exists
        host_user = User.query.get(data['host_user_id'])
        if not host_user:
            return jsonify({
                'message': 'Host user does not exist',
                'error': f'User with ID {data["host_user_id"]} not found'
            }), 404
        
        # Check if host organization exists
        host_org = Organization.query.get(data['host_org_id'])
        if not host_org:
            return jsonify({
                'message': 'Host organization does not exist',
                'error': f'Organization with ID {data["host_org_id"]} not found'
            }), 404
        
        # Set host_org_name from organization if not provided
        if not data.get('host_org_name'):
            data['host_org_name'] = host_org.name
        
        # Parse date with flexible format support
        date_string = data['date'].strip()
        try:
            # Try with seconds first
            parsed_date = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            try:
                # Try without seconds
                parsed_date = datetime.strptime(date_string, '%Y-%m-%dT%H:%M')
            except ValueError:
                return jsonify({
                    'message': 'Invalid date format. Use YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM'
                }), 400
        
        gmt_date = parsed_date + timedelta(hours=4)


        # admin users can create approved opps
        if host_user.admin:
            approved = True
        else:
            approved = False

        print( data.get('multiopp_id', None))
            
        # Create new opportunity
        new_opportunity = Opportunity(
            name=data['name'],
            description=data.get('description'),
            date=gmt_date, 
            duration=data['duration'],
            causes=data.get('causes'),
            tags=data.get('tags', []),
            address=data.get('address'),
            nonprofit=data.get('nonprofit'),
            total_slots=data.get('total_slots'),
            image=data.get('image'),
            host_org_id=data['host_org_id'],
            host_user_id=data['host_user_id'],
            host_org_name=data['host_org_name'],
            comments=data.get('comments', []),
            qualifications=data.get('qualifications', []),
            recurring=data.get('recurring', 'once'),
            visibility=data.get('visibility', []),
            attendance_marked=data.get('attendance_marked', False),
            redirect_url=data.get('redirect_url', None),
            actual_runtime=data.get('actual_runtime', None),
            approved=approved,
            multiopp_id=data.get('multiopp_id', None),
            multiopp=data.get('multiopp', None)
        )
        db.session.add(new_opportunity)
        db.session.commit()

        # mark host as registered with registered=False
        user_opportunity = UserOpportunity(
                        user_id=data['host_user_id'],
                        opportunity_id=new_opportunity.id,
                        registered=False, # Host is initially not registered
                        attended=False  # Match your model field spelling
                    )
        db.session.add(user_opportunity)
        db.session.commit()
            
        return jsonify(new_opportunity.serialize()), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to create opportunity',
            'error': str(e)
        }), 500

@app.route('/api/opps', methods=['GET'])
@require_auth
def get_opportunities():
    """Get all opportunities with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        opportunities = Opportunity.query.order_by(Opportunity.id.desc())
        paginated_opps = paginate(opportunities, page, per_page)
        
        return jsonify({
            'opportunities': [opp.serialize() for opp in paginated_opps.items],
            'pagination': {
                'page': paginated_opps.page,
                'per_page': paginated_opps.per_page,
                'total': paginated_opps.total
            }
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch opportunities',
            'error': str(e)
        }), 500

@app.route('/api/opps/current', methods=['GET'])
@require_auth
def get_current_opportunities():
    """Get current opportunities (whose start dates haven't passed) with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        # Get current datetime
        current_datetime = datetime.utcnow()
        
        # Filter opportunities where date is in the future
        current_opportunities = Opportunity.query.filter(
            Opportunity.date > current_datetime
        ).order_by(Opportunity.date.asc())  # Order by date ascending (earliest first)
        
        paginated_opps = paginate(current_opportunities, page, per_page)
        
        return jsonify({
            'opportunities': [opp.serialize() for opp in paginated_opps.items],
            'pagination': {
                'page': paginated_opps.page,
                'per_page': paginated_opps.per_page,
                'total': paginated_opps.total
            },
            'current_datetime': current_datetime.isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch current opportunities',
            'error': str(e)
        }), 500

@app.route('/api/opps/approved', methods=['GET'])
@require_auth
def get_approved_opportunities():
    """Get approved opportunities with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        # Filter opportunities where approved is True
        approved_opportunities = Opportunity.query.filter(
            Opportunity.approved == True
        ).order_by(Opportunity.id.desc())
        
        paginated_opps = paginate(approved_opportunities, page, per_page)
        
        return jsonify({
            'opportunities': [opp.serialize() for opp in paginated_opps.items],
            'pagination': {
                'page': paginated_opps.page,
                'per_page': paginated_opps.per_page,
                'total': paginated_opps.total
            }
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch approved opportunities',
            'error': str(e)
        }), 500

@app.route('/api/opps/unapproved', methods=['GET'])
@require_auth
def get_unapproved_opportunities():
    """Get unapproved opportunities with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        # Filter opportunities where approved is False
        unapproved_opportunities = Opportunity.query.filter(
            Opportunity.approved == False
        ).order_by(Opportunity.id.desc())
        
        paginated_opps = paginate(unapproved_opportunities, page, per_page)
        
        return jsonify({
            'opportunities': [opp.serialize() for opp in paginated_opps.items],
            'pagination': {
                'page': paginated_opps.page,
                'per_page': paginated_opps.per_page,
                'total': paginated_opps.total
            }
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch unapproved opportunities',
            'error': str(e)
        }), 500

@app.route('/api/opps/active', methods=['GET'])
@require_auth
def get_active_opportunities():
    """Get active opportunities (start date is no more than 24 hours behind current date) with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        # Calculate the cutoff time (24 hours ago from now)
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        # Filter opportunities where date is >= cutoff_time (within last 24 hours)
        active_opportunities = Opportunity.query.filter(
            Opportunity.date >= cutoff_time
        ).order_by(Opportunity.date.asc())  # Order by date ascending (earliest first)
        
        paginated_opps = paginate(active_opportunities, page, per_page)
        
        return jsonify({
            'opportunities': [opp.serialize() for opp in paginated_opps.items],
            'pagination': {
                'page': paginated_opps.page,
                'per_page': paginated_opps.per_page,
                'total': paginated_opps.total
            },
            'cutoff_time': cutoff_time.isoformat(),
            'message': f'Active opportunities from the last 24 hours (since {cutoff_time.strftime("%Y-%m-%d %H:%M:%S")})'
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch active opportunities',
            'error': str(e)
        }), 500

@app.route('/api/opps/<int:opp_id>/phone', methods=['GET'])
@require_auth
def get_involved_users_phone_numbers(opp_id):
    """Get the phone numbers of all users involved in an opportunity"""
    try:
        opp = UserOpportunity.query.filter_by(opportunity_id=opp_id).first().opportunity
        return jsonify([user.phone for user in opp.involved_users])
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch involved users phone numbers',
            'error': str(e)
        }), 500

@app.route('/api/opps/<int:opp_id>/attendance', methods=['GET'])
@require_auth
def get_opportunity_attendance(opp_id):
    """Get all involved user IDs and their attendance status for an opportunity"""
    try:
        # Check if opportunity exists
        opportunity = Opportunity.query.get(opp_id)
        if not opportunity:
            return jsonify({
                'message': 'Opportunity not found',
                'error': f'Opportunity with ID {opp_id} does not exist'
            }), 404
        
        # Get all user opportunities for this opportunity
        user_opportunities = UserOpportunity.query.filter_by(opportunity_id=opp_id).all()
        
        # Build response with user IDs and attendance status
        attendance_data = []
        for uo in user_opportunities:
            attendance_data.append({
                'user_id': uo.user_id,
                'attended': uo.attended,
                'registered': uo.registered,
                'driving': uo.driving
            })
        
        return jsonify({
            'opportunity_id': opp_id,
            'opportunity_name': opportunity.name,
            'total_involved': len(attendance_data),
            'users': attendance_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch opportunity attendance',
            'error': str(e)
        }), 500


@app.route('/api/opps/<int:opp_id>', methods=['GET'])
@require_auth
def get_opportunity(opp_id):
    """Get a single opportunity"""
    try:
        opp = Opportunity.query.get_or_404(opp_id)
        return jsonify(opp.serialize())
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch opportunity',
            'error': str(e)
        }), 500

@app.route('/api/opps/<int:opp_id>/full', methods=['GET'])
def check_opportunity_full(opp_id):
    """Check if opportunity is fully booked"""
    try:
        opportunity = Opportunity.query.get_or_404(opp_id)
        
        # Count the number of users involved in this opportunity
        involved_users_count = UserOpportunity.query.filter_by(opportunity_id=opp_id).count()
        
        # Check if fully booked
        is_full = involved_users_count >= opportunity.total_slots
        
        return jsonify({
            'is_full': is_full
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to check opportunity status',
            'error': str(e)
        }), 500

@app.route('/api/opps/<int:opp_id>', methods=['PUT'])
@require_auth
def update_opportunity(opp_id):
    """Update an opportunity with optional file upload"""
    try:
        opp = Opportunity.query.get_or_404(opp_id)
        points = getattr(opp, "duration", 0) or 0

        # Check if this is a multipart form (file upload) or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file upload
            data = {}
            for field in ['name', 'causes', 'tags', 'description', 'date', 'address', 'approved', 'nonprofit', 'total_slots', 'host_org_id', 'host_user_id', 'host_org_name', 'comments', 'duration','qualifications', 'recurring', 'visibility', 'attendance_marked', 'redirect_url', 'actual_runtime']:
                if field in request.form:
                    data[field] = request.form[field]
                if field == 'date':
                    new_date = datetime.strptime(request.form[field], '%Y-%m-%dT%H:%M:%S') # converts to datetime object
                    new_date = new_date + timedelta(hours=4)
                    setattr(opp, field, new_date)
            
            # Handle image upload
            if 'image' in request.files:
                file = request.files['image']
                image_path = save_opportunity_image(file, opp_id)
                if image_path:
                    data['image'] = image_path
        else:
            # Handle JSON data
            data = request.get_json()
        
        # Only update fields that exist in the model
        valid_fields = ['name', 'duration', 'description', 'date', 'address', 'approved', 'nonprofit', 'total_slots', 'image',
                       'host_org_id', 'host_user_id', 'host_org_name', 'comments', 'qualifications', 'recurring', 'visibility', 'attendance_marked', 'redirect_url', 'actual_runtime', 'tags']       
        
        for field in valid_fields:
            if field in data:
                if(field == 'date'):
                    # Parse date with flexible format support
                    date_string = data['date'].strip()
                    try:
                        # Try with seconds first
                        new_date = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
                    except ValueError:
                        try:
                            # Try without seconds
                            new_date = datetime.strptime(date_string, '%Y-%m-%dT%H:%M')
                        except ValueError:
                            return jsonify({
                                'message': 'Invalid date format. Use YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM'
                            }), 400
                    new_date = new_date.replace(tzinfo=timezone(timedelta(hours=-4)))
                    setattr(opp, field, new_date)
                elif(field == 'host_org_id'): # if host org changes, update this in other models
                    new_host_org_id = data['host_org_id']
                    old_host_org_id = opp.host_org_id
                    
                    # Check if new organization exists
                    new_org = Organization.query.get(new_host_org_id)
                    if not new_org:
                        return jsonify({
                            'message': 'Host organization does not exist',
                            'error': f'Organization with ID {new_host_org_id} not found'
                        }), 404
                    
                    # Simply update the host_org_id field
                    setattr(opp, field, new_host_org_id)
                    
                elif field == 'host_user_id':
                    new_host_user_id = data['host_user_id']
                    old_host_user_id = opp.host_user_id
                    
                    # Check if new user exists
                    new_user = User.query.get(new_host_user_id)
                    if not new_user:
                        return jsonify({
                            'message': 'Host user does not exist',
                            'error': f'User with ID {new_host_user_id} not found'
                        }), 404   

                    if new_host_user_id != old_host_user_id:
                        # Adjust points
                        old_host = User.query.get(old_host_user_id)
                        new_host = User.query.get(new_host_user_id)
                        if old_host:
                            old_host.points = max(0, old_host.points - points)  # prevent negative points
                        if new_host:
                            new_host.points += points

                        # Remove old UserOpportunity
                        old_uo = UserOpportunity.query.filter_by(
                            user_id=old_host_user_id, opportunity_id=opp.id
                        ).first()
                        if old_uo:
                            db.session.delete(old_uo)

                        # Add or update new UserOpportunity
                        new_uo = UserOpportunity.query.filter_by(
                            user_id=new_host_user_id, opportunity_id=opp.id
                        ).first()
                        if not new_uo:
                            new_uo = UserOpportunity(
                                user_id=new_host_user_id,
                                opportunity_id=opp.id,
                                registered=True,
                                attended=True
                            )
                            db.session.add(new_uo)
                        else:
                            new_uo.registered = True
                            new_uo.attended = True
            
                        # Set new host
                        setattr(opp, field, new_host_user_id)
                        db.session.commit()
                else:
                    setattr(opp, field, data[field])
        
        # Commit all changes
        db.session.commit()
        return jsonify(opp.serialize())
    
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to update opportunity',
            'error': str(e)
        }), 500

@app.route('/api/opps/<int:opp_id>', methods=['DELETE'])
@require_auth
def delete_opportunity(opp_id):
    """Delete an opportunity"""
    try:
        opp = Opportunity.query.get_or_404(opp_id)
        db.session.delete(opp)
        db.session.commit()
        return jsonify({
            'message': 'Opportunity deleted successfully'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to delete opportunity',
            'error': str(e)
        }), 500


# Friends Endpoints
@app.route('/api/users/<int:user_id>/friends', methods=['GET'])
@require_auth
def get_user_friends(user_id):
    """Get all accepted friends of a user"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'message': 'User not found',
                'error': f'User with ID {user_id} does not exist'
            }), 404
        
        friends = user.get_accepted_friends()
        
        return jsonify({
            'friends': [
                {
                    'id': friend.id,
                    'name': friend.name,
                    'profile_image': friend.profile_image,
                    'phone': friend.phone,
                    'points': friend.points
                } for friend in friends
            ]
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch friends',
            'error': str(e)
        }), 500

@app.route('/api/users/<int:user_id>/friend-requests', methods=['GET'])
@require_auth
def get_friend_requests(user_id):
    """Get pending friend requests for a user"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'message': 'User not found',
                'error': f'User with ID {user_id} does not exist'
            }), 404
        
        # Get pending requests where user is the receiver
        pending_requests = Friendship.query.filter_by(
            receiver_id=user_id, 
            accepted=False
        ).all()
        
        return jsonify({
            'friend_requests': [
                {
                    'id': request.id,
                    'requester_name': User.query.get(request.requester_id).name,
                    'requester_profile_image': User.query.get(request.requester_id).profile_image
                } for request in pending_requests
            ]
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch friend requests',
            'error': str(e)
        }), 500

@app.route('/api/friendships', methods=['GET'])
@require_auth
def get_all_friendships():
    """Get all friendships in the system (admin endpoint)"""
    try:
        # Get all friendships
        friendships = Friendship.query.all()
        
        return jsonify({
            'friendships': [
                {
                    'id': friendship.id,
                    'accepted': friendship.accepted,
                    'requester_name': User.query.get(friendship.requester_id).name,
                    'receiver_name': User.query.get(friendship.receiver_id).name
                } for friendship in friendships
            ]
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch friendships',
            'error': str(e)
        }), 500

@app.route('/api/users/<int:user_id>/friendships', methods=['GET'])
@require_auth
def get_user_friendships(user_id):
    """Get all friendships for a specific user (both sent and received)"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'message': 'User not found',
                'error': f'User with ID {user_id} does not exist'
            }), 404
        
        # Get all friendships where user is either requester or receiver
        friendships = Friendship.query.filter(
            (Friendship.requester_id == user_id) | (Friendship.receiver_id == user_id)
        ).all()
        
        return jsonify({
            'friendships': [
                {
                    'id': friendship.id,
                    'accepted': friendship.accepted,
                    'requester_name': User.query.get(friendship.requester_id).name,
                    'receiver_name': User.query.get(friendship.receiver_id).name,
                    'is_requester': friendship.requester_id == user_id
                } for friendship in friendships
            ]
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch friendships',
            'error': str(e)
        }), 500

@app.route('/api/users/<int:user_id>/friends', methods=['POST'])
@require_auth
def send_friend_request(user_id):
    """Send a friend request"""
    try:
        data = request.get_json()
        receiver_id = data.get('receiver_id')
        
        if not receiver_id:
            return jsonify({'error': 'receiver_id is required'}), 400
        
        # Check if trying to send request to self
        if user_id == receiver_id:
            return jsonify({'error': 'Cannot send friend request to yourself'}), 400
        
        # Check if users exist
        requester = User.query.get(user_id)
        if not requester:
            return jsonify({
                'message': 'Requester not found',
                'error': f'User with ID {user_id} does not exist'
            }), 404
        
        receiver = User.query.get(receiver_id)
        if not receiver:
            return jsonify({
                'message': 'Receiver not found',
                'error': f'User with ID {receiver_id} does not exist'
            }), 404
        
        # Check if friendship already exists
        existing_friendship = Friendship.query.filter(
            ((Friendship.requester_id == user_id) & (Friendship.receiver_id == receiver_id)) |
            ((Friendship.requester_id == receiver_id) & (Friendship.receiver_id == user_id))
        ).first()
        
        if existing_friendship:
            if existing_friendship.accepted:
                return jsonify({'message': 'Already friends'}), 200
            else:
                return jsonify({'message': 'Friend request already sent'}), 200
        
        # Create new friendship request
        friendship = Friendship(accepted=False)
        friendship.requester_id = user_id
        friendship.receiver_id = receiver_id
        
        db.session.add(friendship)
        db.session.commit()
        
        return jsonify({'message': 'Friend request sent successfully'}), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to send friend request',
            'error': str(e)
        }), 500

@app.route('/api/friendships/<int:friendship_id>/accept', methods=['PUT'])
@require_auth
def accept_friend_request(friendship_id):
    """Accept a friend request"""
    try:
        friendship = Friendship.query.get(friendship_id)
        if not friendship:
            return jsonify({
                'message': 'Friendship not found',
                'error': f'Friendship with ID {friendship_id} does not exist'
            }), 404
        
        if friendship.accepted:
            return jsonify({'message': 'Friend request already accepted'}), 200
        
        friendship.accepted = True
        db.session.commit()
        
        return jsonify({'message': 'Friend request accepted successfully'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to accept friend request',
            'error': str(e)
        }), 500

@app.route('/api/friendships/<int:friendship_id>/reject', methods=['PUT'])
@require_auth
def reject_friend_request(friendship_id):
    """Reject a friend request"""
    try:
        friendship = Friendship.query.get(friendship_id)
        if not friendship:
            return jsonify({
                'message': 'Friendship not found',
                'error': f'Friendship with ID {friendship_id} does not exist'
            }), 404
        
        db.session.delete(friendship)
        db.session.commit()
        
        return jsonify({'message': 'Friend request rejected successfully'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to reject friend request',
            'error': str(e)
        }), 500

@app.route('/api/users/<int:user_id>/friends/<int:friend_id>', methods=['DELETE'])
@require_auth
def remove_friend(user_id, friend_id):
    """Remove a friend (delete friendship)"""
    try:
        # Check if users exist
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'message': 'User not found',
                'error': f'User with ID {user_id} does not exist'
            }), 404
        
        friend = User.query.get(friend_id)
        if not friend:
            return jsonify({
                'message': 'Friend not found',
                'error': f'User with ID {friend_id} does not exist'
            }), 404
        
        # Find the friendship between these users
        friendship = Friendship.query.filter(
            ((Friendship.requester_id == user_id) & (Friendship.receiver_id == friend_id)) |
            ((Friendship.requester_id == friend_id) & (Friendship.receiver_id == user_id))
        ).first()
        
        if not friendship:
            return jsonify({
                'message': 'Friendship not found',
                'error': f'No friendship exists between users {user_id} and {friend_id}'
            }), 404
        
        if not friendship.accepted:
            return jsonify({
                'message': 'Friendship request not yet accepted',
                'error': 'Cannot remove a pending friend request. Use reject instead.'
            }), 400
        
        db.session.delete(friendship)
        db.session.commit()
        
        return jsonify({'message': 'Friend removed successfully'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to remove friend',
            'error': str(e)
        }), 500

@app.route('/api/users/<int:user_id>/friends/check/<int:friend_id>', methods=['GET'])
@require_auth
def check_friendship(user_id, friend_id):
    """Check friendship status between two users"""
    try:
        # Check if users exist
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'message': 'User not found',
                'error': f'User with ID {user_id} does not exist'
            }), 404
        
        friend = User.query.get(friend_id)
        if not friend:
            return jsonify({
                'message': 'Friend not found',
                'error': f'User with ID {friend_id} does not exist'
            }), 404
        
        # Find the friendship between these users
        friendship = Friendship.query.filter(
            ((Friendship.requester_id == user_id) & (Friendship.receiver_id == friend_id)) |
            ((Friendship.requester_id == friend_id) & (Friendship.receiver_id == user_id))
        ).first()
        
        if not friendship:
            return jsonify({
                'status': 'no_friendship',
                'are_friends': False,
                'user_id': user_id,
                'friend_id': friend_id
            })
        
        if friendship.accepted:
            return jsonify({
                'status': 'friends',
                'are_friends': True,
                'user_id': user_id,
                'friend_id': friend_id
            })
        else:
            # Check who sent the request
            if friendship.requester_id == user_id:
                return jsonify({
                    'status': 'request_sent',
                    'are_friends': False,
                    'user_id': user_id,
                    'friend_id': friend_id
                })
            else:
                return jsonify({
                    'status': 'request_received',
                    'are_friends': False,
            'user_id': user_id,
            'friend_id': friend_id
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to check friendship',
            'error': str(e)
        }), 500

@app.route('/api/users/<int:user_id>/friendships/all', methods=['GET'])
@require_auth
def get_all_user_friendships(user_id):
    """Get friendship relationship status between user A and all other users"""
    try:
        # Check if user exists
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'message': 'User not found',
                'error': f'User with ID {user_id} does not exist'
            }), 404
        
        # Get all users except the current user
        all_users = User.query.filter(User.id != user_id).all()
        
        # Get all friendships involving the current user
        user_friendships = Friendship.query.filter(
            (Friendship.requester_id == user_id) | (Friendship.receiver_id == user_id)
        ).all()
        
        # Create maps for friendship status and friendship ID
        friendship_map = {}
        friendship_id_map = {}
        for friendship in user_friendships:
            if friendship.requester_id == user_id:
                # User A is requester to user B
                other_user_id = friendship.receiver_id
                if friendship.accepted:
                    friendship_map[other_user_id] = "friends"
                else:
                    friendship_map[other_user_id] = "sent"
                friendship_id_map[other_user_id] = friendship.id
            else:
                # User B is requester to user A
                other_user_id = friendship.requester_id
                if friendship.accepted:
                    friendship_map[other_user_id] = "friends"
                else:
                    friendship_map[other_user_id] = "received"
                friendship_id_map[other_user_id] = friendship.id
        
        # Build response with all users and their friendship status
        users_with_friendship_status = []
        for other_user in all_users:
            friendship_status = friendship_map.get(other_user.id, "add")
            friendship_id = friendship_id_map.get(other_user.id, None)
            
            users_with_friendship_status.append({
                'user_id': other_user.id,
                'name': other_user.name,
                'profile_image': other_user.profile_image,
                'email': other_user.email,
                'friendship_status': friendship_status,
                'friendship_id': friendship_id
            })
        
        return jsonify({
            'current_user_id': user_id,
            'users': users_with_friendship_status,
            'total_users': len(users_with_friendship_status)
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch user friendships',
            'error': str(e)
        }), 500


@app.route('/api/protected', methods=['POST'])
def protected_endpoint():
    """Protected endpoint that requires Firebase token verification"""
    try:
        # Get the Authorization header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                'error': 'Authorization header is required',
                'message': 'Please provide a valid Firebase ID token'
            }), 401
        
        # Check if it's a Bearer token
        if not auth_header.startswith('Bearer '):
            return jsonify({
                'error': 'Invalid authorization format',
                'message': 'Authorization header must be in format: Bearer <token>'
            }), 401
        
        # Extract the token
        token = auth_header.split('Bearer ')[1]
        
        if not token:
            return jsonify({
                'error': 'Token is required',
                'message': 'Please provide a valid Firebase ID token'
            }), 401
        
        # Verify the token
        verification_result = verify_firebase_token(token)
        
        if not verification_result['success']:
            return jsonify({
                'error': 'Invalid token',
                'message': 'The provided token is invalid or expired',
                'details': verification_result.get('error', 'Unknown error')
            }), 401
        
        # Token is valid, return user information
        return jsonify({
            'message': 'Token verified successfully',
            'user': {
                'uid': verification_result['user_id'],
                'email': verification_result['email'],
                'name': verification_result['name'],
                'picture': verification_result['picture']
            },
            'status': 'authenticated'
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': 'An error occurred while verifying the token',
            'details': str(e)
        }), 500


@app.route('/api/firebase-status', methods=['GET'])
def firebase_status():
    """Check Firebase configuration status"""
    try:
        # Check if Firebase is properly initialized
        if firebase_admin._apps:
            return jsonify({
                'status': 'Firebase Admin SDK is initialized',
                'message': 'Firebase authentication is available',
                'apps_count': len(firebase_admin._apps)
            }), 200
        else:
            return jsonify({
                'status': 'Firebase Admin SDK is not initialized',
                'message': 'Firebase authentication is not available',
                'error': 'No Firebase apps found'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'Firebase Admin SDK error',
            'message': 'Firebase authentication is not available',
            'error': str(e)
        }), 500

@app.route('/api/me', methods=['GET'])
@require_auth
def get_current_user():
    """Get current authenticated user information"""
    try:
        # request.user contains the authenticated user info from the token
        return jsonify({
            'message': 'Current user information',
            'user': request.user
        }), 200
    except Exception as e:
        return jsonify({
            'error': 'Failed to get user information',
            'details': str(e)
        }), 500

@app.route("/upload", methods=["POST"])
def upload():
    """Upload file to S3"""
    try:
        file = request.files["file"]

        # Extract safe extension (e.g. ".jpg")
        _, ext = os.path.splitext(secure_filename(file.filename))

        # Generate unique filename with UUID
        unique_filename = f"{uuid.uuid4()}{ext}"

        # Upload to S3
        s3.upload_fileobj(
            file,
            S3_BUCKET,
            unique_filename,
            ExtraArgs={"ContentType": file.content_type}
        )

        # Public URL of the file
        url = f"https://{S3_BUCKET}.s3.amazonaws.com/{unique_filename}"
        return {"url": url}
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to upload file to S3',
            'error': str(e)
        }), 500

# Approved Email Management Endpoints

@app.route('/api/approved-emails', methods=['POST'])
@require_auth
def create_approved_email():
    """Create a new approved email entry"""
    try:
        data = request.get_json()
        
        if not data or 'email' not in data:
            return jsonify({
                'error': 'Email is required',
                'message': 'Please provide an email address'
            }), 400
        
        email = data['email'].strip().lower()
        
        # Check if email already exists
        existing_email = ApprovedEmail.query.filter_by(email=email).first()
        if existing_email:
            return jsonify({
                'error': 'Email already approved',
                'message': f'Email {email} is already in the approved list'
            }), 409
        
        # Create new approved email
        approved_email = ApprovedEmail(
            email=email,
            added_by_admin=data.get('added_by_admin', 'admin')
        )
        
        db.session.add(approved_email)
        db.session.commit()
        
        return jsonify({
            'message': 'Email approved successfully',
            'approved_email': approved_email.serialize()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to create approved email',
            'message': str(e)
        }), 500

@app.route('/api/approved-emails/<int:email_id>', methods=['DELETE'])
@require_auth
def delete_approved_email(email_id):
    """Delete an approved email entry"""
    try:
        approved_email = ApprovedEmail.query.get(email_id)
        
        if not approved_email:
            return jsonify({
                'error': 'Approved email not found',
                'message': f'No approved email found with ID {email_id}'
            }), 404
        
        email_address = approved_email.email
        db.session.delete(approved_email)
        db.session.commit()
        
        return jsonify({
            'message': 'Approved email deleted successfully',
            'deleted_email': email_address
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to delete approved email',
            'message': str(e)
        }), 500

@app.route('/api/approved-emails/check/<email>', methods=['GET'])
def check_email_approval(email):
    """Check if an email is approved"""
    try:
        # Normalize the email (lowercase, trimmed)
        normalized_email = email.strip().lower()
        
        # Check if email exists in approved list
        approved_email = ApprovedEmail.query.filter_by(email=normalized_email).first()
        
        is_approved = approved_email is not None
        
        response_data = {
            'email': normalized_email,
            'is_approved': is_approved
        }
        
        # If approved, include additional details
        if is_approved:
            response_data['approved_details'] = approved_email.serialize()
        
        return jsonify({
            'message': 'Email approval status checked successfully',
            **response_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to check email approval',
            'message': str(e)
        }), 500

@app.route('/api/generate-schema', methods=['POST'])
def generate_random_schema():
    """Generate a random database schema with users, orgs, opportunities, and friend requests"""
    try:
        
        # Sample data for generation
        first_names = ["Alex", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Avery", "Quinn", "Sage", "River"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        universities = ["Harvard", "Stanford", "MIT", "Yale", "Princeton", "Columbia", "Duke", "Northwestern", "Brown", "Dartmouth"]
        companies = ["Google", "Microsoft", "Apple", "Amazon", "Meta", "Tesla", "Netflix", "Uber", "Airbnb", "Spotify"]
        
        org_types = ["Academic", "Professional", "Social", "Service", "Cultural"]
        causes = ["Education", "Environment", "Healthcare", "Poverty", "Animal Welfare", "Arts", "Sports", "Technology"]
        locations = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego"]
        
        generated_data = {
            "users": [],
            "organizations": [],
            "opportunities": [],
            "friend_requests": []
        }
        
        # 1. Generate 5 users
        users = []  # Store users in a list
        for i in range(5):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            university = random.choice(universities)
            
            user = User(
                name=f"{first_name} {last_name}",
                email=f"{first_name.lower()}.{last_name.lower()}@{university.lower()}.edu",
                phone=f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                points=random.randint(0, 500),
                interests=random.sample(causes, random.randint(1, 3)),
                admin=random.choice([True, False]),
                gender=random.choice(["Male", "Female", "Non-binary", "Prefer not to say"]),
                graduation_year=str(random.randint(2024, 2028)),
                academic_level=random.choice(["Undergraduate", "Graduate", "PhD"]),
                major=random.choice(["Computer Science", "Business", "Engineering", "Medicine", "Law", "Arts"]),
                birthday=datetime.now() - timedelta(days=random.randint(6570, 10950)),  # 18-30 years old
                car_seats=random.randint(0, 7),
                bio=None
            )
            
            db.session.add(user)
            db.session.flush()  # Get the ID
            users.append(user)  # Add to our list
            generated_data["users"].append(user.serialize())
        
        # 2. Generate 5 organizations, approve 3
        organizations = []  # Store orgs in a list
        for i in range(5):
            org_type = random.choice(org_types)
            company = random.choice(companies)
            
            org = Organization(
                name=f"{company} {org_type} Society",
                description=f"A {org_type.lower()} organization focused on professional development and networking in the {company} ecosystem.",
                member_count=random.randint(10, 200),
                points=random.randint(50, 1000),
                type=org_type,
                approved=i < 3,  # First 3 are approved
                date_created=""
            )
            
            db.session.add(org)
            db.session.flush()  # Get the ID
            organizations.append(org)  # Add to our list
            generated_data["organizations"].append(org.serialize())
        
        db.session.commit()
        # 3. Generate 5 opportunities, approve 3
        for i in range(5):
            causes = random.choice(causes)
            location = random.choice(locations)
            org = organizations[i % 5]  # Use our list instead of querying
            
            # Random date between now and 3 months from now
            start_date = datetime.now() + timedelta(days=random.randint(1, 90))
            
            opportunity = Opportunity(
                name=f"{causes} Volunteer Event in {location}",
                description=f"Join us for a meaningful {causes.lower()} volunteer opportunity in {location}. Help make a difference in your community while meeting like-minded individuals.",
                date=start_date,
                duration=random.choice([60, 120, 180, 240, 480]),  # 1-8 hours
                causes=causes,
                tags=random.sample(["volunteer", "community", "service", "outdoor", "indoor", "teamwork", "leadership", "creative"], random.randint(1, 3)),
                address=f"{random.randint(100, 9999)} {random.choice(['Main St', 'Oak Ave', 'Pine Rd', 'Elm Blvd'])} {location}",
                nonprofit=random.choice(["Local Food Bank", "Habitat for Humanity", "Red Cross", "United Way", "Boys & Girls Club"]),
                total_slots=random.randint(5, 50),
                approved=i < 3,  # First 3 are approved
                host_org_id=org.id,
                host_org_name=org.name,
                comments=[],
                qualifications=random.sample(["No experience required", "Background check needed", "Must be 18+", "Physical activity involved"], random.randint(1, 3)),
                recurring=random.choice(["once", "weekly", "monthly"]),
                visibility=[],
                attendance_marked=False,
                redirect_url=None,
                actual_runtime=None
            )
            
            db.session.add(opportunity)
            db.session.flush()  # Get the ID
            generated_data["opportunities"].append(opportunity.serialize())
        
        # Commit users, orgs, and opportunities first
        db.session.commit()
        with db.session.no_autoflush:   # 👈 Prevent autoflush while querying
            all_users = User.query.all()
        
        # 4. Generate 4 friend requests between users
        # 4. Generate 4 friend requests between users
        friend_requests_created = 0

        while friend_requests_created < 4:
            requester = random.choice(users)   # ✅ use the in-memory list
            receiver = random.choice(users)

            if requester.id == receiver.id:
                continue

            # check duplicates manually
            exists = any(
                (fr["requester"] == requester.name and fr["receiver"] == receiver.name) or
                (fr["requester"] == receiver.name and fr["receiver"] == requester.name)
                for fr in generated_data["friend_requests"]
            )
            if exists:
                continue

            friendship = Friendship(
                requester_id=requester.id,
                receiver_id=receiver.id,
                accepted=random.choice([True, False])
            )

            db.session.add(friendship)
            friend_requests_created += 1

            generated_data["friend_requests"].append({
                "requester": requester.name,
                "receiver": receiver.name,
                "accepted": friendship.accepted
            })

        # Final commit
        db.session.commit()

        
        return jsonify({
            'message': 'Random database schema generated successfully',
            'generated_data': generated_data,
            'summary': {
                'users_created': len(generated_data["users"]),
                'organizations_created': len(generated_data["organizations"]),
                'organizations_approved': len([org for org in generated_data["organizations"] if org["approved"]]),
                'opportunities_created': len(generated_data["opportunities"]),
                'opportunities_approved': len([opp for opp in generated_data["opportunities"] if opp["approved"]]),
                'friend_requests_created': len(generated_data["friend_requests"])
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to generate random schema',
            'message': str(e)
        }), 500

@app.route('/api/monthly-points', methods=['GET'])
@require_auth
def get_monthly_points():
    """Get all users and their points earned from a given date to present"""
    try:
        # Get the date from query parameters
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({
                'error': 'Date parameter is required',
                'message': 'Please provide a date in YYYY-MM-DD format'
            }), 400
        
        # Parse the date
        try:
            from_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'error': 'Invalid date format',
                'message': 'Date must be in YYYY-MM-DD format'
            }), 400
        
        # Get all users
        users = User.query.all()
        user_points = []
        
        for user in users:
            total_points = 0
            
            # Get all user opportunities where user attended
            user_opportunities = UserOpportunity.query.filter_by(
                user_id=user.id,
                attended=True
            ).all()
            
            for uo in user_opportunities:
                opportunity = uo.opportunity
                
                # Check if opportunity date is on or after the given date
                if opportunity.date >= from_date:
                    # Use actual_runtime if available, otherwise use duration
                    if opportunity.actual_runtime is not None:
                        total_points += opportunity.actual_runtime
                    else:
                        total_points += opportunity.duration
            
            user_points.append({
                'id': user.id,
                'points': total_points
            })
        
        return jsonify({
            'users': user_points
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to calculate monthly points',
            'message': str(e)
        }), 500


@app.route('/api/users/csv', methods=['GET'])
@require_auth
def get_users_csv():
    """Return users as CSV attachment with requested columns."""
    try:

        users = User.query.all()

        si = io.StringIO()
        writer = csv.writer(si)

        # header
        writer.writerow([
            'friend_count',
            'opportunities_registered',
            'opportunities_attended',
            'opportunities_hosted',
            'organizations_hosted',
            'car_seats',
            'points',
            'registration_date',
            'graduation_year',
            'has_bio',
            'has_profile_image'
        ])

        for user in users:
            friend_count = len(user.get_accepted_friends())
            opp_registered = sum(1 for uo in user.user_opportunities if getattr(uo, 'registered', False))
            opp_attended = sum(1 for uo in user.user_opportunities if getattr(uo, 'attended', False))
            opp_hosted = len(user.opportunities_hosted or [])
            # organizations hosted: organizations where this user is host_user
            organizations_hosted = Organization.query.filter_by(host_user_id=user.id).count()
            car_seats = user.car_seats if user.car_seats is not None else 0
            points = user.points if user.points is not None else 0
            registration_date = user.registration_date.isoformat() if getattr(user, 'registration_date', None) else ''
            graduation_year = user.graduation_year or ''
            has_bio = bool(user.bio)
            has_profile_image = bool(user.profile_image)

            writer.writerow([
                friend_count,
                opp_registered,
                opp_attended,
                opp_hosted,
                organizations_hosted,
                car_seats,
                points,
                registration_date,
                graduation_year,
                int(has_bio),
                int(has_profile_image),
            ])

        output = si.getvalue()
        si.close()

        response = make_response(output)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename="data.csv"'
        return response

    except Exception as e:
        return jsonify({'error': 'Failed to generate users CSV', 'message': str(e)}), 500


@app.route('/api/opps/csv', methods=['GET'])
@require_auth
def get_opps_csv():
    """Return opportunities as CSV attachment with requested columns."""
    try:
        opps = Opportunity.query.all()

        si = io.StringIO()
        writer = csv.writer(si)

        writer.writerow([
            'duration',
            'actual_runtime',
            'total_slots',
            'total_attended',
            'total_registered',
            'address',
            'date',
            'num_comments',
            'approved',
            'has_image',
            'has_description'
        ])

        for opp in opps:
            duration = opp.duration
            actual_runtime = opp.actual_runtime if opp.actual_runtime is not None else ''
            total_slots = opp.total_slots if opp.total_slots is not None else ''
            total_attended = sum(1 for uo in (opp.user_opportunities or []) if getattr(uo, 'attended', False))
            total_registered = sum(1 for uo in (opp.user_opportunities or []) if getattr(uo, 'registered', False))
            address = opp.address or ''
            date = opp.date.isoformat() if getattr(opp, 'date', None) else ''
            num_comments = len(opp.comments or [])
            approved = bool(opp.approved)
            has_image = int(bool(opp.image))
            has_description = int(bool(opp.description))

            writer.writerow([
                duration,
                actual_runtime,
                total_slots,
                total_attended,
                total_registered,
                address,
                date,
                num_comments,
                int(approved),
                has_image,
                has_description,
            ])

        output = si.getvalue()
        si.close()

        response = make_response(output)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename="data.csv"'
        return response

    except Exception as e:
        return jsonify({'error': 'Failed to generate opportunities CSV', 'message': str(e)}), 500

# Waiver endpoints
@app.route('/api/waivers/create-waiver', methods=['POST', 'OPTIONS'])
@require_auth
def create_waiver():
    """Create a new waiver"""
    try:
        data = request.get_json()
        
        required_fields = ['typed_name', 'type', 'content', 'checked_consent', 'user_id']
        if not all(field in data for field in required_fields):
            return jsonify({
                'message': 'Missing required fields',
                'required': required_fields
            }), 400
        
        user = User.query.get(data['user_id'])

        if not user:
            return jsonify({
                'message': 'User does not exist'
            })        
        
        ip = request.remote_addr

        new_waiver = Waiver(
            typed_name=data.get('typed_name'),
            type=data.get('type'),
            content=data.get('content'),
            checked_consent=data.get('checked_consent'),
            ip_address=ip,
            user_id=data.get('user_id'),
            organization_id=data.get('organization_id')
        )
        
        db.session.add(new_waiver)
        user.carpool_waiver_signed = True
        db.session.commit()
        
        return jsonify(new_waiver.serialize()), 201
    
    except Exception as e:
        db.session.rollback()
        print("Error in /api/waivers/create-waiver:")
        traceback.print_exc()
        return jsonify({
            'message': 'Failed to create waiver',
            'error': str(e)
        }), 500
    
# SERVICE JOURNAL ENDPOINTS
@app.route('/api/service-journal/opps/<int:user_id>', methods=['GET'])
@require_auth
def service_opps(user_id):
    # Query only the columns you need — no model overhead
    rows = (
        db.session.query(
            Opportunity.name,
            Opportunity.date,
            UserOpportunity.driving,
            Opportunity.host_user_id,
            Opportunity.duration,
            UserOpportunity.attended
        )
        .join(UserOpportunity, UserOpportunity.opportunity_id == Opportunity.id)
        .filter(UserOpportunity.user_id == user_id)
        .all()
    )

    # Convert results to JSON-serializable dicts
    result = [
        {
            "name": name,
            "date": date,
            "driver": driving,
            "host": (host_user_id == user_id),
            "duration": duration,
            "attended": attended
        }
        for name, date, driving, host_user_id, duration, attended in rows
    ]

    return jsonify(result), 200

@app.route('/api/service-journal/opps/<int:user_id>/csv', methods=['GET'])
@require_auth
def service_opps_csv(user_id):
    """
    Return opportunities as CSV attachment with requested columns.
    """
    # Query only the needed columns efficiently
    stmt = (
        select(
            Opportunity.name,
            Opportunity.date,
            UserOpportunity.driving,
            Opportunity.host_user_id,
            Opportunity.duration,
            UserOpportunity.attended
        )
        .join(UserOpportunity, UserOpportunity.opportunity_id == Opportunity.id)
        .filter(UserOpportunity.user_id == user_id)
    )
    rows = db.session.execute(stmt).all()

    # Create an in-memory CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "date", "driver", "host", "duration", "attended"])  # header row

    for name, date, driving, host_user_id, duration, attended in rows:
        writer.writerow([
            name,
            date.isoformat() if date else "",
            "true" if driving else "false",
            "host" if host_user_id == user_id else "participant",
            duration,
            "true" if attended else "false"
        ])

    csv_data = output.getvalue()
    output.close()

    # Build HTTP response
    response = make_response(csv_data)
    
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; ffilename=service_opps_user_{user_id}.csv'

    return response

from flask import Blueprint, request, Response
from datetime import date, timedelta
from sqlalchemy import and_
import io, csv


@app.route("/api/service-data/org/", methods=["POST"])
@require_auth
def org_service_data_csv():
    data = request.get_json()
    start_date = date.fromisoformat(data["start_date"])
    end_date = date.fromisoformat(data["end_date"])

    # Align to full week range (Mon–Sun)
    start_date -= timedelta(days=start_date.weekday())
    end_date += timedelta(days=(6 - end_date.weekday()))

    # Get all attended user–opportunity pairs in the range
    rows = (
        db.session.query(
            User.id.label("user_id"),
            Opportunity.date.label("date"),
            Opportunity.duration.label("duration")
        )
        .join(UserOpportunity, User.id == UserOpportunity.user_id)
        .join(Opportunity, Opportunity.id == UserOpportunity.opportunity_id)
        .filter(
            and_(
                UserOpportunity.attended == True,
                Opportunity.date >= start_date,
                Opportunity.date <= end_date
            )
        )
        .all()
    )

    # Get mapping of user → orgs (to avoid querying repeatedly)
    user_org_map = {
        u.id: [(org.id, org.name) for org in u.organizations]
        for u in db.session.query(User).options(db.joinedload(User.organizations)).all()
    }

    # Define weekly bins
    num_weeks = ((end_date - start_date).days // 7) + 1
    week_bins = [
        (start_date + timedelta(days=i*7), start_date + timedelta(days=i*7 + 6))
        for i in range(num_weeks)
    ]
    week_labels = [f"{ws:%b %d}–{we:%b %d}" for ws, we in week_bins]

    # Aggregate totals: {org_id: {week_label: total_hours}}
    table = {}

    for row in rows:
        user_orgs = user_org_map.get(row.user_id, [])
        for (week_start, week_end) in week_bins:
            if week_start <= row.date.date() <= week_end:
                week_label = f"{week_start:%b %d}–{week_end:%b %d}"
                for org_id, org_name in user_orgs:
                    table.setdefault((org_id, org_name), {}).setdefault(week_label, 0)
                    table[(org_id, org_name)][week_label] += row.duration
                break

    # --- Build CSV ---
    output = io.StringIO()
    writer = csv.writer(output)
    header = ["Organization ID", "Organization Name"] + week_labels
    writer.writerow(header)

    for (org_id, org_name), weekly_data in table.items():
        row = [org_id, org_name]
        for label in week_labels:
            row.append(round(weekly_data.get(label, 0), 2))
        writer.writerow(row)

    csv_data = output.getvalue()
    output.close()

    filename = f"org_service_data_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )



def generate_opportunities_from_multiopp(multiopp: MultiOpportunity, data: dict):
    """Generate individual opportunities from a MultiOpportunity recurrence pattern."""
    from datetime import datetime, timedelta
    import pytz

    all_opps = []
    start_date = multiopp.start_date

    eastern = pytz.timezone("US/Eastern")

    # Flatten day/time mapping list into (weekday, [(time_str, duration), ...]) pairs
    day_time_pairs = []
    for entry in multiopp.days_of_week:
        for weekday, time_list in entry.items():
            day_time_pairs.append((weekday, time_list))

    total_weeks = multiopp.week_recurrences or 4
    week_frequency = multiopp.week_frequency or 1

    for week_index in range(total_weeks):
        # Handle every Nth week (e.g., every 2 weeks)
        if week_frequency > 1 and week_index % week_frequency != 0:
            continue

        base_week_start = start_date + timedelta(weeks=week_index)

        for weekday_name, time_list in day_time_pairs:
            weekday_index = [
                "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
            ].index(weekday_name)
            day_date = base_week_start + timedelta(days=(weekday_index - base_week_start.weekday()) % 7)

            for time_entry in time_list:
                # Each entry is a tuple or list: (start_time_str, duration)
                if isinstance(time_entry, (list, tuple)) and len(time_entry) == 2:
                    start_time_str, duration = time_entry
                else:
                    start_time_str, duration = time_entry, 60

                # Parse "HH:MM" or ISO "T" time
                start_time = (
                    datetime.fromisoformat(start_time_str).time()
                    if "T" in start_time_str
                    else datetime.strptime(start_time_str, "%H:%M").time()
                )

                # Combine with date (naive datetime)
                naive_dt = datetime.combine(day_date.date(), start_time)

                # ✅ Localize to Eastern time, then convert to UTC for DB storage
                localized_dt = eastern.localize(naive_dt)
                dt_utc = localized_dt.astimezone(pytz.utc)

                opp = Opportunity(
                    name=data["name"],
                    description=data.get("description"),
                    causes=data.get("causes", []),
                    tags=data.get("tags", []),
                    address=data["address"],
                    nonprofit=data.get("nonprofit"),
                    image=data.get("image"),
                    approved=data.get("approved", False),
                    host_org_name=data.get("host_org_name"),
                    qualifications=data.get("qualifications", []),
                    visibility=data.get("visibility", []),
                    host_org_id=data.get("host_org_id"),
                    host_user_id=data.get("host_user_id"),
                    redirect_url=data.get("redirect_url"),
                    total_slots=data.get("total_slots"),

                    # Recurrence-specific fields
                    date=dt_utc,  # store in UTC
                    duration=duration,
                    recurring="recurring",
                    comments=[],
                    attendance_marked=False,
                    actual_runtime=None,

                    # Relationship
                    multiopp_id=multiopp.id,
                    multi_opportunity=multiopp,
                )

                db.session.add(opp)
                all_opps.append(opp)

    db.session.commit()
    return all_opps



@app.route("/api/multiopps", methods=["POST"])
@require_auth
def create_multiopp():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
        # Parse JSON-like fields manually
        if "days_of_week" in data:
            data["days_of_week"] = json.loads(data["days_of_week"])
        if "week_frequency" in data:
            data["week_frequency"] = int(data["week_frequency"])
        if "week_recurrences" in data:
            data["week_recurrences"] = int(data["week_recurrences"])
        if "approved" in data:
            data["approved"] = data["approved"].lower() == "true"


    # Step 1: Create MultiOpportunity (recurrence definition)
    multiopp = MultiOpportunity(
        name=data["name"],
        description=data.get("description"),
        causes=data.get("causes", []),
        tags=data.get("tags", []),
        address=data["address"],
        nonprofit=data.get("nonprofit"),
        image=data.get("image"),
        approved=data.get("approved", False),
        host_org_name=data.get("host_org_name"),
        qualifications=data.get("qualifications", []),
        visibility=data.get("visibility", []),
        host_org_id=data.get("host_org_id"),
        host_user_id=data.get("host_user_id"),
        redirect_url=data.get("redirect_url"),
        total_slots=data.get("total_slots"),

        start_date=datetime.fromisoformat(data["start_date"]),
        days_of_week=data["days_of_week"],
        week_frequency=data.get("week_frequency"),
        week_recurrences=data.get("week_recurrences", 4)
    )

    db.session.add(multiopp)
    db.session.commit()

    # Step 2: Generate the actual individual Opportunities
    generated_opps = generate_opportunities_from_multiopp(multiopp, data)

    # Step 3: Return serialized MultiOpportunity and its generated Opportunities
    return jsonify({
        "multiopp": multiopp.serialize(),
        "generated_opportunities": [opp.serialize() for opp in generated_opps]
    }), 201

# 🟡 GET ALL multiopps
@app.route("/api/multiopps", methods=["GET"])
@require_auth
def get_all_multiopps():
    multiopps = MultiOpportunity.query.all()
    return jsonify([m.serialize() for m in multiopps]), 200


# 🟢 GET SINGLE multiopp by ID
@app.route("/api/multiopps/<int:multiopp_id>", methods=["GET"])
@require_auth
def get_multiopp(multiopp_id):
    multiopp = MultiOpportunity.query.get_or_404(multiopp_id)
    return jsonify(multiopp.serialize()), 200


# 🔴 DELETE multiopp by ID
@app.route("/api/multiopps/<int:multiopp_id>", methods=["DELETE"])
@require_auth
def delete_multiopp(multiopp_id):
    multiopp = MultiOpportunity.query.get_or_404(multiopp_id)

    # Optional: Delete all linked individual opportunities first, if cascade isn’t set up
   

    db.session.delete(multiopp)
    db.session.commit()
    return jsonify({"message": f"MultiOpportunity {multiopp_id} deleted successfully."})

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host="0.0.0.0", port=port, debug=False)