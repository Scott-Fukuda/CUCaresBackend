import os
from dotenv import load_dotenv

# Load environment variables from .env file FIRST
load_dotenv()

from flask_migrate import Migrate
from config import StagingConfig
from extensions.cors import init_cors
from extensions.firebase import init_firebase
from flask import Flask, send_from_directory
from db import db
from routes.users import users_bp 
from routes.carpool import carpool_bp 
from routes.cars import cars_bp 
from routes.emails import emails_bp 
from routes.friends import friends_bp 
from routes.misc import misc_bp 
from routes.multiopp import multiopp_bp 
from routes.opps import opps_bp 
from routes.orgs import orgs_bp 
from routes.rides import rides_bp 
from routes.service import service_bp 
from routes.setup import setup_bp 
from routes.waivers import waivers_bp

# define db filename
db_filename = "cucares.db"
app = Flask(__name__, static_folder='build', static_url_path='')

app.register_blueprint(users_bp)
app.register_blueprint(carpool_bp)
app.register_blueprint(cars_bp)
app.register_blueprint(emails_bp)
app.register_blueprint(friends_bp)
app.register_blueprint(misc_bp)
app.register_blueprint(multiopp_bp)
app.register_blueprint(opps_bp)
app.register_blueprint(orgs_bp)
app.register_blueprint(rides_bp)
app.register_blueprint(service_bp)
app.register_blueprint(setup_bp)
app.register_blueprint(waivers_bp)

env = os.environ.get("MY_ENV", "production")

# Load environment variables from .env file
load_dotenv()

app.secret_key = os.environ["FLASK_SECRET_KEY"]
init_cors(app, env)
init_firebase()

if env == "staging":
    app.config.from_object(StagingConfig)

# setup config
database_url = os.environ.get('DATABASE_URL', f"sqlite:///{db_filename}")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = os.environ.get('FLASK_ENV') == 'development'

# initialize app
db.init_app(app)
migrate = Migrate(app, db)

# with app.app_context():
#     # For app migrations don't create all tables
#     # db.create_all()

#     # NOTE: DON'T UNCOMMENT UNLESS YOU WANT TO DELETE TABLES
#     User.__table__.drop(db.engine)
#     Opportunity.__table__.drop(db.engine)
#     Organization.__table__.drop(db.engine)
#     UserOpportunity.__table__.drop(db.engine)
#     Friendship.__table__.drop(db.engine)
#     MultiOpportunity.__table__.drop(db.engine)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    # If the request matches a static file, serve it
    file_path = os.path.join(app.static_folder, path)
    if path != "" and os.path.exists(file_path):
        return send_from_directory(app.static_folder, path)
    # Otherwise, serve index.html for React Router
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host="0.0.0.0", port=port, debug=False)