from flask import Blueprint, request, jsonify, make_response
from utils.auth import require_auth
from db import db, User, Organization
from datetime import datetime
import os
from utils.helper import paginate, allowed_file
from werkzeug.utils import secure_filename
from services.s3_client import s3, S3_BUCKET
import csv, io

users_bp = Blueprint("users", __name__)

# User Endpoints
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

@users_bp.route('/api/users', methods=['POST'])
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

@users_bp.route('/api/users/emails', methods=['GET'])
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

@users_bp.route('/api/users', methods=['GET'])
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

@users_bp.route('/api/users/email', methods=['GET'])
@require_auth
def get_users_netid():
    """Get all users' netids - requires authentication"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))

        # Correct query — select users ordered by id DESC
        users_query = User.query.order_by(User.id.desc())

        # Paginate the actual query
        paginated_users = paginate(users_query, page, per_page)

        # Serialize just netid values
        users_list = [
            {"id": user.id, "email": user.email}
            for user in paginated_users.items
        ]

        return jsonify({
            "users": users_list,
            "pagination": {
                "page": paginated_users.page,
                "per_page": paginated_users.per_page,
                "total": paginated_users.total
            }
        })

    except Exception as e:
        return jsonify({
            "message": "Failed to fetch users",
            "error": str(e)
        }), 500


@users_bp.route('/api/users/<int:user_id>', methods=['GET'])
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

@users_bp.route('/api/users/check/<email>', methods=['GET'])
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


@users_bp.route('/api/users/minimal', methods=['GET'])
@require_auth
def get_users_light():
    # Query only light user info and org IDs efficiently
    users = (
        db.session.query(User)
        .options(
            db.load_only(
                User.id,
                User.name,
                User.profile_image,
                User.email,
                User.bio,
                User.car_seats,
                User.admin,
                User.phone,
                User.points,
                User.carpool_waiver_signed
            ),
            db.joinedload(User.organizations).load_only(Organization.id)
        )
        .all()
    )

    result = [
        {
            "id": u.id,
            "name": u.name,
            "profile_image": u.profile_image,
            "bio": u.bio,
            "admin": u.admin,
            "email": u.email,
            "car_seats": u.car_seats,
            "phone": u.phone,
            "organizationIds": [org.id for org in (u.organizations or [])],
            "points": u.points or 0,
            "carpool_waiver_signed": u.carpool_waiver_signed
        }
        for u in users
    ]
    return jsonify({"users": result})



@users_bp.route('/api/users/email/<email>', methods=['GET'])
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

@users_bp.route('/api/users/<int:user_id>', methods=['PUT'])
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

@users_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
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
    
@users_bp.route('/api/users/csv', methods=['GET'])
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
