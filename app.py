import os
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- CONFIG ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smart_bus_pass_ultimate_2026')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'buspass.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')

db = SQLAlchemy(app)

# --- MODELS ---
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
    fee = db.Column(db.Integer, default=250)
    profile_pic_filename = db.Column(db.String(255))
    aadhar_pic_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    validity_end = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(days=30))

# --- TRANSLATIONS (Full and Complete) ---
TRANSLATIONS = {
    'en': {
        'title': 'SmartBus Pass', 'home': 'Home', 'login': 'Login', 'register': 'Register',
        'dashboard': 'Dashboard', 'logout': 'Logout', 'apply_pass': 'Apply New Pass',
        'routes': 'Bus Routes', 'profile': 'Profile', 'pay_now': 'Pay Fee',
        'view_pass': 'View Pass', 'download_pdf': 'Download', 'renew': 'Renew',
        'source': 'Source Village', 'destination': 'Destination', 'pass_type_label': 'Pass Type',
        'photo_label': 'Your Photo', 'aadhar_label': 'Aadhar Card', 'submit_btn': 'Submit Application',
        'admin_panel': 'Admin Control', 'status_label': 'Application Status', 'pending': 'Wait for Approval'
    },
    'hi': {
        'title': 'स्मार्टबस पास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'पंजीकरण',
        'dashboard': 'डैशबोर्ड', 'logout': 'लॉगआउट', 'apply_pass': 'नया पास आवेदन',
        'routes': 'बस मार्ग', 'profile': 'प्रोफ़ाइल', 'pay_now': 'शुल्क भुगतान',
        'view_pass': 'पास देखें', 'download_pdf': 'डाउनलोड', 'renew': 'नवीनीकरण',
        'source': 'स्रोत गांव', 'destination': 'गंतव्य', 'pass_type_label': 'पास का प्रकार',
        'photo_label': 'आपका फोटो', 'aadhar_label': 'आधार कार्ड', 'submit_btn': 'आवेदन जमा करें',
        'admin_panel': 'एडमिन पैनल', 'status_label': 'आवेदन की स्थिति', 'pending': 'अनुमोदन की प्रतीक्षा करें'
    },
    'mr': {
        'title': 'स्मार्टबस पास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'नोंदणी',
        'dashboard': 'डॅशबोर्ड', 'logout': 'लॉगआउट', 'apply_pass': 'नवीन अर्ज',
        'routes': 'बस मार्ग', 'profile': 'प्रोफाईल', 'pay_now': 'शुल्क भरा',
        'view_pass': 'पास पहा', 'download_pdf': 'डाउनलोड', 'renew': 'नूतनीकरण',
        'source': 'कुठून (गाव)', 'destination': 'कुठे (गंतव्य)', 'pass_type_label': 'पासचा प्रकार',
        'photo_label': 'तुमचा फोटो', 'aadhar_label': 'आधार कार्ड', 'submit_btn': 'अर्ज सादर करा',
        'admin_panel': 'एडमिन पॅनेल', 'status_label': 'अर्जाची स्थिती', 'pending': 'मान्यतेची प्रतीक्षा करा'
    }
}
VILLAGES = ["Kolhapur City", "Ichalkaranji", "Kagal", "Panhala", "Jaysingpur", "Gadhinglaj", "Shirol", "Hatkanangale"]

# --- INIT (With Auto-Admin Seeding) ---
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.create_all()
    # Create Default Admin so you don't have to keep re-registering
    if not User.query.filter_by(role='admin').first():
        admin = User(email='admin@buspass.com', password=generate_password_hash('admin123'), role='admin')
        db.session.add(admin)
        db.session.commit()
        print(">>> DEFAULT ADMIN CREATED: admin@buspass.com / admin123")

@app.context_processor
def inject_global_data():
    lang = session.get('lang', 'en')
    t_data = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    t_data.setdefault('admin_dashboard', t_data.get('admin_panel', 'Admin'))
    return dict(lang=lang, t=t_data, datetime=datetime, villages=VILLAGES)

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
        flash('Invalid login', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        if User.query.filter_by(email=email).first():
            flash('Email already used', 'warning')
            return redirect(url_for('register'))
        otp = str(random.randint(100000, 999999))
        session.update({'reg_email': email, 'reg_password': generate_password_hash(request.form['password']), 'reg_otp': otp})
        flash(f"YOUR OTP IS: {otp}", "info")
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
            flash('Success! Log in now.', 'success')
            return redirect(url_for('login'))
        flash('Invalid OTP', 'danger')
    return render_template('verify_otp.html')

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('student_dashboard.html', applications=user.applications, user=user)

@app.route('/student/apply', methods=['GET', 'POST'])
def apply_pass():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        p_file = request.files.get('profile_pic')
        a_file = request.files.get('aadhar_pic')
        p_name = secure_filename(p_file.filename) if p_file else "default.png"
        a_name = secure_filename(a_file.filename) if a_file else "default.png"
        if p_file: p_file.save(os.path.join(app.config['UPLOAD_FOLDER'], p_name))
        if a_file: a_file.save(os.path.join(app.config['UPLOAD_FOLDER'], a_name))

        new_app = PassApplication(
            user_id=session['user_id'], pass_type=request.form['pass_type'],
            source=request.form['source'], destination=request.form['destination'],
            profile_pic_filename=p_name, aadhar_pic_filename=a_name, fee=250
        )
        db.session.add(new_app)
        db.session.commit()
        return redirect(url_for('student_dashboard'))
    return render_template('apply_pass.html', villages=VILLAGES)

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    apps = PassApplication.query.all()
    stats = {
        'total_passes': len(apps), 
        'active_passes': len([a for a in apps if a.status == 'Approved']),
        'pending_count': len([a for a in apps if a.status == 'Pending']),
        'total_revenue': sum([a.fee for a in apps if a.status == 'Approved'])
    }
    return render_template('admin_dashboard.html', applications=apps, stats=stats)

@app.route('/profile')
@app.route('/student/profile')
def student_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('profile.html', user=User.query.get(session['user_id']))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/pay/<int:app_id>')
def pay_pass(app_id): return render_template('payment.html', app_id=app_id)

@app.route('/print/<int:app_id>')
def print_pass(app_id): return render_template('print_pass.html', app=PassApplication.query.get(app_id))

@app.route('/routes')
@app.route('/bus_routes')
def bus_routes(): 
    routes_list = [
        {"bus_no": "K-10", "path": "Kolhapur-Panhala", "frequency": "30m"},
        {"bus_no": "K-22", "path": "Kolhapur-Kagal", "frequency": "15m"}
    ]
    return render_template('routes.html', routes=routes_list)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
