import datetime
from operator import and_
import traceback
from flask import Blueprint, jsonify, make_response, request, Response
from utils.auth import require_auth
from db import db, Ride, User, RideRider, Carpool

rides_bp = Blueprint("rides", __name__)

# Ride endpoints
@rides_bp.route('/api/rides', methods=['POST'])
@require_auth 
def create_ride():
    try:
        data = request.get_json()

        required_fields = ['carpool_id', 'driver_id']
        if not all(field in data for field in required_fields):
            return jsonify({
                'message': 'Missing required fields',
                'required': required_fields
            }), 400
        
        user = User.query.get(data['driver_id'])

        if not user:
            return jsonify({
                'message': 'User does not exist'
            })        

        new_ride = Ride(
            carpool_id=data.get('carpool_id'),
            driver_id=data.get('driver_id')
        )
        
        db.session.add(new_ride)
        db.session.commit()
        
        return jsonify(new_ride.serialize()), 201
    
    except Exception as e:
        db.session.rollback()
        print("Error in /api/rides:")
        traceback.print_exc()
        return jsonify({
            'message': 'Failed to create ride',
            'error': str(e)
        }), 500

@rides_bp.route('/api/rides/<int:carpool_id>', methods=['GET'])
@require_auth 
def get_rides(carpool_id):
    try:
        carpool = Carpool.query.get(carpool_id)
        if not carpool:
            return jsonify({"error": "Carpool not found"}), 404
        
        rides = Ride.query.filter_by(carpool_id=carpool_id).all()

        return jsonify({
            "rides": [ride.serialize() for ride in rides]
        }), 200
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch rides',
            'error': str(e)
        }), 500
    
@rides_bp.route('/api/rides/add-rider', methods=['POST'])
@require_auth
def add_rider():
    try:
        data = request.get_json()

        required_fields=['ride_id', 'user_id', 'pickup_location']
        if not all(field in data for field in required_fields):
            return jsonify({
                'message': 'missing required fields',
                'required': required_fields
            }), 400
        
        user = User.query.get(data['user_id'])
        ride = Ride.query.get(data['ride_id'])
        if not user or not ride:
            return jsonify({
                'message': 'Rider or user does not exist'
            })
        print('PICKUP', data['pickup_location'])
        
        new_ride_rider = RideRider(
            ride_id=ride.id,
            user_id=user.id,
            pickup_location=data['pickup_location'],
            notes=data['notes']
        )
        db.session.add(new_ride_rider)
        db.session.commit()
        return jsonify(new_ride_rider.serialize()), 201

    except Exception as e:
        db.session.rollback()
        print("Error in /api/rides/add-rider")
        traceback.print_exc()
        return jsonify({
            'message': 'Failed to add rider',
            'error': e
        }), 500

@rides_bp.route('/api/rides/remove-rider', methods=['DELETE'])
@require_auth
def remove_rider():
    try:
        data = request.get_json()

        required_fields = ['ride_id', 'user_id']
        if not all(field in data for field in required_fields):
            return jsonify({
                'message': 'missing required fields',
                'required': required_fields
            }), 400
        
        user = User.query.get(data['user_id'])
        ride = Ride.query.get(data['ride_id'])
        if not user or not ride:
            return jsonify({
                'message': 'Rider or user does not exist'
            }), 404
        
        ride_rider = RideRider.query.filter_by(
            ride_id=ride.id,
            user_id=user.id
        ).first()
        
        if not ride_rider:
            return jsonify({
                'message': 'User is not registered for this ride'
            }), 404
        
        db.session.delete(ride_rider)
        db.session.commit()
        
        return jsonify({
            'message': 'Rider removed successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        print("Error in /api/rides/remove-rider")
        traceback.print_exc()
        return jsonify({
            'message': 'Failed to remove rider',
            'error': str(e)
        }), 500

@rides_bp.route('/api/rides/remove-carpool-user', methods=['DELETE'])
@require_auth
def remove_carpool_user():
    try:
        data = request.get_json()

        required_fields = ['carpool_id', 'user_id']
        if not all(field in data for field in required_fields):
            return jsonify({
                'message': 'missing required fields',
                'required': required_fields,
            }), 400
        
        user = User.query.get(data['user_id'])
        ride = Ride.query.filter_by(carpool_id=data['carpool_id']).first()
        if not user or not ride:
            return jsonify({
                'message': 'Rider or user does not exist'
            }), 404
        
        if user.id == ride.driver_id:
            # User can't unsignup if they signed up to be a driver
            return jsonify({
                'message': 'User has signed up to drive and therefore cannot be removed',
                'valid': False
            }), 200
        
        ride_rider = RideRider.query.filter_by(
            ride_id=ride.id,
            user_id=user.id
        ).first()
        
        if not ride_rider:
            return jsonify({
                'message': 'User is not registered for this ride',
                'valid': True
            }), 200
        
        db.session.delete(ride_rider)
        db.session.commit()
        
        return jsonify({
            'message': 'Rider removed successfully',
            'valid': True
        }), 200

    except Exception as e:
        db.session.rollback()
        print("Error in /api/rides/remove-rider")
        traceback.print_exc()
        return jsonify({
            'message': 'Failed to remove rider',
            'error': str(e)
        }), 500
