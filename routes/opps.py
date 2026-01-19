from flask import Blueprint, request, jsonify, make_response
from utils.auth import require_auth
from db import db, User, Organization, Opportunity, UserOpportunity
from datetime import datetime, timedelta, timezone
from utils.helper import paginate, save_opportunity_image
from scheduler import cancel_scheduled_email
from services.carpool_service import add_carpool
import json
import io, csv

opps_bp = Blueprint("opps", __name__)

# Opportunity Endpoints
@opps_bp.route('/api/opps', methods=['POST'])
@require_auth
def create_opportunity():
    """Create a new opportunity with optional file upload"""
    try:
        # Check if this is a multipart form (file upload) or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file upload
            data = {}
            for field in ['name', 'host_org_id', 'host_user_id', 'date', 'causes', 'tags', 'duration', 'description', 'address', 'nonprofit', 'total_slots', 'image', 'approved', 'host_org_name', 'comments', 'qualifications', 'recurring', 'visibility', 'attendance_marked', 'redirect_url', 'actual_runtime', 'allow_carpool']:
                if field in request.form:
                    if field == 'visibility':
                        data[field] = json.loads(request.form["visibility"])

                    else: 
                        data[field] = request.form[field]
            
        else:
            # Handle JSON data
            data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'host_org_id', 'host_user_id', 'date', 'duration']
        if not all(field in data for field in required_fields):
            return jsonify({
                'message': 'Missing required fields',
                'required': required_fields
            }), 400
        
        # Check if host user exists
        host_user = User.query.get(data['host_user_id'])
        if not host_user:
            return jsonify({
                'message': 'Host user does not exist',
                'error': f'User with ID {data["host_user_id"]} not found'
            }), 404
        
        # Check if host organization exists
        host_org = Organization.query.get(data['host_org_id'])
        if not host_org:
            return jsonify({
                'message': 'Host organization does not exist',
                'error': f'Organization with ID {data["host_org_id"]} not found'
            }), 404
        
        # Set host_org_name from organization if not provided
        if not data.get('host_org_name'):
            data['host_org_name'] = host_org.name
        
        # Parse date with flexible format support
        date_string = data['date'].strip()
        try:
            # Try with seconds first
            parsed_date = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            try:
                # Try without seconds
                parsed_date = datetime.strptime(date_string, '%Y-%m-%dT%H:%M')
            except ValueError:
                return jsonify({
                    'message': 'Invalid date format. Use YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM'
                }), 400
        
        gmt_date = parsed_date + timedelta(hours=4)


        # admin users can create approved opps
        if host_user.admin:
            approved = True
        else:
            approved = False

        print( data.get('multiopp_id', None))
        allow_carpool = data.get('allow_carpool').lower() == "true"
            
        # Create new opportunity
        new_opportunity = Opportunity(
            name=data['name'],
            description=data.get('description'),
            date=gmt_date, 
            duration=data['duration'],
            causes=data.get('causes'),
            tags=data.get('tags', []),
            address=data.get('address'),
            nonprofit=data.get('nonprofit'),
            total_slots=data.get('total_slots'),
            image=data.get('image'),
            host_org_id=data['host_org_id'],
            host_user_id=data['host_user_id'],
            host_org_name=data['host_org_name'],
            comments=data.get('comments', []),
            qualifications=data.get('qualifications', []),
            recurring=data.get('recurring', 'once'),
            visibility=data.get('visibility', []),
            attendance_marked=data.get('attendance_marked', False),
            redirect_url=data.get('redirect_url', None),
            actual_runtime=data.get('actual_runtime', None),
            approved=approved,
            allow_carpool=allow_carpool,
            multiopp_id=data.get('multiopp_id', None),
            multiopp=data.get('multiopp', None)
        )
        db.session.add(new_opportunity)
        db.session.flush() 

        if allow_carpool:
            add_carpool(new_opportunity, 'opp')

        # mark host as registered with registered=False
        user_opportunity = UserOpportunity(
                        user_id=data['host_user_id'],
                        opportunity_id=new_opportunity.id,
                        registered=False, # Host is initially not registered
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
    
@opps_bp.route('/api/opps', methods=['GET'])
@require_auth
def get_opportunities():
    """Get all opportunities with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
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

@opps_bp.route('/api/opps/current', methods=['GET'])
# @require_auth
def get_current_opportunities():
    """Get current opportunities (whose dates are not older than yesterday) with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))

        # Current UTC datetime
        current_datetime = datetime.utcnow()

        # Leeway: allow opportunities from up to 1 day ago
        leeway_start = current_datetime - timedelta(days=1)

        # Filter: include all opps whose date >= (yesterday at this time)
        current_opportunities = (
            Opportunity.query
            .filter(Opportunity.date >= leeway_start)
            .order_by(Opportunity.date.asc())
        )

        paginated_opps = paginate(current_opportunities, page, per_page)

        return jsonify({
            "opportunities": [opp.serialize() for opp in paginated_opps.items],
            "pagination": {
                "page": paginated_opps.page,
                "per_page": paginated_opps.per_page,
                "total": paginated_opps.total,
            },
            "current_datetime": current_datetime.isoformat(),
            "leeway_start": leeway_start.isoformat()
        })

    except Exception as e:
        return jsonify({
            "message": "Failed to fetch current opportunities",
            "error": str(e)
        }), 500
    
@opps_bp.route('/api/opps/approved', methods=['GET'])
@require_auth
def get_approved_opportunities():
    """Get approved opportunities with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        # Filter opportunities where approved is True
        approved_opportunities = Opportunity.query.filter(
            Opportunity.approved == True
        ).order_by(Opportunity.id.desc())
        
        paginated_opps = paginate(approved_opportunities, page, per_page)
        
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
            'message': 'Failed to fetch approved opportunities',
            'error': str(e)
        }), 500

@opps_bp.route('/api/opps/unapproved', methods=['GET'])
@require_auth
def get_unapproved_opportunities():
    """Get unapproved opportunities with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        # Filter opportunities where approved is False
        unapproved_opportunities = Opportunity.query.filter(
            Opportunity.approved == False
        ).order_by(Opportunity.id.desc())
        
        paginated_opps = paginate(unapproved_opportunities, page, per_page)
        
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
            'message': 'Failed to fetch unapproved opportunities',
            'error': str(e)
        }), 500

@opps_bp.route('/api/opps/active', methods=['GET'])
@require_auth
def get_active_opportunities():
    """Get active opportunities (start date is no more than 24 hours behind current date) with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10000))
        
        # Calculate the cutoff time (24 hours ago from now)
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        # Filter opportunities where date is >= cutoff_time (within last 24 hours)
        active_opportunities = Opportunity.query.filter(
            Opportunity.date >= cutoff_time
        ).order_by(Opportunity.date.asc())  # Order by date ascending (earliest first)
        
        paginated_opps = paginate(active_opportunities, page, per_page)
        
        return jsonify({
            'opportunities': [opp.serialize() for opp in paginated_opps.items],
            'pagination': {
                'page': paginated_opps.page,
                'per_page': paginated_opps.per_page,
                'total': paginated_opps.total
            },
            'cutoff_time': cutoff_time.isoformat(),
            'message': f'Active opportunities from the last 24 hours (since {cutoff_time.strftime("%Y-%m-%d %H:%M:%S")})'
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch active opportunities',
            'error': str(e)
        }), 500

@opps_bp.route('/api/opps/<int:opp_id>/phone', methods=['GET'])
@require_auth
def get_involved_users_phone_numbers(opp_id):
    """Get the phone numbers of all users involved in an opportunity"""
    try:
        opp = UserOpportunity.query.filter_by(opportunity_id=opp_id).first().opportunity
        return jsonify([user.phone for user in opp.involved_users])
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch involved users phone numbers',
            'error': str(e)
        }), 500

@opps_bp.route('/api/opps/<int:opp_id>/attendance', methods=['GET'])
@require_auth
def get_opportunity_attendance(opp_id):
    """Get all involved user IDs and their attendance status for an opportunity"""
    try:
        # Check if opportunity exists
        opportunity = Opportunity.query.get(opp_id)
        if not opportunity:
            return jsonify({
                'message': 'Opportunity not found',
                'error': f'Opportunity with ID {opp_id} does not exist'
            }), 404
        
        # Get all user opportunities for this opportunity
        user_opportunities = UserOpportunity.query.filter_by(opportunity_id=opp_id).all()
        
        # Build response with user IDs and attendance status
        attendance_data = []
        for uo in user_opportunities:
            attendance_data.append({
                'user_id': uo.user_id,
                'attended': uo.attended,
                'registered': uo.registered,
                'driving': uo.driving
            })
        
        return jsonify({
            'opportunity_id': opp_id,
            'opportunity_name': opportunity.name,
            'total_involved': len(attendance_data),
            'users': attendance_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'message': 'Failed to fetch opportunity attendance',
            'error': str(e)
        }), 500


@opps_bp.route('/api/opps/<int:opp_id>', methods=['GET'])
@require_auth
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

@opps_bp.route('/api/opps/<int:opp_id>/full', methods=['GET'])
def check_opportunity_full(opp_id):
    """Check if opportunity is fully booked"""
    try:
        opportunity = Opportunity.query.get_or_404(opp_id)
        
        # Count the number of users involved in this opportunity
        involved_users_count = UserOpportunity.query.filter_by(opportunity_id=opp_id).count()
        
        # Check if fully booked
        is_full = involved_users_count >= opportunity.total_slots
        
        return jsonify({
            'is_full': is_full
        })
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to check opportunity status',
            'error': str(e)
        }), 500

@opps_bp.route('/api/opps/<int:opp_id>', methods=['PUT'])
@require_auth
def update_opportunity(opp_id):
    """Update an opportunity with optional file upload"""
    try:
        opp = Opportunity.query.get_or_404(opp_id)
        points = getattr(opp, "duration", 0) or 0
        init_allow_carpool = opp.allow_carpool

        # Check if this is a multipart form (file upload) or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file upload
            data = {}
            for field in ['name', 'causes', 'tags', 'description', 'date', 'address', 'approved', 'nonprofit', 'total_slots', 'host_org_id', 'host_user_id', 'host_org_name', 'comments', 'duration','qualifications', 'recurring', 'visibility', 'attendance_marked', 'redirect_url', 'actual_runtime', 'allow_carpool']:
                if field in request.form:
                    data[field] = request.form[field]
                if field == 'date':
                    new_date = datetime.strptime(request.form[field], '%Y-%m-%dT%H:%M:%S') # converts to datetime object
                    new_date = new_date + timedelta(hours=4)
                    setattr(opp, field, new_date)
            
            # Handle image upload
            if 'image' in request.files:
                file = request.files['image']
                image_path = save_opportunity_image(file, opp_id)
                if image_path:
                    data['image'] = image_path
        else:
            # Handle JSON data
            data = request.get_json()
        
        # Only update fields that exist in the model
        valid_fields = ['name', 'duration', 'description', 'date', 'address', 'approved', 'nonprofit', 'total_slots', 'image',
                       'host_org_id', 'host_user_id', 'host_org_name', 'comments', 'qualifications', 'recurring', 'visibility', 'attendance_marked', 'redirect_url', 'actual_runtime', 'tags', 'allow_carpool']       
        
        for field in valid_fields:
            if field in data:
                if(field == 'date'):
                    # Parse date with flexible format support
                    date_string = data['date'].strip()
                    try:
                        # Try with seconds first
                        new_date = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
                    except ValueError:
                        try:
                            # Try without seconds
                            new_date = datetime.strptime(date_string, '%Y-%m-%dT%H:%M')
                        except ValueError:
                            return jsonify({
                                'message': 'Invalid date format. Use YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM'
                            }), 400
                    new_date = new_date.replace(tzinfo=timezone(timedelta(hours=-4)))
                    setattr(opp, field, new_date)
                elif(field == 'host_org_id'): # if host org changes, update this in other models
                    new_host_org_id = data['host_org_id']
                    old_host_org_id = opp.host_org_id
                    
                    # Check if new organization exists
                    new_org = Organization.query.get(new_host_org_id)
                    if not new_org:
                        return jsonify({
                            'message': 'Host organization does not exist',
                            'error': f'Organization with ID {new_host_org_id} not found'
                        }), 404
                    
                    # Simply update the host_org_id field
                    setattr(opp, field, new_host_org_id)
                    
                elif field == 'host_user_id':
                    new_host_user_id = data['host_user_id']
                    old_host_user_id = opp.host_user_id
                    
                    # Check if new user exists
                    new_user = User.query.get(new_host_user_id)
                    if not new_user:
                        return jsonify({
                            'message': 'Host user does not exist',
                            'error': f'User with ID {new_host_user_id} not found'
                        }), 404   

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
        db.session.flush() 
        
        if data.get('allow_carpool') and not init_allow_carpool:
            add_carpool(opp, 'opp')
        
        # Commit all changes
        db.session.commit()
        return jsonify(opp.serialize())
    
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to update opportunity',
            'error': str(e)
        }), 500

@opps_bp.route('/api/opps/<int:opp_id>', methods=['DELETE'])
@require_auth
def delete_opportunity(opp_id):
    """Delete an opportunity"""
    try:
        opp = Opportunity.query.get_or_404(opp_id)
        db.session.delete(opp)
        db.session.commit()

        cancel_scheduled_email(opp_id)

        return jsonify({
            'message': 'Opportunity deleted successfully'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Failed to delete opportunity',
            'error': str(e)
        }), 500

# Registration Endpoints
@opps_bp.route('/api/register-opp', methods=['POST'])
@require_auth
def register_user_for_opportunity():
    data = request.get_json()
    user_id = data.get('user_id')
    opportunity_id = data.get('opportunity_id')
    driving = data.get('driving', False)  # Default to False if not provided

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
            attended=False,  # default
            driving=driving
        )
        db.session.add(user_opportunity)
        db.session.commit()
        return jsonify({"message": "Registration successful"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@opps_bp.route('/api/unregister-opp', methods=['POST'])
@require_auth
def unregister_user_from_opportunity():
    """Unregister a user from an opportunity"""
    data = request.get_json()
    user_id = data.get('user_id')
    opportunity_id = data.get('opportunity_id')

    if not user_id or not opportunity_id:
        return jsonify({"error": "user_id and opportunity_id are required"}), 400

    # Check if user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({
            "message": "User does not exist",
            "error": f"User with ID {user_id} not found"
        }), 404

    # Check if opportunity exists
    opportunity = Opportunity.query.get(opportunity_id)
    if not opportunity:
        return jsonify({
            "message": "Opportunity does not exist",
            "error": f"Opportunity with ID {opportunity_id} not found"
        }), 404

    # Check if user is registered with the opportunity
    existing = UserOpportunity.query.filter_by(user_id=user_id, opportunity_id=opportunity_id).first()
    if not existing:
        return jsonify({
            "message": "User not registered with this opportunity",
            "error": f"User {user_id} is not registered for opportunity {opportunity_id}"
        }), 404

    try:
        # Remove the association
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"message": "Unregistration successful"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@opps_bp.route('/api/opps/csv', methods=['GET'])
@require_auth
def get_opps_csv():
    """Return opportunities as CSV attachment with requested columns."""
    try:
        opps = Opportunity.query.all()

        si = io.StringIO()
        writer = csv.writer(si)

        writer.writerow([
            'duration',
            'actual_runtime',
            'total_slots',
            'total_attended',
            'total_registered',
            'address',
            'date',
            'num_comments',
            'approved',
            'has_image',
            'has_description'
        ])

        for opp in opps:
            duration = opp.duration
            actual_runtime = opp.actual_runtime if opp.actual_runtime is not None else ''
            total_slots = opp.total_slots if opp.total_slots is not None else ''
            total_attended = sum(1 for uo in (opp.user_opportunities or []) if getattr(uo, 'attended', False))
            total_registered = sum(1 for uo in (opp.user_opportunities or []) if getattr(uo, 'registered', False))
            address = opp.address or ''
            date = opp.date.isoformat() if getattr(opp, 'date', None) else ''
            num_comments = len(opp.comments or [])
            approved = bool(opp.approved)
            has_image = int(bool(opp.image))
            has_description = int(bool(opp.description))

            writer.writerow([
                duration,
                actual_runtime,
                total_slots,
                total_attended,
                total_registered,
                address,
                date,
                num_comments,
                int(approved),
                has_image,
                has_description,
            ])

        output = si.getvalue()
        si.close()

        response = make_response(output)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename="data.csv"'
        return response

    except Exception as e:
        return jsonify({'error': 'Failed to generate opportunities CSV', 'message': str(e)}), 500
