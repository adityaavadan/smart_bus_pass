import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

# --- CONFIG ---
app = Flask(__name__)
app.secret_key = 'smart_bus_pass_final_999'
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
    fee = db.Column(db.Integer, default=250)
    profile_pic_filename = db.Column(db.String(255))
    aadhar_pic_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- TRANSLATIONS ---
TRANSLATIONS = {
    'en': {'title': 'SmartPass', 'home': 'Home', 'login': 'Login', 'register': 'Register', 'dashboard': 'Dashboard', 'logout': 'Logout', 'profile': 'Profile', 'routes': 'Bus Routes'},
    'hi': {'title': 'स्मार्टपास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'पंजीकरण', 'dashboard': 'डैशबोर्ड', 'logout': 'लॉगआउट', 'profile': 'प्रोफ़ाइल', 'routes': 'बस मार्ग'},
    'mr': {'title': 'स्मार्टपास', 'home': 'होम', 'login': 'लॉगिन', 'register': 'नोंदणी', 'dashboard': 'डॅशबोर्ड', 'logout': 'लॉगआउट', 'profile': 'प्रोफाईल', 'routes': 'बस मार्ग'}
}

with app.app_context():
    os.makedirs(os.path.join(app.root_path, 'static', 'uploads'), exist_ok=True)
    db.create_all()

@app.context_processor
def inject_translations():
    lang = session.get('lang', 'en')
    t_data = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    t_data.setdefault('admin_dashboard', 'Admin')
    return dict(lang=lang, t=t_data, datetime=datetime)

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
        if not User.query.filter_by(email=request.form['email']).first():
            db.session.add(User(email=request.form['email'], password=generate_password_hash(request.form['password'])))
            db.session.commit()
            flash('Registered! Please login.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/verify-otp')
def verify_otp():
    return render_template('verify_otp.html')

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    apps = PassApplication.query.filter_by(user_id=session['user_id']).all()
    return render_template('student_dashboard.html', applications=apps, user=User.query.get(session['user_id']), expiring_soon=False)

@app.route('/student/apply', methods=['GET', 'POST'])
def apply_pass():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        new_app = PassApplication(user_id=session['user_id'], pass_type=request.form.get('pass_type'),
                                  source=request.form.get('source'), destination=request.form.get('destination'))
        db.session.add(new_app)
        db.session.commit()
        return redirect(url_for('student_dashboard'))
    return render_template('apply_pass.html', villages=["Kolhapur", "Kagal", "Panhala"])

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('admin_dashboard.html', applications=PassApplication.query.all(), stats={})

@app.route('/routes')
def bus_routes():
    return render_template('routes.html', routes=[])

@app.route('/profile')
@app.route('/student/profile')
def student_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('profile.html', user=User.query.get(session['user_id']))

@app.route('/payment/<int:app_id>')
def payment(app_id):
    return render_template('payment.html', app_id=app_id)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/secret-admin-setup', methods=['GET', 'POST'])
def secret_admin_setup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if not User.query.filter_by(email=email).first():
            db.session.add(User(email=email, password=generate_password_hash(password), role='admin'))
            db.session.commit()
            flash('Admin account created!', 'success')
            return redirect(url_for('login'))
    return render_template('register_admin.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
