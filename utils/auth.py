from functools import wraps
from flask import request, jsonify
import firebase_admin
from firebase_admin import auth, credentials, initialize_app
import os

env = os.environ.get("MY_ENV", "production")
API_SECRET = os.environ["API_SECRET"]

def verify_firebase_token(token):
    """Verify Firebase ID token and return user info"""
    try:
        # Add this debug line
        print(f"Firebase apps initialized: {len(firebase_admin._apps)}")
        print(f"Attempting to verify token starting with: {token[:20]}")
        
        # Verify the token
        decoded_token = auth.verify_id_token(token)
        
        print(f"Token verified successfully for user: {decoded_token['uid']}")
        
        return {
            'success': True,
            'user_id': decoded_token['uid'],
            'email': decoded_token.get('email'),
            'name': decoded_token.get('name'),
            'picture': decoded_token.get('picture')
        }
    except Exception as e:
        print(f"=== TOKEN VERIFICATION FAILED ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        return {
            'success': False,
            'error': str(e)
        }

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
                if env == "staging":
                    request.user = {"uid": "testuser", "email": "test@example.com"}
                    return f(*args, **kwargs)
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


def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization'}), 401
        
        token = auth_header.split(' ')[1]
        if token != API_SECRET:
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function