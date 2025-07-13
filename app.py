import json
from flask import Flask, request
from db import db, User, Request, Items

# define db filename
db_filename = "found.db"
app = Flask(__name__)

# setup config
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_filename}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = True

# initialize app
db.init_app(app)
with app.app_context():
    # db.drop_all()
    db.create_all()

    # NOTE: DON'T UNCOMMENT UNLESS YOU WANT TO DELETE TABLES
    # User.__table__.drop(db.engine)
    # Request.__table__.drop(db.engine)

# generalized response formats
def success_response(data, code=200):
    return json.dumps({"success": True, "data": data}), code

def failure_response(message, code=404):
    return json.dumps({"success": False, "error": message}), code


@app.route("/")
def welcome():
    return 'Hi'

############# USER ROUTES #############

@app.route("/api/users/")
def get_all_users():
    """
    Get all users from User table
    """
    users = [u.serialize() for u in User.query.all()]
    return success_response(users)


@app.route("/api/users/<int:user_id>/")
def get_user(user_id):
    """
    Get specific users from User table by user_id
    """
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        return failure_response('User not found!')
    return success_response(user.serialize())


@app.route("/api/users/", methods=["POST"])
def create_user():
    """
    Create user
    """
    body = json.loads(request.data)
    user = User(
        profile_image = body.get("profile_image"),
        username = body.get("username"),
        bio = body.get("bio"),
        email = body.get("email"),
        phone = body.get("phone"),
        license_approve = body.get("license_approve")
    )
    db.session.add(user)
    db.session.commit()
    return success_response(user.serialize(), 201)


@app.route("/api/users/<int:user_id>/", methods=["DELETE"])
def delete_user(user_id):
    """
    Delete specific users from User table by user_id
    """
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        return failure_response('User not found!')
    db.session.delete(user)
    db.session.commit()
    return success_response(user.serialize())


############ ITEMS ROUTES #############

@app.route("/api/items/")
def get_items():
    """
    Gets all found items
    """
    return success_response({"items": [i.serialize() for i in Items.query.all()]})

@app.route("/api/users/<int:user_id>/items/", methods = ["POST"])
def create_item(user_id):
    """
    Creates a post for a found item
    """
    body = json.loads(request.data)
    new_item = Items(
        item_name = body.get("item name"),
        description = body.get("description"),
        location = body.get("location"),
        current_location = body.get("current location"),
        color = body.get("color"),
        finder_number = body.get("finder number"),
        finder_email = body.get("finder email"),
        image = body.get("image"),
        fulfilled = body.get("fulfilled"),
        user_id = user_id
        )
    if new_item.item_name is None or new_item.description is None or new_item.location is None or new_item.color is None or new_item.finder_email is None or new_item.finder_number is None or new_item.image is None or new_item.fulfilled is None:
        return failure_response("Not enough information provided", 400)
    db.session.add(new_item)
    db.session.commit()
    return success_response(new_item.serialize(), 201)

@app.route("/api/items/<int:item_id>/", methods = ["DELETE"])
def delete_item(item_id):
    """
    Deletes an item
    """
    item = Items.query.filter_by(id = item_id).first()
    if item is None:
        return failure_response("Item not found")
    db.session.delete(item)
    db.session.commit()
    return success_response(item.serialize())

@app.route("/api/items/<int:item_id>/")
def get_item(item_id):
    """
    Gets a specific item
    """
    item = Items.query.filter_by(id = item_id).first()
    if item is None:
        return failure_response("Item not found")
    return success_response(item.serialize())

############# LOST_REQUEST ROUTES #############

@app.route("/api/requests/")
def get_all_requests():
    """
    Get all requests from Request table
    """
    requests = [r.serialize() for r in Request.query.all()]
    return success_response(requests)


@app.route("/api/requests/<int:request_id>/")
def get_request(request_id):
    """
    Get specific requests from Request table by request_id
    """
    request = User.query.filter_by(id=request_id).first()
    if request is None:
        return failure_response('Request not found!')
    return success_response(request.serialize())


@app.route("/api/users/<int:user_id>/requests/", methods=["POST"])
def create_request(user_id):
    """
    Create request
    """
    body = json.loads(request.data)
    new_request = Request(
        item_name = body.get("item_name"),
        timestamp = body.get("timestamp"),
        category = body.get("category"),
        color = body.get("color"),
        description = body.get("description"),
        location_found = body.get("location_found"),
        fulfilled = False,
        user_id = user_id,
    )
    db.session.add(new_request)
    db.session.commit()
    return success_response(new_request.serialize(), 201)


@app.route("/api/requests/<int:request_id>/", methods=["DELETE"])
def delete_request(request_id):
    """
    Delete specific request from Request table by request_id
    """
    request = Request.query.filter_by(id=request_id).first()
    if request is None:
        return failure_response('Request not found!')
    db.session.delete(request)
    db.session.commit()
    return success_response(request.serialize())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)