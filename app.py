import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

# --- CONFIGURATION ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smart_bus_pass_secure_2026')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'buspass.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='student')
    applications = db.relationship('PassApplication', backref='owner', lazy=True)

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
    expiry_date = db.Column(db.DateTime)

# --- TRANSLATIONS ---
TRANSLATIONS = {
    'en': {'title': 'SmartPass', 'home': 'Home', 'login': 'Login', 'register': 'Register', 'dashboard': 'Dashboard', 'logout': 'Logout', 'apply_pass': 'Apply Pass', 'routes': 'Bus Routes', 'profile': 'Profile', 'renewal': 'Renew Pass', 'submit': 'Submit', 'approve': 'Fast Approval', 'view_pass': 'Digital Pass'},
    'hi': {'title': 'स्मार्टपास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'पंजीकरण', 'dashboard': 'डैशबोर्ड', 'logout': 'लॉगआउट', 'apply_pass': 'पास आवेदन', 'routes': 'बस मार्ग', 'profile': 'प्रोफ़ाइल', 'renewal': 'नवीनीकरण', 'submit': 'जमा करें', 'approve': 'तेजी से स्वीकृति', 'view_pass': 'डिजिटल पास'},
    'mr': {'title': 'स्मार्टपास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'नोंदणी', 'dashboard': 'डॅशबोर्ड', 'logout': 'लॉगआउट', 'apply_pass': 'अर्ज करा', 'routes': 'बस मार्ग', 'profile': 'प्रोफाईल', 'renewal': 'नूतनीकरण', 'submit': 'प्रस्तुत करा', 'approve': 'त्वरीत मान्यता', 'view_pass': 'डिजिटल पास'}
}
VILLAGES = ["Kolhapur City", "Ichalkaranji", "Kagal", "Panhala", "Jaysingpur", "Gadhinglaj", "Shirol", "Hatkanangale"]

# --- INITIALIZATION ---
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'static', 'qrcodes'), exist_ok=True)
    db.create_all()

@app.context_processor
def inject_translations():
    lang = session.get('lang', 'en')
    t_data = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    # Helper to prevent missing key errors in templates
    t_data.setdefault('admin_dashboard', 'Admin Panel')
    return dict(lang=lang, t=t_data, datetime=datetime)

# --- GENERAL ROUTES ---
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
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
        
        # OTP Simulation
        otp = str(random.randint(100000, 999999))
        session.update({
            'reg_email': email,
            'reg_password': generate_password_hash(request.form['password']),
            'reg_otp': otp
        })
        print(f"\n--- [OTP FOR {email}]: {otp} ---\n")
        flash(f"OTP sent to {email} (Check server logs)", "info")
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
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        flash('Invalid OTP', 'danger')
    return render_template('verify_otp.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- STUDENT ROUTES ---
@app.route('/student/dashboard')
def student_dashboard():
    if not session.get('user_id'): return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('student_dashboard.html', applications=user.applications, user=user, expiring_soon=False)

@app.route('/student/apply', methods=['GET', 'POST'])
def apply_pass():
    if not session.get('user_id'): return redirect(url_for('login'))
    if request.method == 'POST':
        p_file = request.files.get('profile_pic')
        a_file = request.files.get('aadhar_pic')
        if p_file and a_file:
            ts = int(datetime.utcnow().timestamp())
            p_name = secure_filename(f"p_{ts}_{p_file.filename}")
            a_name = secure_filename(f"a_{ts}_{a_file.filename}")
            p_file.save(os.path.join(app.config['UPLOAD_FOLDER'], p_name))
            a_file.save(os.path.join(app.config['UPLOAD_FOLDER'], a_name))
            
            fee = 100 + (len(request.form['source']) + len(request.form['destination'])) * 10
            new_app = PassApplication(
                user_id=session['user_id'],
                pass_type=request.form['pass_type'],
                source=request.form['source'],
                destination=request.form['destination'],
                profile_pic_filename=p_name,
                aadhar_pic_filename=a_name,
                fee=fee
            )
            db.session.add(new_app)
            db.session.commit()
            return redirect(url_for('student_dashboard'))
    return render_template('apply_pass.html', villages=VILLAGES)

@app.route('/profile')
@app.route('/student/profile')
def student_profile():
    if not session.get('user_id'): return redirect(url_for('login'))
    return render_template('profile.html', user=User.query.get(session['user_id']))

# --- ADMIN ROUTES ---
@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    apps = PassApplication.query.all()
    stats = {'total_passes': len(apps), 'active_passes': len([a for a in apps if a.status=='Approved']), 'pending_count': len([a for a in apps if a.status=='Pending']), 'total_revenue': sum([a.fee for a in apps if a.status=='Approved'])}
    return render_template('admin_dashboard.html', applications=apps, stats=stats)

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

# --- BUS ROUTES ---
@app.route('/routes')
def bus_routes():
    routes_list = [
        {"bus_no": "K-101", "path": "Kolhapur -> Panhala", "frequency": "15m"},
        {"bus_no": "K-202", "path": "Kolhapur -> Kagal", "frequency": "20m"},
        {"bus_no": "K-303", "path": "Kolhapur -> Ichalkaranji", "frequency": "10m"}
    ]
    return render_template('routes.html', routes=routes_list)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
