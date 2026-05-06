import os
import random
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- CONFIGURATION ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smart_bus_pass_production_2026')

# Database Setup (Absolute path for Render stability)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'buspass.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Uploads Setup
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

db = SQLAlchemy(app)

# --- DATABASE MODELS ---
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
    status = db.Column(db.String(20), default='Pending') # Pending, Approved, Rejected, Expired
    fee = db.Column(db.Integer, default=0)
    profile_pic_filename = db.Column(db.String(255))
    aadhar_pic_filename = db.Column(db.String(255))
    qr_code_data = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    validity_start = db.Column(db.DateTime)
    validity_end = db.Column(db.DateTime)

# --- TRANSLATIONS DATA ---
TRANSLATIONS = {
    'en': {
        'title': 'SmartBus Pass', 'home': 'Home', 'login': 'Login', 'register': 'Register',
        'dashboard': 'Dashboard', 'logout': 'Logout', 'apply_pass': 'Apply New Pass',
        'routes': 'Bus Routes', 'profile': 'My Profile', 'renewal': 'Renew Pass',
        'pay_now': 'Pay Fee', 'view_pass': 'View Digital Pass', 'download_pdf': 'Download PDF'
    },
    'hi': {
        'title': 'स्मार्टबस पास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'पंजीकरण',
        'dashboard': 'डैशबोर्ड', 'logout': 'लॉगआउट', 'apply_pass': 'नया पास आवेदन',
        'routes': 'बस मार्ग', 'profile': 'मेरी प्रोफाइल', 'renewal': 'पास नवीनीकरण',
        'pay_now': 'शुल्क भुगतान', 'view_pass': 'डिजिटल पास देखें', 'download_pdf': 'पीडीएफ डाउनलोड'
    },
    'mr': {
        'title': 'स्मार्टबस पास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'नोंदणी',
        'dashboard': 'डॅशबोर्ड', 'logout': 'लॉगआउट', 'apply_pass': 'नवीन पास अर्ज',
        'routes': 'बस मार्ग', 'profile': 'माझी प्रोफाईल', 'renewal': 'पास नूतनीकरण',
        'pay_now': 'शुल्क भरा', 'view_pass': 'डिजिटल पास पहा', 'download_pdf': 'पीडीएफ डाउनलोड'
    }
}

KOLHAPUR_VILLAGES = ["Kolhapur", "Ichalkaranji", "Kagal", "Panhala", "Jaysingpur", "Gadhinglaj", "Shirol", "Hatkanangale"]

# --- INITIALIZATION ---
with app.app_context():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    db.create_all()

@app.context_processor
def inject_global_data():
    lang = session.get('lang', 'en')
    t_data = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    t_data.update({'admin_dashboard': 'Admin Panel', 'status': 'Status', 'expiry': 'Expiry', 'pay_now': 'Pay Now', 'view_pass': 'View Pass', 'download_pdf': 'Download', 'renew': 'Renew'})
    return dict(lang=lang, t=t_data, datetime=datetime, villages=KOLHAPUR_VILLAGES)

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/set-language/<lang>')
def set_language(lang):
    session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session.update({'user_id': user.id, 'role': user.role, 'email': user.email})
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'student_dashboard'))
        flash('Invalid Email or Password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        
        # 1. Block non-gmail (optional but good)
        if not email.endswith('@gmail.com'):
            flash('Please use a real @gmail.com address', 'warning')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'warning')
            return redirect(url_for('register'))

        otp = str(random.randint(100000, 999999))
        session.update({
            'reg_email': email,
            'reg_password': generate_password_hash(request.form['password']),
            'reg_otp': otp
        })
        
        # --- SHOW OTP ON SCREEN (Simulation) ---
        flash(f"SECURITY CHECK: YOUR OTP IS {otp}", "info")
        
        return redirect(url_for('verify_otp'))
    return render_template('register.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reg_email' not in session: return redirect(url_for('register'))
    if request.method == 'POST':
        if request.form['otp'] == session.get('reg_otp'):
            db.session.add(User(email=session['reg_email'], password=session['reg_password']))
            db.session.commit()
            session.clear()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        flash('Incorrect OTP', 'danger')
    return render_template('verify_otp.html')

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('student_dashboard.html', applications=user.applications, user=user, expiring_soon=False)

@app.route('/student/apply', methods=['GET', 'POST'])
def apply_pass():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        new_app = PassApplication(user_id=session['user_id'], pass_type=request.form['pass_type'], 
                                  source=request.form['source'], destination=request.form['destination'],
                                  fee=250)
        db.session.add(new_app)
        db.session.commit()
        return redirect(url_for('student_dashboard'))
    return render_template('apply_pass.html', villages=KOLHAPUR_VILLAGES)

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    apps = PassApplication.query.all()
    stats = {'total_passes': len(apps), 'active_passes': len([a for a in apps if a.status == 'Approved']), 'pending_count': len([a for a in apps if a.status == 'Pending']), 'total_revenue': sum([a.fee for a in apps if a.status == 'Approved'])}
    return render_template('admin_dashboard.html', applications=apps, stats=stats)

@app.route('/profile')
@app.route('/student/profile')
def student_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('profile.html', user=User.query.get(session['user_id']))

@app.route('/pay/<int:app_id>')
def pay_pass(app_id): return render_template('payment.html', app_id=app_id)

@app.route('/print/<int:app_id>')
def print_pass(app_id): return render_template('print_pass.html', app=PassApplication.query.get(app_id))

@app.route('/renew/<int:app_id>')
def renew_pass(app_id): 
    flash('Renewal request received!', 'info')
    return redirect(url_for('student_dashboard'))

@app.route('/routes')
def bus_routes(): return render_template('routes.html', routes=[])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/secret-admin-setup', methods=['GET', 'POST'])
def secret_admin_setup():
    if request.method == 'POST':
        db.session.add(User(email=request.form['email'], password=generate_password_hash(request.form['password']), role='admin'))
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register_admin.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
