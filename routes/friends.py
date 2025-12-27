from flask import Blueprint, request, jsonify 
from utils.auth import require_auth
from db import db, User, Friendship

friends_bp = Blueprint("friends", __name__)

# Friends Endpoints
@friends_bp.route('/api/users/<int:user_id>/friends', methods=['GET'])
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

@friends_bp.route('/api/users/<int:user_id>/friend-requests', methods=['GET'])
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

@friends_bp.route('/api/friendships', methods=['GET'])
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

@friends_bp.route('/api/users/<int:user_id>/friendships', methods=['GET'])
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

@friends_bp.route('/api/users/<int:user_id>/friends', methods=['POST'])
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

@friends_bp.route('/api/friendships/<int:friendship_id>/accept', methods=['PUT'])
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

@friends_bp.route('/api/friendships/<int:friendship_id>/reject', methods=['PUT'])
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

@friends_bp.route('/api/users/<int:user_id>/friends/<int:friend_id>', methods=['DELETE'])
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

@friends_bp.route('/api/users/<int:user_id>/friends/check/<int:friend_id>', methods=['GET'])
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

@friends_bp.route('/api/users/<int:user_id>/friendships/all', methods=['GET'])
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