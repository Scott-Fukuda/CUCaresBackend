import json
from flask import Flask, request, jsonify
from db import db, User, Organization, Opportunity, UserOpportunity
from werkzeug.security import generate_password_hash
from datetime import datetime
from flask_cors import CORS

# define db filename
db_filename = "cucares.db"
app = Flask(__name__)

# restrict API access to requests from secure origin
CORS(app, origins=["http://localhost:5173"])


# setup config
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_filename}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = True

# initialize app
db.init_app(app)
with app.app_context():
    # db.drop_all()
    db.create_all()

    # # NOTE: DON'T UNCOMMENT UNLESS YOU WANT TO DELETE TABLES
    # User.__table__.drop(db.engine)
    # Opportunity.__table__.drop(db.engine)
    # Organization.__table__.drop(db.engine)
    # UserOpportunity.__table__.drop(db.engine)


# Helper function to handle pagination
def paginate(query, page=1, per_page=20):
    return query.paginate(page=page, per_page=per_page, error_out=False)

# Special Endpoints
@app.route('/api/register-opp', methods=['POST'])
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

@app.route('/api/attendance', methods=['PUT'])
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
def create_user():
    """Create a new user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'password']
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
        
        # Create new user
        new_user = User(
            profile_image=data.get('profile_image'),
            name=data['name'],
            email=data['email'],
            password=generate_password_hash(data['password']),
            points=data.get('points', 0)
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
def get_users():
    """Get all users with pagination"""
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

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update a user"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        
        # Only update fields that exist in the model
        valid_fields = ['profile_image', 'name', 'email', 'password', 'points']
        for field in valid_fields:
            if field in data:
                setattr(user, field, data[field])
        
        # Special handling for password
        if 'password' in data:
            user.password = generate_password_hash(data['password'])
        
        db.session.commit()
        return jsonify(user.serialize())
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to update user',
            'error': str(e)
        }), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
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
            description=data.get('description'),
            member_count=data.get('member_count', 0),
            points=data.get('points', 0),
            type=data.get('type'),
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

@app.route('/api/orgs/<int:org_id>', methods=['GET'])
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
def update_organization(org_id):
    """Update an organization"""
    try:
        org = Organization.query.get_or_404(org_id)
        data = request.get_json()
        
        # Only update fields that exist in the model
        valid_fields = ['name', 'description', 'member_count', 'points', 'type', 'host_user_id']
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
def create_opportunity():
    """Create a new opportunity"""
    try:
        data = request.get_json()
        # Validate required fields
        required_fields = ['name', 'host_org_id', 'host_user_id', 'date', 'cause', 'duration']
        if not all(field in data for field in required_fields):
            return jsonify({
                'message': 'Missing required fields',
                'required': required_fields
            }), 400
        
        if not User.query.get(data['host_user_id']):
            return jsonify({
                'message': 'Host user does not exist'
            })        
        
        # Create new opportunity
        new_opportunity = Opportunity(
            name=data['name'],
            description=data.get('description'),
            date=datetime.strptime(data['date'], '%Y-%m-%dT%H:%M:%S'), # converts to datetime object
            duration=data['duration'],
            cause=data.get('cause'),
            completed=data.get('completed', False),
            host_org_id=data['host_org_id'],
            host_user_id=data['host_user_id']
        )
        
        db.session.add(new_opportunity)
        db.session.commit()

        # mark host are registered
        user_opportunity = UserOpportunity(
                        user_id=data['host_user_id'],
                        opportunity_id=new_opportunity.id,
                        registered=True, # Keep marked as not registered
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

@app.route('/api/opps/<int:opp_id>', methods=['GET'])
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
def update_opportunity(opp_id):
    """Update an opportunity"""
    try:
        opp = Opportunity.query.get_or_404(opp_id)
        data = request.get_json()
        points = getattr(opp, "duration", 0) or 0

        
        # Only update fields that exist in the model
        valid_fields = ['name', 'description', 'date', 'completed', 
                       'host_org_id', 'host_user_id']       
        
        for field in valid_fields:
            if field in data:
                if(field == 'date'):
                    new_date = datetime.strptime(data['date'], '%Y-%m-%dT%H:%M:%S') # converts to datetime object
                    setattr(opp, field, new_date)
                elif(field == 'host_org_id'): # if host org changes, update this in other models
                    new_host_org_id = data['host_org_id']
                    old_host_org_id = opp.host_user_id
                    if not Organization.query.get(old_host_org_id):
                        return jsonify({
                            'message': 'Host org does not exist'
                        })  
                    
                    if new_host_org_id != old_host_org_id:
                        old_org = Organization.query.get(old_host_user_id)
                        new_org = Organization.query.get(new_host_user_id)

                        opp.participating_organizations.append(new_org)
                        opp.participating_organizations.remove(old_org)
                        db.session.commit()
                        setattr(opp, field, new_host_org_id)
                    
                elif field == 'host_user_id':
                    new_host_user_id = data['host_user_id']
                    old_host_user_id = opp.host_user_id
                    if not User.query.get(old_host_user_id):
                        return jsonify({
                            'message': 'Host user does not exist'
                        })   

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
        return jsonify(opp.serialize())
    
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to update opportunity',
            'error': str(e)
        }), 500

@app.route('/api/opps/<int:opp_id>', methods=['DELETE'])
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
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)