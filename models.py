from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='student') # 'student' or 'admin'
    full_name = db.Column(db.String(100), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    applications = db.relationship('PassApplication', backref='student', lazy=True)

class PassApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pass_type = db.Column(db.String(50), nullable=False) # e.g., 'Monthly', 'Quarterly'
    source = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pending') # Pending, Pending Payment, Approved, Rejected, Expired
    fee = db.Column(db.Integer, nullable=False, default=0)
    profile_pic_filename = db.Column(db.String(255), nullable=True)
    aadhar_pic_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    validity_start = db.Column(db.DateTime, nullable=True)
    validity_end = db.Column(db.DateTime, nullable=True)
    qr_code_data = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<PassApplication {self.id} - {self.status}>'
