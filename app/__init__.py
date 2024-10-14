import os 
from flask import Flask
from os import path
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Load environment variables
load_dotenv()

# Initialize the database instance
db = SQLAlchemy()
DB_NAME = "database.db"

def create_app():
    app = Flask(__name__)

    # Database configuration
    app.config['SECRET_KEY'] = 'dfahdsjfheal'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'

    # Initialize SQLAlchemy and Flask-Migrate
    db.init_app(app)

    from .auth import auth
    app.register_blueprint(auth, url_prefix='/')
    from .views import views
    app.register_blueprint(views)


    from .models import User

    with app.app_context():
        db.create_all()

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))


    # Import and register blueprints
    return app


def create_database(app):
    if not path.exists('website/' + DB_NAME):
        db.create_all(app=app)
        print('Created Database!')