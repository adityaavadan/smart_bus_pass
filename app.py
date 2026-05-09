import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode
from datetime import datetime, timedelta

from models import db, User, PassApplication
from translations import TRANSLATIONS, KOLHAPUR_VILLAGES

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_bus_pass'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'buspass.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

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
    for app_item in expired_apps:
        app_item.status = 'Expired'
    if expired_apps:
        db.session.commit()

with app.app_context():
    db.create_all()
    # Auto-seed admin
    if not User.query.filter_by(email='admin@buspass.com').first():
        db.session.add(User(email='admin@buspass.com', password=generate_password_hash('admin123'), role='admin'))
        db.session.commit()

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
        session.update({'reg_email': email, 'reg_password': hashed_password, 'reg_role': 'student', 'reg_otp': otp})
        flash(f'An OTP has been sent (SIMULATION): {otp}', 'info')
        return redirect(url_for('verify_otp'))
    return render_template('register.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reg_email' not in session: return redirect(url_for('register'))
    if request.method == 'POST':
        if request.form['otp'] == session.get('reg_otp'):
            new_user = User(email=session['reg_email'], password=session['reg_password'], role=session['reg_role'])
            db.session.add(new_user); db.session.commit()
            session.clear()
            flash('Verified! Please login.', 'success')
            return redirect(url_for('login'))
        flash('Invalid OTP.', 'danger')
    return render_template('verify_otp.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session.update({'user_id': user.id, 'email': user.email, 'role': user.role})
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'student_dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session or session.get('role') != 'student': return redirect(url_for('login'))
    check_expirations()
    apps = PassApplication.query.filter_by(user_id=session['user_id']).order_by(PassApplication.created_at.desc()).all()
    user = User.query.get(session['user_id'])
    return render_template('student_dashboard.html', applications=apps, user=user)

@app.route('/student/profile', methods=['GET', 'POST'])
def student_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.full_name = request.form.get('full_name'); user.phone_number = request.form.get('phone_number'); user.address = request.form.get('address')
        db.session.commit()
        return redirect(url_for('student_dashboard'))
    return render_template('profile.html', user=user)

@app.route('/student/apply', methods=['GET', 'POST'])
def apply_pass():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        p_file = request.files['profile_pic']; a_file = request.files['aadhar_pic']
        if p_file and a_file:
            ts = int(datetime.utcnow().timestamp())
            p_name = secure_filename(f"u_{session['user_id']}_{ts}_{p_file.filename}")
            a_name = secure_filename(f"u_{session['user_id']}_{ts}_{a_file.filename}")
            p_file.save(os.path.join(UPLOAD_DIR, p_name)); a_file.save(os.path.join(UPLOAD_DIR, a_name))
            new_app = PassApplication(user_id=session['user_id'], pass_type=request.form['pass_type'], source=request.form['source'], destination=request.form['destination'], profile_pic_filename=p_name, aadhar_pic_filename=a_name, fee=150)
            db.session.add(new_app); db.session.commit()
            return redirect(url_for('student_dashboard'))
    return render_template('apply_pass.html', villages=KOLHAPUR_VILLAGES)

@app.route('/student/pay/<int:app_id>', methods=['GET', 'POST'])
def pay_pass(app_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    app_item = PassApplication.query.get_or_404(app_id)
    if request.method == 'POST':
        app_item.status = 'Approved'; app_item.validity_start = datetime.utcnow()
        app_item.validity_end = app_item.validity_start + timedelta(days=30)
        qr_name = f"qr_{app_item.id}.png"
        qrcode.make(f"ID:{app_item.id}").save(os.path.join(QR_DIR, qr_name))
        app_item.qr_code_data = qr_name; db.session.commit()
        return redirect(url_for('student_dashboard'))
    return render_template('payment.html', application=app_item)

@app.route('/student/pass/<int:app_id>/print')
def print_pass(app_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('print_pass.html', app=PassApplication.query.get_or_404(app_id))

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    apps = PassApplication.query.all()
    stats = {'total_passes': len(apps), 'active_passes': len([a for a in apps if a.status == 'Approved']), 'pending_count': len([a for a in apps if a.status == 'Pending']), 'total_revenue': sum(a.fee for a in apps if a.status == 'Approved')}
    return render_template('admin_dashboard.html', applications=apps, stats=stats)

@app.route('/admin/approve/<int:app_id>')
def approve_pass(app_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    PassApplication.query.get_or_404(app_id).status = 'Pending Payment'; db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject/<int:app_id>')
def reject_pass(app_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    PassApplication.query.get_or_404(app_id).status = 'Rejected'; db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/secret-admin-setup', methods=['GET', 'POST'])
def secret_admin_setup():
    if request.method == 'POST':
        db.session.add(User(email=request.form['email'], password=generate_password_hash(request.form['password']), role='admin'))
        db.session.commit(); return redirect(url_for('login'))
    return render_template('register_admin.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
