from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='student')
    applications = db.relationship('PassApplication', backref='student', lazy=True)

class PassApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pass_type = db.Column(db.String(50), nullable=False)
    source = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='Pending')
    fee = db.Column(db.Integer, default=250)
    profile_pic_filename = db.Column(db.String(255))
    aadhar_pic_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    validity_end = db.Column(db.DateTime)
