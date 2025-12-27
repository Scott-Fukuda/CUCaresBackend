from flask import Blueprint, request, jsonify 
from utils.auth import require_auth
from db import db, User, Organization
from utils.helper import paginate

orgs_bp = Blueprint("orgs", __name__)

# Organization Endpoints
@orgs_bp.route('/api/orgs', methods=['POST'])
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

@orgs_bp.route('/api/orgs', methods=['GET'])
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

@orgs_bp.route('/api/orgs/approved', methods=['GET'])
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


@orgs_bp.route('/api/orgs/unapproved', methods=['GET'])
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

@orgs_bp.route('/api/orgs/<int:org_id>', methods=['GET'])
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

@orgs_bp.route('/api/orgs/<int:org_id>', methods=['PUT'])
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

@orgs_bp.route('/api/orgs/<int:org_id>', methods=['DELETE'])
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
    
# Registration Endpoints
@orgs_bp.route('/api/register-org', methods=['POST'])
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

@orgs_bp.route('/api/unregister-org', methods=['POST'])
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
