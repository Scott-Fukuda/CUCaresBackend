import datetime
from operator import and_
import traceback
from flask import Blueprint, jsonify, make_response, request, Response
from utils.auth import require_auth
from db import db,User, Car

cars_bp = Blueprint("cars", __name__)

# Car endpoints
@cars_bp.route('/api/cars', methods=['POST'])
@require_auth 
def create_or_update_car():
    try:
        data = request.get_json()

        required_fields = ['user_id', 'seats']
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
        
        existing_car = Car.query.filter_by(user_id=user.id).first()

        if existing_car:
            existing_car.color=data.get('color', '')
            existing_car.model=data.get('model', '')
            existing_car.seats=data.get('seats')
            existing_car.license_plate=data.get('license_plate', '')

            db.session.commit()
            return jsonify(existing_car.serialize()), 201
        else:
            new_car = Car(
                user_id=data.get('user_id'),
                color=data.get('color', ''),
                model=data.get('model', ''),
                seats=data.get('seats'),
                license_plate=data.get('license_plate', '')
            )
            
            db.session.add(new_car)
            db.session.commit()
            return jsonify(new_car.serialize()), 201
    
    except Exception as e:
        db.session.rollback()
        print("Error in /api/cars:")
        traceback.print_exc()
        return jsonify({
            'message': 'Failed to create car',
            'error': str(e)
        }), 500
    
@cars_bp.route('/api/cars/<int:user_id>', methods=['GET'])
@require_auth
def get_car(user_id):
    """Get a user's car"""
    try:
        car = Car.query.filter_by(user_id=user_id).first()

        if car: 
            return jsonify({
                'exists': True,
                'car': car.serialize()
            }), 200 
        else:
            return jsonify({
                'exists': False
            }), 200
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch car',
            'error': str(e)
        }), 500