import json
import os
import uuid
from flask import Flask, request, jsonify, send_from_directory
from db import db, User, Organization, Opportunity, UserOpportunity, Friendship

from datetime import datetime, timedelta, timezone
from flask_cors import CORS
from werkzeug.utils import secure_filename
import firebase_admin
from firebase_admin import auth, credentials, initialize_app
from dotenv import load_dotenv
import boto3

# define db filename
db_filename = "cucares.db"
app = Flask(__name__)

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Load environment variables from .env file
load_dotenv()

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

# restrict API access to requests from secure origin
CORS(app, origins=["https://campuscares.us", "https://www.campuscares.us"])

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

# setup config
database_url = os.environ.get('DATABASE_URL', f"sqlite:///{db_filename}")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
# For psycopg3, ensure we're using the correct driver
if "postgresql://" in database_url and "psycopg" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = os.environ.get('FLASK_ENV') == 'development'

# initialize app
db.init_app(app)
with app.app_context():
    db.create_all()

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
    def decorated_function(*args, **kwargs):
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

# Special Endpoints
@app.route('/api/register-opp', methods=['POST'])
@require_auth
def register_user_for_opportunity():
    data = request.get_json()
    user_id = data.get('user_id')
    opportunity_id = data.get('opportunity_id')

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
            attended=False  # default
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
    user_id = data.get('user_id')
    opportunity_id = data.get('opportunity_id')

    if not user_id or not opportunity_id:
        return jsonify({"error": "user_id and opportunity_id are required"}), 400

    try:
        user = User.query.get(user_id)
        opp = Opportunity.query.get(opportunity_id)

        if not user or not opp:
            return jsonify({"error": "Invalid user_id or opportunity_id"}), 404

        opp_dur = getattr(opp, 'duration', 0) or 0  # fallback if duration is None

        existing = UserOpportunity.query.filter_by(user_id=user_id, opportunity_id=opportunity_id).first()
        
        if existing:
            if not existing.attended:
                existing.attended = True
                user.points += opp_dur
                db.session.commit()
                return jsonify({"message": "Attendance updated & points awarded"}), 200
            else:
                return jsonify({"message": "User already marked as attended"}), 200

        # If not already registered, create new entry and mark as attended
        user_opportunity = UserOpportunity(
            user_id=user_id,
            opportunity_id=opportunity_id,
            registered=False,
            attended=True
        )
        db.session.add(user_opportunity)
        user.points += opp_dur
        db.session.commit()
        return jsonify({"message": "Marked as attended and registered, points awarded"}), 201

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
                'car_seats': car_seats
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
            birthday=birthday
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

@app.route('/api/users', methods=['GET'])
@require_auth
def get_users():
    """Get all users with full details - requires authentication"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
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
        return jsonify(user.serialize())
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch user',
            'error': str(e)
        }), 500

@app.route('/api/users/email/<email>', methods=['GET'])
def get_user_by_email(email):
    """Get user by email - Login only: Quick check if user exists with minimal data"""
    try:
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({
                'message': 'User not found',
                'exists': False
            }), 404
        
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
            for field in ['name', 'car_seats', 'email', 'phone', 'points', 'admin', 'gender', 'graduation_year', 'academic_level', 'major', 'birthday']:
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
        valid_fields = ['profile_image', 'name', 'email', 'phone', 'points', 'interests', 'admin', 'gender', 'graduation_year', 'academic_level', 'major', 'birthday']
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
            approved=data.get('approved', False),
            host_user_id=data['host_user_id']
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
        per_page = int(request.args.get('per_page', 20))
        
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
        per_page = int(request.args.get('per_page', 20))
        
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
        per_page = int(request.args.get('per_page', 20))
        
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
        valid_fields = ['name', 'description', 'member_count', 'points', 'type', 'host_user_id', 'approved']
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
            for field in ['name', 'host_org_id', 'host_user_id', 'date', 'causes', 'duration', 'description', 'address', 'nonprofit', 'total_slots', 'image', 'approved', 'host_org_name', 'comments', 'qualifications', 'recurring']:
                if field in request.form:
                    data[field] = request.form[field]
            
        else:
            # Handle JSON data
            data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'host_org_id', 'host_user_id', 'date', 'causes', 'duration']
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

        # Create new opportunity
        new_opportunity = Opportunity(
            name=data['name'],
            description=data.get('description'),
            date=gmt_date, 
            duration=data['duration'],
            causes=data.get('causes'),
            address=data.get('address'),
            nonprofit=data.get('nonprofit'),
            total_slots=data.get('total_slots'),
            image=data.get('image'),
            host_org_id=data['host_org_id'],
            host_user_id=data['host_user_id'],
            host_org_name=data['host_org_name'],
            comments=data.get('comments', []),
            qualifications=data.get('qualifications', []),
            recurring=data.get('recurring', 'once')
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
        per_page = int(request.args.get('per_page', 20))
        
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
        per_page = int(request.args.get('per_page', 20))
        
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
        per_page = int(request.args.get('per_page', 20))
        
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
        per_page = int(request.args.get('per_page', 20))
        
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
            for field in ['name', 'description', 'date', 'address', 'approved', 'nonprofit', 'total_slots', 'host_org_id', 'host_user_id', 'host_org_name', 'comments', 'qualifications', 'recurring']:
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
        valid_fields = ['name', 'description', 'date', 'address', 'approved', 'nonprofit', 'total_slots', 'image',
                       'host_org_id', 'host_user_id', 'host_org_name', 'comments', 'qualifications', 'recurring']       
        
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





if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host="0.0.0.0", port=port, debug=False)