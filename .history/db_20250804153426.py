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

organization_opportunity = db.Table(
    "organization_opportunity",
    db.Column("organization_id", db.Integer, db.ForeignKey("organization.id"), primary_key=True),
    db.Column("opportunity_id", db.Integer, db.ForeignKey("opportunity.id"), primary_key=True)
)

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)    
    profile_image = db.Column(db.String, nullable=True)  # string must be a url
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    password = db.Column(db.String, nullable=False)
    points = db.Column(db.Integer, nullable=False) 

    organizations = db.relationship(
        "Organization", 
        secondary=user_organization, 
        back_populates="users", 
        cascade="all"
    )  

    user_opportunities = db.relationship('UserOpportunity', back_populates='user')

    opportunities_hosted = db.relationship(
        "Opportunity", 
        back_populates="host_user"
    )  

    def __init__(self, **kwargs):
        self.profile_image = kwargs.get("profile_image")
        self.name = kwargs.get("name")
        self.email = kwargs.get("email")
        self.password = kwargs.get("password")
        self.points = kwargs.get("points", 0)

    def serialize(self):
        return {
            "id": self.id,
            "profile_image": self.profile_image,
            "name": self.name,
            "email": self.email,
            "points": self.points,
            "organizations": [l.serialize() for l in self.organizations],
            "opportunities_hosted": [{"name": l.name} for l in self.opportunities_hosted], 
            "opportunities_involved": [
                {
                    "name": uo.opportunity.name,
                    "registered": uo.registered,
                    "attended": uo.attended,
                } for uo in self.user_opportunities
            ]
        }

class Organization(db.Model):
    __tablename__ = "organization"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)
    member_count = db.Column(db.Integer, nullable=False)
    points = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String, nullable=False)

    users = db.relationship(
        "User", 
        secondary=user_organization, 
        back_populates="organizations"
    )

    opportunities_attended = db.relationship(
        "Opportunity",
        secondary=organization_opportunity,
        back_populates="participating_organizations"
    )

    host_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    def __init__(self, **kwargs):
        self.name = kwargs.get("name")
        self.description = kwargs.get("description")
        self.member_count = kwargs.get("member_count", 0)
        self.type = kwargs.get("type")
        self.points = kwargs.get("points", 0)
        self.host_user_id = kwargs.get("host_user_id")

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "member_count": self.member_count,
            "type": self.type,
            "points": self.points,
            "host_user_id": self.host_user_id,
            "users": [
                { 
                    "name": user.name,
                    "id": user.id,
                } for user in self.users],
            "opportunities_attended": [ 
                {
                    "name": opp.name,
                    "id": opp.id
                } for opp in self.opportunities_attended]
        }

class Opportunity(db.Model):
    __tablename__ = "opportunity"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)
    date = db.Column(DateTime, nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    cause = db.Column(db.String, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)

    host_org_id = db.Column(db.Integer, db.ForeignKey("organization.id"))
    host_org = db.relationship("Organization", backref=db.backref("hosted_opportunities", lazy="dynamic"))

    host_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    host_user = db.relationship("User", back_populates="opportunities_hosted")

    user_opportunities = db.relationship('UserOpportunity', back_populates='opportunity')
    
    participating_organizations = db.relationship(
        "Organization",
        secondary=organization_opportunity,
        back_populates="opportunities_attended"
    )

    def __init__(self, **kwargs):
        self.name = kwargs.get("name")
        self.description = kwargs.get("description")
        self.date = kwargs.get("date")
        self.duration = kwargs.get("duration") # duration in mintues
        self.cause = kwargs.get("cause")
        self.completed = kwargs.get("completed", False)
        self.host_org_id = kwargs.get("host_org_id")
        self.host_user_id = kwargs.get("host_user_id")

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "date": self.date,
            "duration": self.duration,
            "cause": self.cause,
            "completed": self.completed,
            "host_org_id": self.host_org_id,
            "host_user_id": self.host_user_id,
            "involved_users": [
                {
                    "user": uo.user.name,
                    "id": uo.user.id,
                    "registered": uo.registered,
                    "attended": uo.attended,
                }
                for uo in self.user_opportunities
            ],
            "participating_organizations": [org.name for org in self.participating_organizations]
        }
