from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime
import datetime

db = SQLAlchemy()

# association model — used because a user is related to an opportunity in a more complex way
class UserOpportunity(db.Model):
    __tablename__ = 'user_opportunity'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunity.id', ondelete='CASCADE'), primary_key=True)
    registered = db.Column(db.Boolean, default=False)
    attended = db.Column(db.Boolean, default=False)
    driving = db.Column(db.Boolean, default=False)

    user = db.relationship("User", back_populates="user_opportunities")
    opportunity = db.relationship("Opportunity", back_populates="user_opportunities")

# association tables
user_organization = db.Table(
    "user_organization",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("organization_id", db.Integer, db.ForeignKey("organization.id"), primary_key=True)
)

class ApprovedEmail(db.Model):
    __tablename__ = "approved_emails"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String, nullable=False, unique=True)
    added_date = db.Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    
    def __init__(self, **kwargs):
        self.email = kwargs.get("email")
        self.added_date = kwargs.get("added_date", datetime.datetime.utcnow())
    
    def serialize(self):
        return {
            "id": self.id,
            "email": self.email,
            "added_date": self.added_date
        }

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
    car_seats = db.Column(db.Integer, nullable=False, default=0)
    bio = db.Column(db.String, nullable=True)
    registration_date = db.Column(DateTime, nullable=False, default=datetime.datetime.utcnow) 
    carpool_waiver_signed = db.Column(db.Boolean, default=False)

    multiopps_hosted = db.relationship("MultiOpportunity", back_populates="host_user")

    organizations = db.relationship(
        "Organization", 
        secondary=user_organization, 
        back_populates="users", 
        cascade="all"
    )  

    user_opportunities = db.relationship('UserOpportunity', back_populates='user', cascade="all", passive_deletes=True)

    opportunities_hosted = db.relationship(
        "Opportunity", 
        back_populates="host_user",
        cascade="all, delete-orphan"
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

    waiver = db.relationship("Waiver", back_populates="user")
    ride_riders = db.relationship("RideRider", back_populates="user")
    car = db.relationship("Car", back_populates="user", uselist=False)

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
        self.car_seats = kwargs.get("car_seats", 0)
        self.bio = kwargs.get("bio", None)
        self.registration_date = kwargs.get("registration_date", datetime.datetime.utcnow())
        self.carpool_waiver_signed = kwargs.get("carpool_waiver_signed", False)
        self.multiopps_hosted = kwargs.get("multiopps_hosted", [])


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
            "car_seats": self.car.seats if self.car else self.car_seats,
            "bio": self.bio,
            "registration_date": self.registration_date,
            "carpool_waiver_signed": self.carpool_waiver_signed,
            "organizations": [l.serialize() for l in self.organizations],
            "opportunities_hosted": [{"name": l.name} for l in self.opportunities_hosted], 
            "opportunities_involved": [
                {
                    "name": uo.opportunity.name,
                    "registered": uo.registered,
                    "attended": uo.attended,
                    "driving": uo.driving,
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
    date_created = db.Column(db.String, nullable=True, default="")
    multiopps_hosted = db.relationship("MultiOpportunity", back_populates="host_org")

    users = db.relationship(
        "User", 
        secondary=user_organization, 
        back_populates="organizations"
    )

    opportunities_hosted = db.relationship(
        "Opportunity",
        back_populates="host_org"
    )

    waiver = db.relationship("Waiver", back_populates="organization")

    host_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    def __init__(self, **kwargs):
        self.name = kwargs.get("name")
        self.description = kwargs.get("description")
        self.member_count = kwargs.get("member_count", 0)
        self.type = kwargs.get("type")
        self.points = kwargs.get("points", 0)
        self.host_user_id = kwargs.get("host_user_id")
        self.approved = kwargs.get("approved", False)
        self.date_created = kwargs.get("date_created", "")
        self.multiopps_hosted = kwargs.get("multiopps_hosted", [])

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
            "date_created": self.date_created,
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
    causes = db.Column(db.JSON, nullable=True, default=list)
    tags = db.Column(db.JSON, nullable=True, default=list)
    address = db.Column(db.String, nullable=False)
    nonprofit = db.Column(db.String, nullable=True)
    total_slots = db.Column(db.Integer, nullable=True)
    image = db.Column(db.String, nullable=True)
    approved = db.Column(db.Boolean, default=False, nullable=False)
    host_org_name = db.Column(db.String, nullable=True)
    comments = db.Column(db.JSON, nullable=True, default=list)
    qualifications = db.Column(db.JSON, nullable=True, default=list)
    recurring = db.Column(db.String, nullable=False, default="once")
    visibility = db.Column(db.JSON, nullable=True, default=list)
    attendance_marked = db.Column(db.Boolean, default=False)
    redirect_url = db.Column(db.String, nullable=True, default=None)
    actual_runtime = db.Column(db.Integer, nullable=True)
    allow_carpool = db.Column(db.Boolean, nullable=False, default=False)

    host_org_id = db.Column(db.Integer, db.ForeignKey("organization.id"))
    host_org = db.relationship("Organization", back_populates="opportunities_hosted")

    host_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    host_user = db.relationship("User", back_populates="opportunities_hosted")

    user_opportunities = db.relationship('UserOpportunity', back_populates='opportunity', cascade="all", passive_deletes=True)
    carpool = db.relationship("Carpool", back_populates="opportunity", cascade="all, delete-orphan", passive_deletes=True, uselist=False)
    multiopp_id = db.Column(db.Integer, db.ForeignKey("multi_opportunity.id"), nullable=True)
    multi_opportunity = db.relationship("MultiOpportunity", back_populates="opportunities")

    def __init__(self, **kwargs):
        self.name = kwargs.get("name")
        self.description = kwargs.get("description")
        self.date = kwargs.get("date")
        self.duration = kwargs.get("duration") # duration in mintues
        self.causes = kwargs.get("causes", [])
        self.tags = kwargs.get("tags", [])
        self.address = kwargs.get("address")
        self.nonprofit = kwargs.get("nonprofit")
        self.total_slots = kwargs.get("total_slots")
        self.image = kwargs.get("image")
        self.host_org_id = kwargs.get("host_org_id")
        self.host_user_id = kwargs.get("host_user_id")
        self.approved = kwargs.get("approved", False)
        self.host_org_name = kwargs.get("host_org_name")
        self.comments = kwargs.get("comments", [])
        self.qualifications = kwargs.get("qualifications", [])
        self.recurring = kwargs.get("recurring", "once")
        self.visibility = kwargs.get("visibility", [])
        self.attendance_marked = kwargs.get("attendance_marked", False)
        self.redirect_url = kwargs.get("redirect_url", None)
        self.actual_runtime = kwargs.get("actual_runtime", None)
        self.multiopp_id = kwargs.get("multiopp_id", None)
        self.multi_opportunity = kwargs.get("multi_opportunity", None)
        self.allow_carpool = kwargs.get("allow_carpool", False)

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "date": self.date,
            "duration": self.duration,
            "causes": self.causes or [],
            "tags": self.tags or [],
            "address": self.address,
            "nonprofit": self.nonprofit,
            "total_slots": self.total_slots,
            "image": self.image,
            "host_org_id": self.host_org_id,
            "host_user_id": self.host_user_id,
            "host_org_name": self.host_org_name,
            "approved": self.approved,
            "comments": self.comments or [],
            "qualifications": self.qualifications or [],
            "recurring": self.recurring,
            "visibility": self.visibility or [],
            "attendance_marked": self.attendance_marked,
            "redirect_url": self.redirect_url,
            "actual_runtime": self.actual_runtime,
            "multiopp_id": self.multiopp_id,
            "multiopp": (
                {
                    "id": self.multi_opportunity.id,
                    "name": self.multi_opportunity.name,
                    "start_date": self.multi_opportunity.start_date.isoformat() if self.multi_opportunity.start_date else None,
                    "days_of_week": self.multi_opportunity.days_of_week,
                    "week_frequency": self.multi_opportunity.week_frequency,
                    "week_recurrences": self.multi_opportunity.week_recurrences,
                    "created_at": self.multi_opportunity.created_at.isoformat() if self.multi_opportunity.created_at else None
                }
                if self.multi_opportunity else None
            ),
            "allow_carpool": self.allow_carpool,
            "carpool_id": self.carpool.id if self.carpool else None,
            "involved_users": [
                {
                    "user": uo.user.name,
                    "id": uo.user.id,
                    "email": uo.user.email,
                    "phone": uo.user.phone,
                    "registered": uo.registered,
                    "attended": uo.attended,
                    "driving": uo.driving,
                    "profile_image": uo.user.profile_image,
                }
                for uo in self.user_opportunities
            ]
        }
    
class Waiver(db.Model):
    __tablename__ = "waiver"

    id = db.Column(db.Integer, primary_key=True)
    typed_name = db.Column(db.String, nullable=False)
    signed_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    type = db.Column(db.String, nullable=False)
    content = db.Column(db.String, nullable=False)
    ip_address = db.Column(db.String, nullable=False)
    checked_consent = db.Column(db.Boolean, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=True)

    user = db.relationship("User", back_populates="waiver")
    organization = db.relationship("Organization", back_populates="waiver")

    def serialize(self): 
        return {
            "id": self.id,
            "typed_name": self.typed_name,
            "signed_at": self.signed_at,
            "type": self.type,
            "content": self.content,
            "ip_address": self.ip_address,
            "checked_consent": self.checked_consent,
            "user_id": self.user_id,
            "organization_id": self.organization_id
        }


class MultiOpportunity(db.Model):
    __tablename__ = "multi_opportunity"
    # used for multiopp itself
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)
    causes = db.Column(db.JSON, nullable=True, default=list)
    tags = db.Column(db.JSON, nullable=True, default=list)
    address = db.Column(db.String, nullable=False)
    nonprofit = db.Column(db.String, nullable=True)
    image = db.Column(db.String, nullable=True)
    approved = db.Column(db.Boolean, default=False, nullable=False)
    host_org_name = db.Column(db.String, nullable=True)
    qualifications = db.Column(db.JSON, nullable=True, default=list)
    visibility = db.Column(db.JSON, nullable=True, default=list)
    host_org_id = db.Column(db.Integer, db.ForeignKey("organization.id"))
    host_org = db.relationship("Organization", back_populates="multiopps_hosted")
    host_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    host_user = db.relationship("User", back_populates="multiopps_hosted")

    # used to pass down to opportunities
    redirect_url = db.Column(db.String, nullable=True, default=None)
    total_slots = db.Column(db.Integer, nullable=True)
    # this is all from opportunity except for comments, recurring, attendance_marked, actual_runtime


    # these are the ones that vary by each opportunity (used for default values)
    # - date, duration, comments, attendance_marked, user_opportunities, actual_runtime

    # non-editable for each opportunity
    # - name, description, causes, tags, address, nonprofit, host_org_name, qualifications, visibility, host_org_id, host_org, host_user_id, host_user
    
    # recurrence definition
    start_date = db.Column(db.DateTime, nullable=False)
    days_of_week = db.Column(db.JSON, nullable=False, default=list)
    week_frequency = db.Column(db.Integer, nullable=True)
    week_recurrences = db.Column(db.Integer, nullable=True, default=4)
    address = db.Column(db.String, nullable=False)
    nonprofit = db.Column(db.String, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    opportunities = db.relationship(
        "Opportunity", back_populates="multi_opportunity", cascade="all"
    )

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "causes": self.causes,
            "tags": self.tags,
            "address": self.address,
            "nonprofit": self.nonprofit,
            "image": self.image,
            "approved": self.approved,
            "host_org_name": self.host_org_name,
            "qualifications": self.qualifications,
            "visibility": self.visibility,
            "host_org_id": self.host_org_id,
            "host_user_id": self.host_user_id,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "days_of_week": self.days_of_week,
            "week_frequency": self.week_frequency,
            "week_recurrences": self.week_recurrences,

            "opportunities": [
                {
                    "id": opp.id,
                    "date": opp.date,
                    "duration": opp.duration,
                    "total_slots": opp.total_slots,
                    "involved_users": [
                        {
                            "id": uo.user.id,
                            "name": uo.user.name,
                            "profile_image": uo.user.profile_image,
                        }
                        for uo in getattr(opp, "user_opportunities", []) or []
                        if getattr(uo, "user", None)  # ensure no null user
                    ],
                    "allow_carpool": opp.allow_carpool
                }
                for opp in getattr(self, "opportunities", []) or []
            ],    
    }

class Carpool(db.Model):
    __tablename__ = "carpool"
    id = db.Column(db.Integer, primary_key=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunity.id", ondelete="CASCADE"), nullable=False)

    rides = db.relationship("Ride", back_populates="carpool", cascade="all, delete-orphan", passive_deletes=True)
    opportunity = db.relationship("Opportunity", back_populates="carpool")

    def serialize(self):
        return {
            "id": self.id,
            "opportunity_id": self.opportunity_id
        }

class RideRider(db.Model):
    __tablename__ = "ride_riders"
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey("ride.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    pickup_location = db.Column(db.String, nullable=False)
    notes = db.Column(db.String, nullable=True)

    ride = db.relationship("Ride", back_populates="ride_riders")
    user = db.relationship("User", back_populates="ride_riders")

    def serialize(self):
        return {
            "id": self.id,
            "ride_id": self.ride_id,
            "user_id": self.user_id,
            "profile_image": self.user.profile_image,
            "name": self.user.name,
            "pickup_location": self.pickup_location,
            "notes": self.notes
        }

class Ride(db.Model):
    __tablename__ = "ride"
    id = db.Column(db.Integer, primary_key=True)
    carpool_id = db.Column(db.Integer, db.ForeignKey("carpool.id"), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    carpool = db.relationship("Carpool", back_populates="rides")
    ride_riders = db.relationship("RideRider", back_populates="ride", cascade="all, delete-orphan")
    driver = db.relationship("User", foreign_keys=[driver_id])

    def serialize(self):
        return {
            "id": self.id,
            "carpool_id": self.carpool_id,
            "driver_id": self.driver_id,
            "driver_name": self.driver.name if self.driver else None,
            "driver_seats": self.driver.car.seats if self.driver and self.driver.car else None,
            "riders": [rider.serialize() for rider in self.ride_riders]
        }

class Car(db.Model):
    __tablename__ = "car"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    color = db.Column(db.String, nullable=True)
    model = db.Column(db.String, nullable=True)
    seats = db.Column(db.Integer, nullable=False)
    license_plate = db.Column(db.String, nullable=True)

    user = db.relationship("User", back_populates="car")

    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "color": self.color,
            "model": self.model,
            "seats": self.seats,
            "license_plate": self.license_plate
        }
