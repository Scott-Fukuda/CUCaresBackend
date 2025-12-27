from datetime import timedelta, datetime
import random
import uuid
from flask import Blueprint, request, jsonify 
from utils.auth import require_auth
from db import db, Opportunity, UserOpportunity, User, Organization, Friendship
from services.s3_client import s3, S3_BUCKET
import os 
from werkzeug.utils import secure_filename

misc_bp = Blueprint("misc", __name__)

@misc_bp.route('/api/monthly-points', methods=['GET'])
@require_auth
def get_monthly_points():
    """Get all users and their points earned from a given date to present"""
    try:
        # Get the date from query parameters
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({
                'error': 'Date parameter is required',
                'message': 'Please provide a date in YYYY-MM-DD format'
            }), 400
        
        # Parse the date
        try:
            from_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'error': 'Invalid date format',
                'message': 'Date must be in YYYY-MM-DD format'
            }), 400
        
        # Get all users
        users = User.query.all()
        user_points = []
        
        for user in users:
            total_points = 0
            
            # Get all user opportunities where user attended
            user_opportunities = UserOpportunity.query.filter_by(
                user_id=user.id,
                attended=True
            ).all()
            
            for uo in user_opportunities:
                opportunity = uo.opportunity
                
                # Check if opportunity date is on or after the given date
                if opportunity.date >= from_date:
                    # Use actual_runtime if available, otherwise use duration
                    if opportunity.actual_runtime is not None:
                        total_points += opportunity.actual_runtime
                    else:
                        total_points += opportunity.duration
            
            user_points.append({
                'id': user.id,
                'points': total_points
            })
        
        return jsonify({
            'users': user_points
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to calculate monthly points',
            'message': str(e)
        }), 500

# Attendance Endpoints
@misc_bp.route('/api/attendance', methods=['PUT'])
@require_auth
def marked_as_attended():
    data = request.get_json()
    user_ids = data.get('user_ids')
    opportunity_id = data.get('opportunity_id')
    duration = data.get('duration')
    driving = data.get('driving', False)

    if not user_ids or not opportunity_id:
        return jsonify({"error": "user_ids and opportunity_id are required"}), 400

    messages = []
    try:
        opp = Opportunity.query.get(opportunity_id)
        if not opp:
            return jsonify({"error": "Invalid opportunity_id"}), 404

        # Fetch existing registrations for these users
        user_opps = UserOpportunity.query.filter(
            UserOpportunity.user_id.in_(user_ids),
            UserOpportunity.opportunity_id == opportunity_id
        ).all()

        # Map by user_id for O(1) lookup
        user_opp_map = {uo.user_id: uo for uo in user_opps}

        first_user = True
        for user_id in user_ids:
            uo = user_opp_map.get(user_id)

            if first_user:
                uo.user.points += 5 # bonus points
                first_user = False

            if not uo:
                # Not registered -> skip
                messages.append({"user_id": user_id, "error": "User not registered for this opportunity"})
                continue

            if not uo.attended:
                uo.attended = True
                uo.driving = driving
                uo.user.points += duration  # Award points to the User
                messages.append({"user_id": user_id, "message": "Attendance updated & points awarded"})
            else:
                messages.append({"user_id": user_id, "message": "User already marked as attended"})

        # Update opportunity metadata
        opp.actual_runtime = duration
        opp.attendance_marked = True

        db.session.commit()
        return jsonify({"results": messages}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@misc_bp.route('/api/generate-schema', methods=['POST'])
def generate_random_schema():
    """Generate a random database schema with users, orgs, opportunities, and friend requests"""
    try:
        
        # Sample data for generation
        first_names = ["Alex", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Avery", "Quinn", "Sage", "River"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        universities = ["Harvard", "Stanford", "MIT", "Yale", "Princeton", "Columbia", "Duke", "Northwestern", "Brown", "Dartmouth"]
        companies = ["Google", "Microsoft", "Apple", "Amazon", "Meta", "Tesla", "Netflix", "Uber", "Airbnb", "Spotify"]
        
        org_types = ["Academic", "Professional", "Social", "Service", "Cultural"]
        causes = ["Education", "Environment", "Healthcare", "Poverty", "Animal Welfare", "Arts", "Sports", "Technology"]
        locations = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego"]
        
        generated_data = {
            "users": [],
            "organizations": [],
            "opportunities": [],
            "friend_requests": []
        }
        
        # 1. Generate 5 users
        users = []  # Store users in a list
        for i in range(5):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            university = random.choice(universities)
            
            user = User(
                name=f"{first_name} {last_name}",
                email=f"{first_name.lower()}.{last_name.lower()}@{university.lower()}.edu",
                phone=f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                points=random.randint(0, 500),
                interests=random.sample(causes, random.randint(1, 3)),
                admin=random.choice([True, False]),
                gender=random.choice(["Male", "Female", "Non-binary", "Prefer not to say"]),
                graduation_year=str(random.randint(2024, 2028)),
                academic_level=random.choice(["Undergraduate", "Graduate", "PhD"]),
                major=random.choice(["Computer Science", "Business", "Engineering", "Medicine", "Law", "Arts"]),
                birthday=datetime.now() - timedelta(days=random.randint(6570, 10950)),  # 18-30 years old
                car_seats=random.randint(0, 7),
                bio=None
            )
            
            db.session.add(user)
            db.session.flush()  # Get the ID
            users.append(user)  # Add to our list
            generated_data["users"].append(user.serialize())
        
        # 2. Generate 5 organizations, approve 3
        organizations = []  # Store orgs in a list
        for i in range(5):
            org_type = random.choice(org_types)
            company = random.choice(companies)
            
            org = Organization(
                name=f"{company} {org_type} Society",
                description=f"A {org_type.lower()} organization focused on professional development and networking in the {company} ecosystem.",
                member_count=random.randint(10, 200),
                points=random.randint(50, 1000),
                type=org_type,
                approved=i < 3,  # First 3 are approved
                date_created=""
            )
            
            db.session.add(org)
            db.session.flush()  # Get the ID
            organizations.append(org)  # Add to our list
            generated_data["organizations"].append(org.serialize())
        
        db.session.commit()
        # 3. Generate 5 opportunities, approve 3
        for i in range(5):
            causes = random.choice(causes)
            location = random.choice(locations)
            org = organizations[i % 5]  # Use our list instead of querying
            
            # Random date between now and 3 months from now
            start_date = datetime.now() + timedelta(days=random.randint(1, 90))
            
            opportunity = Opportunity(
                name=f"{causes} Volunteer Event in {location}",
                description=f"Join us for a meaningful {causes.lower()} volunteer opportunity in {location}. Help make a difference in your community while meeting like-minded individuals.",
                date=start_date,
                duration=random.choice([60, 120, 180, 240, 480]),  # 1-8 hours
                causes=causes,
                tags=random.sample(["volunteer", "community", "service", "outdoor", "indoor", "teamwork", "leadership", "creative"], random.randint(1, 3)),
                address=f"{random.randint(100, 9999)} {random.choice(['Main St', 'Oak Ave', 'Pine Rd', 'Elm Blvd'])} {location}",
                nonprofit=random.choice(["Local Food Bank", "Habitat for Humanity", "Red Cross", "United Way", "Boys & Girls Club"]),
                total_slots=random.randint(5, 50),
                approved=i < 3,  # First 3 are approved
                host_org_id=org.id,
                host_org_name=org.name,
                comments=[],
                qualifications=random.sample(["No experience required", "Background check needed", "Must be 18+", "Physical activity involved"], random.randint(1, 3)),
                recurring=random.choice(["once", "weekly", "monthly"]),
                visibility=[],
                attendance_marked=False,
                redirect_url=None,
                actual_runtime=None
            )
            
            db.session.add(opportunity)
            db.session.flush()  # Get the ID
            generated_data["opportunities"].append(opportunity.serialize())
        
        # Commit users, orgs, and opportunities first
        db.session.commit()
        with db.session.no_autoflush:   # 👈 Prevent autoflush while querying
            all_users = User.query.all()
        
        # 4. Generate 4 friend requests between users
        # 4. Generate 4 friend requests between users
        friend_requests_created = 0

        while friend_requests_created < 4:
            requester = random.choice(users)   # ✅ use the in-memory list
            receiver = random.choice(users)

            if requester.id == receiver.id:
                continue

            # check duplicates manually
            exists = any(
                (fr["requester"] == requester.name and fr["receiver"] == receiver.name) or
                (fr["requester"] == receiver.name and fr["receiver"] == requester.name)
                for fr in generated_data["friend_requests"]
            )
            if exists:
                continue

            friendship = Friendship(
                requester_id=requester.id,
                receiver_id=receiver.id,
                accepted=random.choice([True, False])
            )

            db.session.add(friendship)
            friend_requests_created += 1

            generated_data["friend_requests"].append({
                "requester": requester.name,
                "receiver": receiver.name,
                "accepted": friendship.accepted
            })

        # Final commit
        db.session.commit()

        
        return jsonify({
            'message': 'Random database schema generated successfully',
            'generated_data': generated_data,
            'summary': {
                'users_created': len(generated_data["users"]),
                'organizations_created': len(generated_data["organizations"]),
                'organizations_approved': len([org for org in generated_data["organizations"] if org["approved"]]),
                'opportunities_created': len(generated_data["opportunities"]),
                'opportunities_approved': len([opp for opp in generated_data["opportunities"] if opp["approved"]]),
                'friend_requests_created': len(generated_data["friend_requests"])
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to generate random schema',
            'message': str(e)
        }), 500

@misc_bp.route("/upload", methods=["POST"])
def upload():
    """Upload file to S3"""
    try:
        file = request.files["file"]

        # Extract safe extension (e.g. ".jpg")
        _, ext = os.path.splitext(secure_filename(file.filename))

        # Generate unique filename with UUID
        unique_filename = f"{uuid.uuid4()}{ext}"

        # Upload to S3
        s3.upload_fileobj(
            file,
            S3_BUCKET,
            unique_filename,
            ExtraArgs={"ContentType": file.content_type}
        )

        # Public URL of the file
        url = f"https://{S3_BUCKET}.s3.amazonaws.com/{unique_filename}"
        return {"url": url}
    
    except Exception as e:
        return jsonify({
            'message': 'Failed to upload file to S3',
            'error': str(e)
        }), 500