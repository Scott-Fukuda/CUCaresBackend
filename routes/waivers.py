from flask import Blueprint, request, jsonify 
from utils.auth import require_auth
from db import db, User, Waiver
import traceback

waivers_bp = Blueprint("waivers", __name__)

# Waiver endpoints
@waivers_bp.route('/api/waivers/create-waiver', methods=['POST', 'OPTIONS'])
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