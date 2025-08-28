from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime
import datetime

db = SQLAlchemy()

# association model — used because a user is related to an opportunity in a more complex way
class UserOpportunity(db.Model):
    __tablename__ = 'user_opportunity'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunity.id'), primary_key=True)
    registered = db.Column(db.Boolean, default=False)
    attended = db.Column(db.Boolean, default=False)

    user = db.relationship("User", back_populates="user_opportunities")
    opportunity = db.relationship("Opportunity", back_populates="user_opportunities")

# association tables
user_organization = db.Table(
    "user_organization",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("organization_id", db.Integer, db.ForeignKey("organization.id"), primary_key=True)
)

# Friendship model
class Friendship(db.Model):
    __tablename__ = "friendship"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    accepted = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relationships - these will be set during request processing
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    requester = db.relationship("User", foreign_keys=[requester_id], back_populates="sent_friend_requests")
    receiver = db.relationship("User", foreign_keys=[receiver_id], back_populates="received_friend_requests")

    def __init__(self, **kwargs):
        self.accepted = kwargs.get("accepted", False)
        # requester_id and receiver_id will be set during request processing

    def serialize(self):
        return {
            "id": self.id,
            "accepted": self.accepted
        }

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)    
    profile_image = db.Column(db.String, nullable=True)  # string must be a url
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    phone = db.Column(db.String, nullable=False)
    points = db.Column(db.Integer, nullable=False)
    interests = db.Column(db.JSON, nullable=True, default=list)
    admin = db.Column(db.Boolean, default=False, nullable=False)
    gender = db.Column(db.String, nullable=True)
    graduation_year = db.Column(db.String, nullable=True)
    academic_level = db.Column(db.String, nullable=True)
    major = db.Column(db.String, nullable=True)
    birthday = db.Column(DateTime, nullable=True)
    registration_date = db.Column(DateTime, nullable=False, default=datetime.datetime.utcnow) 

    organizations = db.relationship(
        "Organization", 
        secondary=user_organization, 
        back_populates="users", 
        cascade="all"
    )  

    user_opportunities = db.relationship('UserOpportunity', back_populates='user', cascade="all", passive_deletes=True)

    opportunities_hosted = db.relationship(
        "Opportunity", 
        back_populates="host_user"
    )

    # Friendship relationships
    sent_friend_requests = db.relationship(
        "Friendship",
        foreign_keys=[Friendship.requester_id],
        back_populates="requester",
        cascade="all, delete-orphan"
    )
    
    received_friend_requests = db.relationship(
        "Friendship",
        foreign_keys=[Friendship.receiver_id],
        back_populates="receiver",
        cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        self.profile_image = kwargs.get("profile_image")
        self.name = kwargs.get("name")
        self.email = kwargs.get("email")
        self.phone = kwargs.get("phone")
        self.points = kwargs.get("points", 0)
        self.interests = kwargs.get("interests", [])
        self.admin = kwargs.get("admin", False)
        self.gender = kwargs.get("gender")
        self.graduation_year = kwargs.get("graduation_year")
        self.academic_level = kwargs.get("academic_level")
        self.major = kwargs.get("major")
        self.birthday = kwargs.get("birthday")
        self.registration_date = kwargs.get("registration_date", datetime.datetime.utcnow())

    def serialize(self):
        return {
            "id": self.id,
            "profile_image": self.profile_image,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "points": self.points,
            "interests": self.interests or [],
            "admin": self.admin,
            "gender": self.gender,
            "graduation_year": self.graduation_year,
            "academic_level": self.academic_level,
            "major": self.major,
            "birthday": self.birthday,
            "registration_date": self.registration_date,
            "organizations": [l.serialize() for l in self.organizations],
            "opportunities_hosted": [{"name": l.name} for l in self.opportunities_hosted], 
            "opportunities_involved": [
                {
                    "name": uo.opportunity.name,
                    "registered": uo.registered,
                    "attended": uo.attended,
                } for uo in self.user_opportunities
            ],
            "friends": [
                {
                    "id": friend.id,
                    "name": friend.name,
                    "profile_image": friend.profile_image
                } for friend in self.get_accepted_friends()
            ]
        }
    
    def get_accepted_friends(self):
        """Get all accepted friends for this user"""
        # Get friendships where this user is the requester and they're accepted
        requester_friendships = Friendship.query.filter_by(
            requester_id=self.id, 
            accepted=True
        ).all()
        
        # Get friendships where this user is the receiver and they're accepted
        receiver_friendships = Friendship.query.filter_by(
            receiver_id=self.id, 
            accepted=True
        ).all()
        
        # Get the friend users
        friends = []
        for friendship in requester_friendships:
            friend = User.query.get(friendship.receiver_id)
            if friend:
                friends.append(friend)
        
        for friendship in receiver_friendships:
            friend = User.query.get(friendship.requester_id)
            if friend:
                friends.append(friend)
        
        return friends

class Organization(db.Model):
    __tablename__ = "organization"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)
    member_count = db.Column(db.Integer, nullable=False)
    points = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String, nullable=False)
    approved = db.Column(db.Boolean, default=False)

    users = db.relationship(
        "User", 
        secondary=user_organization, 
        back_populates="organizations"
    )

    opportunities_hosted = db.relationship(
        "Opportunity",
        back_populates="host_org"
    )

    host_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    def __init__(self, **kwargs):
        self.name = kwargs.get("name")
        self.description = kwargs.get("description")
        self.member_count = kwargs.get("member_count", 0)
        self.type = kwargs.get("type")
        self.points = kwargs.get("points", 0)
        self.host_user_id = kwargs.get("host_user_id")
        self.approved = kwargs.get("approved", False)

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "member_count": self.member_count,
            "type": self.type,
            "points": self.points,
            "host_user_id": self.host_user_id,
            "approved": self.approved,
            "users": [
                { 
                    "name": user.name,
                    "id": user.id,
                    "phone": user.phone,
                } for user in self.users],
            "opportunities_hosted": [ 
                {
                    "name": opp.name,
                    "id": opp.id
                } for opp in self.opportunities_hosted]
        }

class Opportunity(db.Model):
    __tablename__ = "opportunity"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)
    date = db.Column(DateTime, nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    cause = db.Column(db.String, nullable=True)
    address = db.Column(db.String, nullable=False)
    nonprofit = db.Column(db.String, nullable=True)
    total_slots = db.Column(db.Integer, nullable=True)
    image = db.Column(db.String, nullable=True)
    approved = db.Column(db.Boolean, default=False, nullable=False)
    host_org_name = db.Column(db.String, nullable=True)

    host_org_id = db.Column(db.Integer, db.ForeignKey("organization.id"))
    host_org = db.relationship("Organization", back_populates="opportunities_hosted")

    host_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    host_user = db.relationship("User", back_populates="opportunities_hosted")

    user_opportunities = db.relationship('UserOpportunity', back_populates='opportunity', cascade="all", passive_deletes=True)
    


    def __init__(self, **kwargs):
        self.name = kwargs.get("name")
        self.description = kwargs.get("description")
        self.date = kwargs.get("date")
        self.duration = kwargs.get("duration") # duration in mintues
        self.cause = kwargs.get("cause")
        self.address = kwargs.get("address")
        self.nonprofit = kwargs.get("nonprofit")
        self.total_slots = kwargs.get("total_slots")
        self.image = kwargs.get("image")
        self.host_org_id = kwargs.get("host_org_id")
        self.host_user_id = kwargs.get("host_user_id")
        self.approved = kwargs.get("approved", False)
        self.host_org_name = kwargs.get("host_org_name")

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "date": self.date,
            "duration": self.duration,
            "cause": self.cause,
            "address": self.address,
            "nonprofit": self.nonprofit,
            "total_slots": self.total_slots,
            "image": self.image,
            "host_org_id": self.host_org_id,
            "host_user_id": self.host_user_id,
            "host_org_name": self.host_org_name,
            "approved": self.approved,
            "involved_users": [
                {
                    "user": uo.user.name,
                    "id": uo.user.id,
                    "email": uo.user.email,
                    "phone": uo.user.phone,
                    "registered": uo.registered,
                    "attended": uo.attended,
                }
                for uo in self.user_opportunities
            ],

        }
