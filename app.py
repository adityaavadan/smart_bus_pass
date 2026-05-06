import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

# --- APP CONFIG ---
app = Flask(__name__)
app.secret_key = 'smart_bus_pass_secure_key_123'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'buspass.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='student')

class PassApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pass_type = db.Column(db.String(50))
    source = db.Column(db.String(100))
    destination = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Pending')
    fee = db.Column(db.Integer, default=0)
    profile_pic_filename = db.Column(db.String(255))
    aadhar_pic_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- TRANSLATIONS & DATA ---
TRANSLATIONS = {
    'en': {'title': 'Smart Bus Pass', 'home': 'Home', 'login': 'Login', 'register': 'Register', 'dashboard': 'Dashboard', 'logout': 'Logout', 'apply_pass': 'Apply Pass', 'routes': 'Bus Routes', 'profile': 'Profile', 'renewal': 'Renew Pass'},
    'hi': {'title': 'स्मार्ट बस पास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'पंजीकरण', 'dashboard': 'डैशबोर्ड', 'logout': 'लॉगआउट', 'apply_pass': 'पास आवेदन', 'routes': 'बस मार्ग', 'profile': 'प्रोफ़ाइल', 'renewal': 'नवीनीकरण'},
    'mr': {'title': 'स्मार्ट बस पास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'नोंदणी', 'dashboard': 'डॅशबोर्ड', 'logout': 'लॉगआउट', 'apply_pass': 'अर्ज करा', 'routes': 'बस मार्ग', 'profile': 'प्रोफाईल', 'renewal': 'नूतनीकरण'}
}
KOLHAPUR_VILLAGES = ["Kolhapur City", "Ichalkaranji", "Kagal", "Panhala", "Jaysingpur", "Gadhinglaj", "Shirol", "Hatkanangale"]

# --- INIT ---
with app.app_context():
    os.makedirs(os.path.join(app.root_path, 'static', 'uploads'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'static', 'qrcodes'), exist_ok=True)
    db.create_all()

@app.context_processor
def inject_translations():
    lang = session.get('lang', 'en')
    return dict(lang=lang, t=TRANSLATIONS.get(lang, TRANSLATIONS['en']), datetime=datetime)

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
            session['user_id'] = user.id
            session['role'] = user.role
            session['email'] = user.email
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
        hashed_pw = generate_password_hash(request.form['password'])
        otp = str(random.randint(100000, 999999))
        session.update({'reg_email': email, 'reg_password': hashed_pw, 'reg_otp': otp})
        print(f"--- OTP for {email}: {otp} ---")
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
            flash('Success! Please login.', 'success')
            return redirect(url_for('login'))
        flash('Invalid OTP', 'danger')
    return render_template('verify_otp.html')

@app.route('/student/dashboard')
def student_dashboard():
    if not session.get('user_id'): return redirect(url_for('login'))
    apps = PassApplication.query.filter_by(user_id=session['user_id']).all()
    return render_template('student_dashboard.html', applications=apps, user=User.query.get(session['user_id']), expiring_soon=False)

@app.route('/student/apply', methods=['GET', 'POST'])
def apply_pass():
    if not session.get('user_id'): return redirect(url_for('login'))
    if request.method == 'POST':
        p_file = request.files.get('profile_pic')
        a_file = request.files.get('aadhar_pic')
        if p_file and a_file:
            p_name = secure_filename(f"p_{p_file.filename}")
            a_name = secure_filename(f"a_{a_file.filename}")
            p_file.save(os.path.join(app.root_path, 'static', 'uploads', p_name))
            a_file.save(os.path.join(app.root_path, 'static', 'uploads', a_name))
            new_app = PassApplication(user_id=session['user_id'], pass_type=request.form['pass_type'], 
                                      source=request.form['source'], destination=request.form['destination'],
                                      profile_pic_filename=p_name, aadhar_pic_filename=a_name, fee=250)
            db.session.add(new_app)
            db.session.commit()
            return redirect(url_for('student_dashboard'))
    return render_template('apply_pass.html', villages=KOLHAPUR_VILLAGES)

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('admin_dashboard.html', applications=PassApplication.query.all(), stats={'total_passes': 0, 'active_passes': 0, 'pending_count': 0, 'total_revenue': 0})

@app.route('/routes')
def bus_routes():
    return render_template('routes.html', routes=[{"bus_no": "K-10", "path": "Kolhapur-Panhala", "frequency": "30m"}])

@app.route('/profile')
def profile():
    if not session.get('user_id'): return redirect(url_for('login'))
    return render_template('profile.html', user=User.query.get(session['user_id']))

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
