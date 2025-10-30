import datetime
import random
from app import app
from db import db, User, Organization, Opportunity, UserOpportunity, Friendship, ApprovedEmail, Waiver, user_organization

NUM_USERS = 8
NUM_ORGS = 3
NUM_OPPS = 5

with app.app_context():
    print("Clearing existing data...")
    db.session.execute(user_organization.delete())
    db.session.query(Opportunity).delete()
    db.session.query(Organization).delete()
    db.session.query(User).delete()
    db.session.commit()

    print("Seeding users...")
    
    testUsers = {
        1: {
            "name": "Alice Johnson",
            "profile_image": "https://images.unsplash.com/photo-1761833199030-3e2c34a76523?ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&q=80&w=987",
            "email": "alice.johnson@example.com",
            "phone": "555-1234",
            "points": 120,
            "interests": ["hiking", "photography", "reading"],
            "admin": False,
            "gender": "female",
            "graduation_year": 2026,
            "academic_level": "undergraduate",
            "major": "Computer Science",
            "birthday": "2004-03-15",
            "car_seats": 2,
            "bio": "Love outdoor adventures and coding challenges."
        },
        2: {
            "name": "Brian Smith",
            "profile_image": "https://plus.unsplash.com/premium_photo-1760541740387-e0af5182d805?ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&q=80&w=1035",
            "email": "brian.smith@example.com",
            "phone": "555-5678",
            "points": 85,
            "interests": ["gaming", "cooking", "basketball"],
            "admin": True,
            "gender": "male",
            "graduation_year": 2025,
            "academic_level": "graduate",
            "major": "Mechanical Engineering",
            "birthday": "2002-08-22",
            "car_seats": 1,
            "bio": "Aspiring engineer who loves experimenting in the kitchen."
        },
        3: {
            "name": "Carmen Lee",
            "profile_image": "https://images.unsplash.com/photo-1761828122700-11b752d69a88?ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&q=80&w=987",
            "email": "carmen.lee@example.com",
            "phone": "555-8765",
            "points": 200,
            "interests": ["music", "traveling", "yoga"],
            "admin": False,
            "gender": "female",
            "graduation_year": 2027,
            "academic_level": "undergraduate",
            "major": "Psychology",
            "birthday": "2005-11-10",
            "car_seats": 3,
            "bio": "Always seeking new experiences and good vibes."
        },
        4: {
            "name": "David Nguyen",
            "profile_image": "https://images.unsplash.com/photo-1756142753931-87538d2c8cf4?ixlib=rb-4.1.0&ixid=M3wxMjA3fDF8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&q=80&w=987",
            "email": "david.nguyen@example.com",
            "phone": "555-4321",
            "points": 50,
            "interests": ["cycling", "chess", "coding"],
            "admin": False,
            "gender": "male",
            "graduation_year": 2026,
            "academic_level": "undergraduate",
            "major": "Mathematics",
            "birthday": "2003-06-30",
            "car_seats": 2,
            "bio": "Chess enthusiast and aspiring mathematician."
        },
        5: {
            "name": "Emily Carter",
            "profile_image": "https://images.unsplash.com/photo-1752119769630-81c074181749?ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&q=80&w=986",
            "email": "emily.carter@example.com",
            "phone": "555-6543",
            "points": 180,
            "interests": ["painting", "reading", "volunteering"],
            "admin": True,
            "gender": "female",
            "graduation_year": 2024,
            "academic_level": "graduate",
            "major": "Fine Arts",
            "birthday": "2001-02-18",
            "car_seats": 1,
            "bio": "Artist at heart, always exploring new ideas."
        },
        6: {
            "name": "Frank Wilson",
            "profile_image": "https://images.unsplash.com/photo-1757301310756-b092d8bea774?ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&q=80&w=2070",
            "email": "frank.wilson@example.com",
            "phone": "555-9876",
            "points": 95,
            "interests": ["soccer", "gaming", "music"],
            "admin": False,
            "gender": "male",
            "graduation_year": 2025,
            "academic_level": "undergraduate",
            "major": "Economics",
            "birthday": "2002-09-12",
            "car_seats": 4,
            "bio": "Sports fan and music lover."
        },
        7: {
            "name": "Grace Miller",
            "profile_image": None,
            "email": "grace.miller@example.com",
            "phone": "555-3456",
            "points": 160,
            "interests": ["writing", "traveling", "photography"],
            "admin": False,
            "gender": "female",
            "graduation_year": 2026,
            "academic_level": "undergraduate",
            "major": "English Literature",
            "birthday": "2003-12-05",
            "car_seats": 2,
            "bio": "Writer and avid traveler who loves capturing moments."
        },
        8: {
            "name": "Henry Thompson",
            "profile_image": None,
            "email": "henry.thompson@example.com",
            "phone": "555-2109",
            "points": 130,
            "interests": ["hiking", "technology", "gaming"],
            "admin": True,
            "gender": "male",
            "graduation_year": 2024,
            "academic_level": "graduate",
            "major": "Computer Engineering",
            "birthday": "2001-07-21",
            "car_seats": 3,
            "bio": "Tech enthusiast with a love for the outdoors."
        }
    }

    users = []
    for i in range(1, NUM_USERS + 1):
        userObj = testUsers.get(i)

        user = User(
            profile_image=userObj.get("profile_image"),
            name=userObj.get("name"),
            email=userObj.get("email"),
            phone=userObj.get("phone"),
            points=userObj.get("points"),
            interests=userObj.get("interests"),
            admin=userObj.get("admin"),  # some admins
            gender=userObj.get("gender"),
            graduation_year=userObj.get("graduation_year"),
            academic_level=userObj.get("academic_level"),
            major=userObj.get("major"),
            birthday=userObj.get("birthday"),
            car_seats=userObj.get("car_seats"),
            bio=userObj.get("bio"),
        )
        users.append(user)
        db.session.add(user)
    db.session.commit()

    organizations = {
        1: {
            "name": "GreenFuture Foundation",
            "description": "Innovative solutions for a sustainable world",
            "type": "nonprofit",
            "date_created": "2022-05-14",
            "host_user_id": 1,
        },
        2: {
            "name": "Campus Volunteers",
            "description": "Engaging students in community service",
            "type": "student group",
            "date_created": "2021-09-20",
            "host_user_id": 2,
        },
        3: {
            "name": "Health for All",
            "description": "Promoting wellness and access to healthcare",
            "type": "volunteer org",
            "date_created": "2023-02-11",
            "host_user_id": 6,
        }
    }


    print("Seeding organizations...")
    orgs = []
    for i in range(1, NUM_ORGS + 1):
        orgObj = organizations.get(i)
        org_user = users[i - 1]

        org = Organization(
            name=orgObj.get("name"),
            description=orgObj.get("description"),
            type=orgObj.get("type"),
            approved=True,
            host_user_id=org_user.id
        )
        org.users = random.sample(users, k=random.randint(2, 5))
        orgs.append(org)
        db.session.add(org)
    db.session.commit()

    opportunities = {
        1: {
            "name": "Park Cleanup Day",
            "description": "Help clean up the local park and plant flowers",
            "date": "2025-11-10 09:00:00",
            "duration": 120,
            "causes": ["environment", "community"],
            "tags": ["volunteer", "off-campus"],
            "address": "123 Main St, Townsville",
            "nonprofit": "GreenFuture Foundation",
            "total_slots": 15,
            "image": "https://picsum.photos/seed/101/400/300",
            "approved": True,
            "host_org_id": 1,
            "host_user_id": 1,
            "host_org_name": "GreenFuture Foundation",
            "recurring": "once",
            "redirect_url": None
        },
        2: {
            "name": "Food Drive",
            "description": "Collect and distribute food to families in need",
            "date": "2025-11-12 14:00:00",
            "duration": 180,
            "causes": ["community", "health"],
            "tags": ["fundraising", "on-campus"],
            "address": "456 College Ave, Townsville",
            "nonprofit": "Campus Volunteers",
            "total_slots": 10,
            "image": "https://picsum.photos/seed/202/400/300",
            "approved": False,
            "host_org_id": 2,
            "host_user_id": 2,
            "host_org_name": "Campus Volunteers",
            "recurring": "weekly",
            "redirect_url": None
        },
        3: {
            "name": "Health Workshop",
            "description": "Free workshop on nutrition and exercise",
            "date": "2025-11-15 10:00:00",
            "duration": 90,
            "causes": ["health", "education"],
            "tags": ["volunteer", "off-campus"],
            "address": "789 Wellness Rd, Townsville",
            "nonprofit": "Health for All",
            "total_slots": 12,
            "image": "https://picsum.photos/seed/303/400/300",
            "approved": True,
            "host_org_id": 3,
            "host_user_id": 6,
            "host_org_name": "Health for All",
            "recurring": "monthly",
            "redirect_url": None
        },
        4: {
            "name": "Tree Planting",
            "description": "Plant trees around the city park",
            "date": "2025-11-20 08:00:00",
            "duration": 120,
            "causes": ["environment"],
            "tags": ["volunteer", "off-campus"],
            "address": "321 Greenway Blvd, Townsville",
            "nonprofit": "GreenFuture Foundation",
            "total_slots": 20,
            "image": "https://picsum.photos/seed/404/400/300",
            "approved": True,
            "host_org_id": 1,
            "host_user_id": 3,
            "host_org_name": "GreenFuture Foundation",
            "recurring": "once",
            "redirect_url": None
        },
        5: {
            "name": "Community Tutoring",
            "description": "Volunteer to tutor local students after school",
            "date": "2025-11-25 16:00:00",
            "duration": 90,
            "causes": ["education", "community"],
            "tags": ["on-campus"],
            "address": "987 Learning Ln, Townsville",
            "nonprofit": "Campus Volunteers",
            "total_slots": 8,
            "image": "https://picsum.photos/seed/505/400/300",
            "approved": True,
            "host_org_id": 2,
            "host_user_id": 4,
            "host_org_name": "Campus Volunteers",
            "recurring": "weekly",
            "redirect_url": None
        }
    }

    print("Seeding opportunities...")
    opps = []
    for i in range(1, NUM_OPPS + 1):
        oppObj = opportunities.get(i)
        # Map opportunity to organization (cycling through available orgs)
        org_index = (i - 1) % len(orgs)
        hostOrg = orgs[org_index]
        
        opp = Opportunity(
            name=oppObj.get("name"),
            description=oppObj.get("description"),
            date=oppObj.get("date"),
            duration=oppObj.get("duration"),
            causes=oppObj.get("causes"),
            tags=oppObj.get("tags"),
            address=oppObj.get("address"),
            nonprofit=hostOrg.name,
            total_slots=oppObj.get("total_slots"),
            image=oppObj.get("image"),
            approved=True,
            host_org_id=hostOrg.id,  # Use the actual ID from the committed org
            host_user_id=hostOrg.host_user_id,  # Use the actual host_user_id
            host_org_name=hostOrg.name,
            recurring=oppObj.get("recurring"),
            redirect_url=oppObj.get("redirect_url"),
        )
        opps.append(opp)
        db.session.add(opp)
    db.session.commit()

    print(f"✅ Seed complete: {len(users)} users, {len(orgs)} orgs, {len(opps)} opps added.")
