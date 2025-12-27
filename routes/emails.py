from flask import Blueprint, request, jsonify 
from utils.auth import require_auth
from db import db, ApprovedEmail

emails_bp = Blueprint("emails", __name__)

# Approved Email Management Endpoints
@emails_bp.route('/api/approved-emails', methods=['POST'])
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

@emails_bp.route('/api/approved-emails/<int:email_id>', methods=['DELETE'])
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

@emails_bp.route('/api/approved-emails/check/<email>', methods=['GET'])
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