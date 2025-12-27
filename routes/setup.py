import datetime
from operator import and_
import traceback
from flask import Blueprint, jsonify, make_response, request, session
from utils.auth import require_auth
from db import db, Ride, User, RideRider, Carpool
import os 
from utils.auth import verify_firebase_token
import firebase_admin

setup_bp = Blueprint("setup", __name__)

env = os.environ.get("MY_ENV", "production")

# Staging Endpoints
if env == "staging":
    @setup_bp.route("/api/login-test/<int:user_id>")
    def login_test(user_id):
        user = User.query.get(user_id)
        if user: 
            session["user_id"] = user.id
            print(f"Logged in test user {user.name}")
            return jsonify(user.serialize()), 200
        print("User not found")
        return "User not found", 404

@setup_bp.route('/api/protected', methods=['POST'])
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


@setup_bp.route('/api/firebase-status', methods=['GET'])
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

@setup_bp.route('/api/me', methods=['GET'])
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