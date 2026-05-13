import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode
from datetime import datetime, timedelta

from models import db, User, PassApplication
from translations import TRANSLATIONS, KOLHAPUR_VILLAGES

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_bus_pass'
# PostgreSQL for Render, SQLite for Local
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///buspass.db')
if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 # 50MB limit for uploads

db.init_app(app)

QR_DIR = os.path.join(app.root_path, 'static', 'qrcodes')
os.makedirs(QR_DIR, exist_ok=True)
UPLOAD_DIR = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def check_expirations():
    expired_apps = PassApplication.query.filter(
        PassApplication.status == 'Approved',
        PassApplication.validity_end < datetime.utcnow()
    ).all()
    for app in expired_apps:
        app.status = 'Expired'
    if expired_apps:
        db.session.commit()

with app.app_context():
    db.create_all()

@app.context_processor
def inject_translations():
    lang = session.get('lang', 'en')
    return dict(lang=lang, t=TRANSLATIONS.get(lang, TRANSLATIONS['en']), datetime=datetime)

@app.route('/set-language/<lang>')
def set_language(lang):
    if lang in TRANSLATIONS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        
        otp = str(random.randint(100000, 999999))
        session['reg_email'] = email
        session['reg_password'] = hashed_password
        session['reg_role'] = 'student'
        session['reg_otp'] = otp
        
        print(f"--- SIMULATED EMAIL SENT TO {email} | OTP: {otp} ---")
        flash(f'An OTP has been sent to your email. (SIMULATION CODE: {otp})', 'info')
        
        return redirect(url_for('verify_otp'))
        
    return render_template('register.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reg_email' not in session:
        return redirect(url_for('register'))
        
    if request.method == 'POST':
        entered_otp = request.form['otp']
        
        if entered_otp == session.get('reg_otp'):
            new_user = User(
                email=session['reg_email'], 
                password=session['reg_password'], 
                role=session['reg_role']
            )
            db.session.add(new_user)
            db.session.commit()
            
            session.pop('reg_email', None)
            session.pop('reg_password', None)
            session.pop('reg_role', None)
            session.pop('reg_otp', None)
            
            flash('Email verified and registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid OTP. Please try again.', 'danger')
            
    return render_template('verify_otp.html')

@app.route('/secret-admin-setup', methods=['GET', 'POST'])
def secret_admin_setup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Admin email already exists!', 'danger')
            return redirect(url_for('secret_admin_setup'))
            
        hashed_password = generate_password_hash(password)
        new_user = User(email=email, password=hashed_password, role='admin')
        db.session.add(new_user)
        db.session.commit()
        
        flash('Admin Account Created Successfully!', 'success')
        return redirect(url_for('login'))
        
    return render_template('register_admin.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['email'] = user.email
            session['role'] = user.role
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid email or password', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    check_expirations()
    
    user_id = session['user_id']
    applications = PassApplication.query.filter_by(user_id=user_id).order_by(PassApplication.created_at.desc()).all()
    user = User.query.get(user_id)
    
    # Notification check: Is any pass expiring within 3 days?
    expiring_soon = False
    for app in applications:
        if app.status == 'Approved' and app.validity_end:
            days_left = (app.validity_end - datetime.utcnow()).days
            if 0 <= days_left <= 3:
                expiring_soon = True
                break
                
    return render_template('student_dashboard.html', applications=applications, user=user, expiring_soon=expiring_soon)

@app.route('/student/profile', methods=['GET', 'POST'])
def student_profile():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        user.full_name = request.form.get('full_name')
        user.phone_number = request.form.get('phone_number')
        user.address = request.form.get('address')
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student_dashboard'))
        
    return render_template('profile.html', user=user)

@app.route('/student/apply', methods=['GET', 'POST'])
def apply_pass():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        pass_type = request.form['pass_type']
        source = request.form['source']
        destination = request.form['destination']
        
        if 'profile_pic' not in request.files or 'aadhar_pic' not in request.files:
            flash('Missing files', 'danger')
            return redirect(request.url)
            
        profile_file = request.files['profile_pic']
        aadhar_file = request.files['aadhar_pic']
        
        if profile_file.filename == '' or aadhar_file.filename == '':
            flash('Please select both photos', 'danger')
            return redirect(request.url)
            
        if profile_file and allowed_file(profile_file.filename) and aadhar_file and allowed_file(aadhar_file.filename):
            # Read binary data for Database Storage
            profile_data = profile_file.read()
            aadhar_data = aadhar_file.read()
            
            # Dynamic Fee Calculation based on route length
            base_fee = 100 + (len(source) + len(destination)) * 15
            if pass_type == 'Quarterly':
                base_fee = int(base_fee * 2.5)
            
            new_app = PassApplication(
                user_id=session['user_id'],
                pass_type=pass_type,
                source=source,
                destination=destination,
                profile_pic_data=profile_data,
                aadhar_pic_data=aadhar_data,
                fee=base_fee
            )
            db.session.add(new_app)
            db.session.commit()
            flash('Pass application submitted successfully!', 'success')
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid file type. Only JPG and PNG allowed.', 'danger')
            return redirect(request.url)
            
    return render_template('apply_pass.html', villages=KOLHAPUR_VILLAGES)

@app.route('/student/pay/<int:app_id>', methods=['GET', 'POST'])
def pay_pass(app_id):
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    application = PassApplication.query.get_or_404(app_id)
    
    if application.user_id != session['user_id'] or application.status != 'Pending Payment':
        flash('Invalid payment request.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    if request.method == 'POST':
        application.status = 'Approved'
        application.validity_start = datetime.utcnow()
        days = 30 if application.pass_type == 'Monthly' else 90
        application.validity_end = application.validity_start + timedelta(days=days)
        
        qr_data = f"PassID:{application.id}|Email:{application.student.email}|ValidTill:{application.validity_end.strftime('%Y-%m-%d')}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        
        qr_filename = f"qr_{application.id}.png"
        filepath = os.path.join(QR_DIR, qr_filename)
        img.save(filepath)
        
        application.qr_code_data = qr_filename
        db.session.commit()
        
        flash('Payment successful! Your Smart Pass is now active.', 'success')
        return redirect(url_for('student_dashboard'))
        
    return render_template('payment.html', application=application)

@app.route('/student/pass/<int:app_id>/print')
def print_pass(app_id):
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    application = PassApplication.query.get_or_404(app_id)
    if application.user_id != session['user_id'] or application.status != 'Approved':
        flash('Cannot print this pass.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    return render_template('print_pass.html', app=application)

@app.route('/student/renew/<int:app_id>')
def renew_pass(app_id):
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    application = PassApplication.query.get_or_404(app_id)
    if application.user_id != session['user_id']:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    # Reset status to Pending Payment for renewal
    application.status = 'Pending Payment'
    db.session.commit()
    flash('Renewal request initiated. Please complete the payment to extend your pass.', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/routes')
def bus_routes():
    # Simulated route data for Kolhapur
    routes = [
        {"bus_no": "K-101", "path": "Kolhapur City <-> Ichalkaranji", "frequency": "Every 15 mins"},
        {"bus_no": "K-102", "path": "Kolhapur City <-> Panhala", "frequency": "Every 30 mins"},
        {"bus_no": "K-201", "path": "Kagal <-> Gadhinglaj", "frequency": "Every 1 hour"},
        {"bus_no": "K-305", "path": "Hupari <-> Jaysingpur", "frequency": "Every 20 mins"},
        {"bus_no": "K-400", "path": "Karveer <-> Radhanagari", "frequency": "Twice a day"},
    ]
    return render_template('routes.html', routes=routes)

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    check_expirations()
    
    # Analytics
    total_passes = PassApplication.query.count()
    total_approved = PassApplication.query.filter_by(status='Approved').count()
    pending_count = PassApplication.query.filter_by(status='Pending').count()
    
