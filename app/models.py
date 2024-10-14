from . import db
import json
from flask_login import UserMixin
from sqlalchemy.sql import func

# Model for story that contains id, user id, story (data), and changed story (gptdata)
class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(10000))
    title = db.Column(db.String(10000))
    gptdata = db.Column(db.String(10000))
    date = db.Column(db.DateTime(timezone = True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

# Model for user that contains id, email, name, and password
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    stories = db.relationship('Story')