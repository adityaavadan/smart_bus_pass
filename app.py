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
app.secret_key = os.environ.get('SECRET_KEY', 'smart_bus_pass_production_key_2026')

# Database Setup (Absolute path for Render stability)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'buspass.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Uploads Setup
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
QR_FOLDER = os.path.join(basedir, 'static', 'qrcodes')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='student') # 'student' or 'admin'
    applications = db.relationship('PassApplication', backref='student', lazy=True)

class PassApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pass_type = db.Column(db.String(50), nullable=False) # 'Monthly', 'Quarterly', 'Yearly'
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
        'pay_now': 'Pay Fee', 'view_pass': 'View Digital Pass', 'download_pdf': 'Download PDF',
        'status': 'Status', 'expiry': 'Expiry Date', 'source': 'Source', 'destination': 'Destination',
        'admin_panel': 'Admin Control Panel', 'total_revenue': 'Total Revenue', 'active_passes': 'Active Passes'
    },
    'hi': {
        'title': 'स्मार्टबस पास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'पंजीकरण',
        'dashboard': 'डैशबोर्ड', 'logout': 'लॉगआउट', 'apply_pass': 'नया पास आवेदन',
        'routes': 'बस मार्ग', 'profile': 'मेरी प्रोफाइल', 'renewal': 'पास नवीनीकरण',
        'pay_now': 'शुल्क भुगतान', 'view_pass': 'डिजिटल पास देखें', 'download_pdf': 'पीडीएफ डाउनलोड',
        'status': 'स्थिति', 'expiry': 'समाप्ति तिथि', 'source': 'स्रोत', 'destination': 'गंतव्य',
        'admin_panel': 'एडमिन पैनल', 'total_revenue': 'कुल आय', 'active_passes': 'सक्रिय पास'
    },
    'mr': {
        'title': 'स्मार्टबस पास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'नोंदणी',
        'dashboard': 'डॅशबोर्ड', 'logout': 'लॉगआउट', 'apply_pass': 'नवीन पास अर्ज',
        'routes': 'बस मार्ग', 'profile': 'माझी प्रोफाईल', 'renewal': 'पास नूतनीकरण',
        'pay_now': 'शुल्क भरा', 'view_pass': 'डिजिटल पास पहा', 'download_pdf': 'पीडीएफ डाउनलोड',
        'status': 'स्थिती', 'expiry': 'समाप्ती तारीख', 'source': 'स्त्रोत', 'destination': 'गंतव्य',
        'admin_panel': 'एडमिन पॅनेल', 'total_revenue': 'एकूण महसूल', 'active_passes': 'सक्रिय पास'
    }
}

KOLHAPUR_VILLAGES = [
    "Kolhapur City", "Ichalkaranji", "Kagal", "Panhala", "Jaysingpur", "Gadhinglaj", 
    "Shirol", "Hatkanangale", "Ajara", "Chandgad", "Radhanagari", "Bhudargad",
    "Shahuwadi", "Bavada", "Karveer", "Gargoti", "Murgud", "Kurundwad"
]

# --- UTILITIES & INIT ---
with app.app_context():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(QR_FOLDER, exist_ok=True)
    db.create_all()

@app.context_processor
def inject_global_data():
    lang = session.get('lang', 'en')
    t_data = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    # Auto-add missing keys to prevent Jinja errors
    t_data.setdefault('admin_dashboard', t_data.get('admin_panel', 'Admin'))
    return dict(lang=lang, t=t_data, datetime=datetime, villages=KOLHAPUR_VILLAGES)

def check_expirations():
    """Helper to mark passes as expired if date passed"""
    now = datetime.utcnow()
    expired_count = PassApplication.query.filter(
        PassApplication.status == 'Approved',
        PassApplication.validity_end < now
    ).update({PassApplication.status: 'Expired'})
    if expired_count: db.session.commit()

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
        email, password = request.form['email'], request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session.update({'user_id': user.id, 'role': user.role, 'email': user.email})
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'student_dashboard'))
        flash('Invalid Credentials', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        if User.query.filter_by(email=email).first():
            flash('Email already in use', 'warning')
            return redirect(url_for('register'))
        
        # OTP Setup
        otp = str(random.randint(100000, 999999))
        session.update({
            'reg_email': email,
            'reg_password': generate_password_hash(request.form['password']),
            'reg_otp': otp
        })
        print(f"\n>>> SECURITY ALERT: OTP FOR {email} IS {otp} <<<\n")
        flash(f"OTP sent to {email}", "info")
        return redirect(url_for('verify_otp'))
    return render_template('register.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reg_email' not in session: return redirect(url_for('register'))
    if request.method == 'POST':
        if request.form['otp'] == session.get('reg_otp'):
            new_user = User(email=session['reg_email'], password=session['reg_password'])
            db.session.add(new_user)
            db.session.commit()
            session.clear()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        flash('Invalid OTP code', 'danger')
    return render_template('verify_otp.html')

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    check_expirations()
    user = User.query.get(session['user_id'])
    # Logic for expiration alerts
    expiring_soon = any(
        a.status == 'Approved' and a.validity_end and (a.validity_end - datetime.utcnow()).days <= 3
        for a in user.applications
    )
    return render_template('student_dashboard.html', applications=user.applications, user=user, expiring_soon=expiring_soon)

@app.route('/student/apply', methods=['GET', 'POST'])
def apply_pass():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        p_file, a_file = request.files.get('profile_pic'), request.files.get('aadhar_pic')
        if p_file and a_file:
            ts = int(datetime.utcnow().timestamp())
            p_name = secure_filename(f"profile_{ts}_{p_file.filename}")
            a_name = secure_filename(f"aadhar_{ts}_{a_file.filename}")
            p_file.save(os.path.join(app.config['UPLOAD_FOLDER'], p_name))
            a_file.save(os.path.join(app.config['UPLOAD_FOLDER'], a_name))
            
            # Distance-based fee calculation
            source, dest = request.form['source'], request.form['destination']
            base_fee = 150
            distance_factor = (len(source) + len(dest)) * 5
            total_fee = base_fee + distance_factor

            new_app = PassApplication(
                user_id=session['user_id'], pass_type=request.form['pass_type'],
                source=source, destination=dest, fee=total_fee,
                profile_pic_filename=p_name, aadhar_pic_filename=a_name
            )
            db.session.add(new_app)
            db.session.commit()
            flash('Application submitted successfully!', 'success')
            return redirect(url_for('student_dashboard'))
    return render_template('apply_pass.html', villages=KOLHAPUR_VILLAGES)

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    check_expirations()
    all_apps = PassApplication.query.all()
    stats = {
        'total_passes': len(all_apps),
        'active_passes': len([a for a in all_apps if a.status == 'Approved']),
        'pending_count': len([a for a in all_apps if a.status == 'Pending']),
        'total_revenue': sum([a.fee for a in all_apps if a.status == 'Approved'])
    }
    return render_template('admin_dashboard.html', applications=all_apps, stats=stats)

@app.route('/student/profile')
@app.route('/profile')
def student_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('profile.html', user=User.query.get(session['user_id']))

@app.route('/pay/<int:app_id>')
@app.route('/pay_pass/<int:app_id>')
def pay_pass(app_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    application = PassApplication.query.get_or_404(app_id)
    return render_template('payment.html', application=application, app_id=app_id)

@app.route('/print/<int:app_id>')
@app.route('/print_pass/<int:app_id>')
def print_pass(app_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    application = PassApplication.query.get_or_404(app_id)
    return render_template('print_pass.html', app=application)

@app.route('/renew/<int:app_id>')
@app.route('/renew_pass/<int:app_id>')
def renew_pass(app_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    flash('Renewal request received. Please pay the fee.', 'info')
    return redirect(url_for('pay_pass', app_id=app_id))

@app.route('/routes')
def bus_routes():
    routes_data = [
        {"bus_no": "K-12", "path": "Kolhapur -> Panhala", "frequency": "15 mins"},
        {"bus_no": "K-45", "path": "Kolhapur -> Ichalkaranji", "frequency": "10 mins"},
        {"bus_no": "K-08", "path": "Kolhapur -> Kagal", "frequency": "30 mins"},
        {"bus_no": "K-99", "path": "Kolhapur -> Jaysingpur", "frequency": "45 mins"}
    ]
    return render_template('routes.html', routes=routes_data)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/secret-admin-setup', methods=['GET', 'POST'])
def secret_admin_setup():
    if request.method == 'POST':
        email = request.form['email']
        if not User.query.filter_by(email=email).first():
            db.session.add(User(email=email, password=generate_password_hash(request.form['password']), role='admin'))
            db.session.commit()
            flash('Admin account created!', 'success')
            return redirect(url_for('login'))
    return render_template('register_admin.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
