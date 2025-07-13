from flask_sqlalchemy import SQLAlchemy
import datetime
db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True, auto_increment=True)    
    profile_image = db.Column(db.String, nullable=True) # string must be a url
    username = db.Column(db.String, nullable=False)
    bio = db.Column(db.String, nullable=True)
    email = db.Column(db.String, nullable=False)
    phone = db.Column(db.String, nullable=False)
    license_approve = db.Column(db.Boolean, nullable=False)
    requests = db.relationship("Request", cascade="delete")
    items = db.relationship("Items", cascade="delete")

    def __init__(self, **kwargs):
        self.profile_image = kwargs.get("profile_image")
        self.username = kwargs.get("username")
        self.bio = kwargs.get("bio")
        self.email = kwargs.get("email")
        self.phone = kwargs.get("phone")
        self.license_approve = kwargs.get("license_approve")

    def serialize(self):
        return {
            "id": self.id,
            "profile_image": self.profile_image,
            "username": self.username,
            "bio": self.bio,
            "email": self.email,
            "phone": self.phone,
            "license_approve": self.license_approve,
            "requests": [l.serialize() for l in self.requests]
        }

class Request(db.Model):    
    __tablename__ = "request"    
    id = db.Column(db.Integer, primary_key=True, auto_increment=True) 
    item_name = db.Column(db.String, nullable=False)
    timestamp = db.Column(db.String, nullable=True)
    category = db.Column(db.String, nullable=False)   
    color = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)
    location_found = db.Column(db.String, nullable=True)
    fulfilled = db.Column(db.Boolean, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    def __init__(self, **kwargs):
        self.item_name = kwargs.get("item_name")
        self.timestamp = kwargs.get("timestamp")
        self.category = kwargs.get("category")
        self.color = kwargs.get("color")
        self.description = kwargs.get("description")
        self.location_found = kwargs.get("location_found")
        self.fulfilled = kwargs.get("fulfilled", False)
        self.user_id = kwargs.get("user_id")


    def serialize(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "color": self.color,
            "description": self.description,
            "location_found": self.location_found,
            "fulfilled": self.fulfilled,
            "user_id": self.user_id
        }
    

class Items(db.Model):
    """
    Items Model
    """
    __tablename__ = "items"
    id = db.Column(db.Integer, primary_key = True, autoincrement = True)
    item_name = db.Column(db.String, nullable = False)
    timestamp = db.Column(db.Integer, nullable = False)
    description = db.Column(db.String, nullable = True) 
    location = db.Column(db.String, nullable = False) 
    current_location = db.Column(db.String, nullable = False) 
    color = db.Column(db.String, nullable = False)
    finder_number = db.Column(db.Integer, nullable = False) 
    finder_email = db.Column(db.String, nullable = False) 
    image = db.Column(db.String, nullable = False) 
    fulfilled = db.Column(db.Boolean, nullable = False) 
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), \
                         nullable=False)

    def __init__(self, **kwargs):
        """
        Initialized Items entry
        """
        self.item_name = kwargs.get("item name", "")
        self.description = kwargs.get("description","")
        self.timestamp = datetime.datetime.now() 
        self.location = kwargs.get("location", "")
        self.current_location = kwargs.get("current location","")
        self.color = kwargs.get("color","")
        self.finder_number = kwargs.get("finder number",0)
        self.finder_email = kwargs.get("finder email","")
        self.image = kwargs.get("image", "")
        self.fulfilled = kwargs.get("fulfilled",False)
        self.user_id = kwargs.get("user_id")


    def serialize(self):
        """"
        Serializes a item object
        """
        return {
            "id": self.id,
            "item name": self.item_name,
            "description": self.description,
            "time created": self.timestamp,
            "location": self.location,
            "currnet location": self.current_location,
            "color": self.color,
            "finder number": self.finder_number,
            "finder email": self.finder_email,
            "image": self.image,
            "fulfilled": self.fulfilled,
            "user_id": self.user_id
        } 