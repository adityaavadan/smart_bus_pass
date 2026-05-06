import os
import random
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

# Try-except block for imports to help debugging on Render
try:
    from models import db, User, PassApplication
    from translations import TRANSLATIONS, KOLHAPUR_VILLAGES
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    # Local import fallback
    from .models import db, User, PassApplication
    from .translations import TRANSLATIONS, KOLHAPUR_VILLAGES

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_bus_pass_789')

# Use a very stable database path
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'buspass.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

db.init_app(app)

# Ensure folders exist
with app.app_context():
    os.makedirs(os.path.join(app.root_path, 'static', 'qrcodes'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'static', 'uploads'), exist_ok=True)
    try:
        db.create_all()
    except Exception as e:
        print(f"DATABASE ERROR: {e}")

@app.context_processor
def inject_translations():
    lang = session.get('lang', 'en')
    t_data = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    return dict(lang=lang, t=t_data, datetime=datetime)

@app.route('/set-language/<lang>')
def set_language(lang):
    session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(request.form['password'])
        otp = str(random.randint(100000, 999999))
        session['reg_email'] = email
        session['reg_password'] = hashed_password
        session['reg_role'] = 'student'
        session['reg_otp'] = otp
        print(f"--- OTP SENT TO {email}: {otp} ---")
        flash(f'OTP sent (CODE: {otp})', 'info')
        return redirect(url_for('verify_otp'))
    return render_template('register.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reg_email' not in session: return redirect(url_for('register'))
    if request.method == 'POST':
        if request.form['otp'] == session.get('reg_otp'):
            new_user = User(email=session['reg_email'], password=session['reg_password'], role=session['reg_role'])
            db.session.add(new_user)
            db.session.commit()
            session.clear()
            flash('Success! Please login.', 'success')
            return redirect(url_for('login'))
        flash('Invalid OTP', 'danger')
    return render_template('verify_otp.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['email'] = user.email
            session['role'] = user.role
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'student_dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    apps = PassApplication.query.filter_by(user_id=session['user_id']).all()
    user = User.query.get(session['user_id'])
    return render_template('student_dashboard.html', applications=apps, user=user, expiring_soon=False)

@app.route('/student/apply', methods=['GET', 'POST'])
def apply_pass():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        source, dest = request.form['source'], request.form['destination']
        p_file, a_file = request.files['profile_pic'], request.files['aadhar_pic']
        if p_file and a_file:
            ts = int(datetime.utcnow().timestamp())
            p_name, a_name = secure_filename(f"p_{ts}_{p_file.filename}"), secure_filename(f"a_{ts}_{a_file.filename}")
            p_file.save(os.path.join(app.root_path, 'static', 'uploads', p_name))
            a_file.save(os.path.join(app.root_path, 'static', 'uploads', a_name))
            fee = 100 + (len(source) + len(dest)) * 15
            new_app = PassApplication(user_id=session['user_id'], pass_type=request.form['pass_type'], source=source, destination=dest, profile_pic_filename=p_name, aadhar_pic_filename=a_name, fee=fee)
            db.session.add(new_app)
            db.session.commit()
            return redirect(url_for('student_dashboard'))
    return render_template('apply_pass.html', villages=KOLHAPUR_VILLAGES)

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    apps = PassApplication.query.all()
    return render_template('admin_dashboard.html', applications=apps, stats={'total_passes': len(apps), 'active_passes': 0, 'pending_count': 0, 'total_revenue': 0})

@app.route('/secret-admin-setup', methods=['GET', 'POST'])
def secret_admin_setup():
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            db.session.add(User(email=request.form['email'], password=generate_password_hash(request.form['password']), role='admin'))
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register_admin.html')

@app.route('/routes')
def bus_routes():
    return render_template('routes.html', routes=[{"bus_no": "K-101", "path": "Kolhapur City", "frequency": "15m"}])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
