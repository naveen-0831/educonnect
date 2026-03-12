import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models.recommendation_model import recommend_groups, recommend_partners
from flask_mail import Mail, Message as MailMessage
from itsdangerous import URLSafeTimedSerializer
# AI imports removed
import requests as http_requests
from dotenv import load_dotenv

# Load Environment Variables from .env file
load_dotenv()

app = Flask(__name__)
# Ensure secret key works locally and safely in production
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'educonnect_secret_key_123')

# Check for production DATABASE URI, fallback to SQLite locally
db_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
# Add a maximum file upload limit (16 Megabytes) to prevent crashing the server
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Configuration for Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'mock.educonnect@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'dummy_password')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'mock.educonnect@gmail.com')
mail = Mail(app)

serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

db = SQLAlchemy(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ----------------- MODULE 10: DATABASE TABLES -----------------

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    subjects = db.Column(db.String(255)) # Comma-separated subjects
    skill_level = db.Column(db.String(50)) # Beginner, Intermediate, Advanced
    availability = db.Column(db.String(100)) # e.g., "Weekends", "Evenings", "Anytime"
    learning_goals = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)  # Whether the user account is active
    is_verified = db.Column(db.Boolean, default=False) # Email verification flag
    last_login = db.Column(db.DateTime)  # Track last login time

    # Relationships
    groups_created = db.relationship('Group', backref='creator', lazy=True)
    group_memberships = db.relationship('GroupMember', backref='user', lazy=True)
    resources_uploaded = db.relationship('Resource', backref='uploader', lazy=True)
    messages = db.relationship('Message', backref='sender', lazy=True)

class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    meeting_time = db.Column(db.String(100))
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    members = db.relationship('GroupMember', backref='group', lazy=True, cascade='all, delete-orphan')
    resources = db.relationship('Resource', backref='group', lazy=True, cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='group', lazy=True, cascade='all, delete-orphan')
    sessions = db.relationship('StudySession', backref='group', lazy=True, cascade='all, delete-orphan')

class GroupMember(db.Model):
    __tablename__ = 'group_members'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

class Resource(db.Model):
    __tablename__ = 'resources'
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

class StudySession(db.Model):
    __tablename__ = 'study_sessions'
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(150), nullable=False)
    date = db.Column(db.String(50), nullable=False) # e.g., YYYY-MM-DD
    time = db.Column(db.String(50), nullable=False) # e.g., HH:MM
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


# ----------------- MIDDLEWARE -----------------

def login_required(func):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@app.context_processor
def inject_user():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        return dict(current_user=user)
    return dict(current_user=None)


# ----------------- MODULE 1: HOME PAGE -----------------

@app.route('/')
def index():
    # Gather stats for the landing page
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    inactive_users = total_users - active_users
    total_groups = Group.query.count()
    
    # Backend data for features
    our_features = [
        {
            "icon": "🎯",
            "color": "indigo",
            "title": "Smart Matching",
            "desc": "Our ML engine finds the perfect study partners and groups based on your subject, skill level, and schedule."
        },
        {
            "icon": "💬",
            "color": "teal",
            "title": "Real-Time Collaboration",
            "desc": "Virtual discussion rooms allow students to share ideas, chat in real time, and learn together effectively."
        },
        {
            "icon": "🧠",
            "color": "emerald",
            "title": "AI-Powered Recommendations",
            "desc": "Our AI system recommends groups and resources tailored to your interests and abilities."
        },
        {
            "icon": "📁",
            "color": "blue",
            "title": "Resource Sharing",
            "desc": "Easily upload and access shared study materials. Build a comprehensive knowledge base together with your group."
        }
    ]
    
    return render_template('index.html',
                           total_users=total_users,
                           active_users=active_users,
                           inactive_users=inactive_users,
                           total_groups=total_groups,
                           our_features=our_features)

@app.route('/api/stats')
def api_stats():
    """API endpoint returning user statistics as JSON."""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    inactive_users = total_users - active_users
    total_groups = Group.query.count()
    return jsonify({
        'total_registered': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'total_groups': total_groups
    })


# ----------------- MODULE 2: USER AUTHENTICATION -----------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        subjects = request.form.get('subjects')
        skill_level = request.form.get('skill_level')
        availability = request.form.get('availability')

        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered! Please log in.', 'danger')
            return redirect(url_for('login'))

        # Create new user
        hashed_pw = generate_password_hash(password)
        new_user = User(
            name=name,
            email=email,
            password_hash=hashed_pw,
            subjects=subjects,
            skill_level=skill_level,
            availability=availability,
            learning_goals="",
            is_verified=False
        )
        db.session.add(new_user)
        db.session.commit()
        
        # --- Email Verification logic ---
        token = serializer.dumps(email, salt='email-confirm-salt')
        confirm_url = url_for('confirm_email', token=token, _external=True)
        
        try:
            msg = MailMessage("Confirm your EduConnect Email", recipients=[email])
            msg.body = f"Welcome {name}! Please click the link to verify your email endpoint:\n\n{confirm_url}"
            
            # Simulated Email for Local Testing
            if app.config['MAIL_USERNAME'] == 'mock.educonnect@gmail.com':
                with open(os.path.join(app.root_path, 'latest_email.txt'), 'w') as f:
                    f.write(msg.body)
                flash('Registration successful! Please check your email to verify your account.', 'success')
            else:
                mail.send(msg)
                flash('Registration successful! Please check your email to verify your account.', 'success')
        except Exception as e:
            print(f"Failed to send email securely: {e}")
            flash('Registration successful! (Email verify in offline safe-mode. You can login)', 'warning')
            user_manual = User.query.filter_by(email=email).first()
            user_manual.is_verified = True
            db.session.commit()

        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            if not getattr(user, 'is_verified', True):
                flash('Please check your email and verify your account securely before logging in.', 'warning')
                return redirect(url_for('login'))
                
            session['user_id'] = user.id
            # Track last login time and mark user as active
            user.last_login = datetime.utcnow()
            user.is_active = True
            db.session.commit()
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            
    return render_template('login.html')

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = serializer.loads(token, salt='email-confirm-salt', max_age=3600)
    except Exception:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('login'))
        
    user = User.query.filter_by(email=email).first_or_404()
    if getattr(user, 'is_verified', False):
        flash('Account already verified securely. Please login.', 'info')
    else:
        user.is_verified = True
        db.session.commit()
        flash('You have successfully verified your email securely. Welcome!', 'success')
        
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ----------------- MODULE 3: USER PROFILE -----------------

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.subjects = request.form.get('subjects')
        user.skill_level = request.form.get('skill_level')
        user.availability = request.form.get('availability')
        user.learning_goals = request.form.get('learning_goals')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
        
    return render_template('profile.html', user=user)


# ----------------- MODULE 4: DASHBOARD -----------------

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    
    # Joined groups
    memberships = GroupMember.query.filter_by(user_id=user.id).all()
    joined_groups = [m.group for m in memberships]
    
    # Extract group IDs for filtering upcoming sessions
    group_ids = [g.id for g in joined_groups]
    
    # Upcoming sessions
    upcoming_sessions = StudySession.query.filter(StudySession.group_id.in_(group_ids) if group_ids else False).all()
    
    # Smart Recommendations (Module 6 integration)
    all_groups = Group.query.all()
    # pass all groups and user into ML model directly formatted
    recommended_groups = recommend_groups(user, all_groups)
    
    return render_template('dashboard.html', 
                           user=user, 
                           joined_groups=joined_groups, 
                           upcoming_sessions=upcoming_sessions,
                           recommended_groups=recommended_groups)


# ----------------- MODULE 5: STUDY GROUP MANAGEMENT -----------------

@app.route('/groups')
@login_required
def groups():
    all_groups = Group.query.all()
    user = User.query.get(session['user_id'])
    memberships = GroupMember.query.filter_by(user_id=user.id).all()
    joined_group_ids = [m.group_id for m in memberships]
    
    return render_template('groups.html', groups=all_groups, joined_group_ids=joined_group_ids)

@app.route('/groups/create', methods=['GET', 'POST'])
@login_required
def create_group():
    if request.method == 'POST':
        name = request.form.get('name')
        subject = request.form.get('subject')
        description = request.form.get('description')
        meeting_time = request.form.get('meeting_time')
        
        new_group = Group(
            name=name,
            subject=subject,
            description=description,
            meeting_time=meeting_time,
            creator_id=session['user_id']
        )
        db.session.add(new_group)
        db.session.commit()
        
        # Add creator as a member automatically
        member = GroupMember(group_id=new_group.id, user_id=session['user_id'])
        db.session.add(member)
        db.session.commit()
        
        flash('Study group created successfully!', 'success')
        return redirect(url_for('group_detail', group_id=new_group.id))
        
    return render_template('create_group.html')

@app.route('/groups/<int:group_id>')
@login_required
def group_detail(group_id):
    group = Group.query.get_or_404(group_id)
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    is_member = GroupMember.query.filter_by(group_id=group.id, user_id=user_id).first() is not None
    
    messages = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.asc()).all()
    resources = Resource.query.filter_by(group_id=group.id).order_by(Resource.upload_time.desc()).all()
    sessions = StudySession.query.filter_by(group_id=group.id).order_by(StudySession.date.asc()).all()
    
    # Recommend study partners with similar interests
    all_users = User.query.all()
    recommended_partners = recommend_partners(user, all_users)
    
    return render_template('group_detail.html', 
                           group=group, 
                           is_member=is_member,
                           messages=messages,
                           resources=resources,
                           sessions=sessions,
                           recommended_partners=recommended_partners)

@app.route('/groups/<int:group_id>/join')
@login_required
def join_group(group_id):
    group = Group.query.get_or_404(group_id)
    user_id = session['user_id']
    
    existing = GroupMember.query.filter_by(group_id=group.id, user_id=user_id).first()
    if not existing:
        new_member = GroupMember(group_id=group.id, user_id=user_id)
        db.session.add(new_member)
        db.session.commit()
        flash('You have successfully joined the group!', 'success')
    return redirect(url_for('group_detail', group_id=group.id))

@app.route('/groups/<int:group_id>/leave')
@login_required
def leave_group(group_id):
    group = Group.query.get_or_404(group_id)
    user_id = session['user_id']
    
    membership = GroupMember.query.filter_by(group_id=group.id, user_id=user_id).first()
    if membership:
        db.session.delete(membership)
        db.session.commit()
        flash('You have left the group.', 'info')
    return redirect(url_for('dashboard'))


# ----------------- MODULE 7: REAL TIME DISCUSSION -----------------

@app.route('/groups/<int:group_id>/message', methods=['POST'])
@login_required
def send_message(group_id):
    content = request.form.get('content')
    if content:
        msg = Message(content=content, group_id=group_id, user_id=session['user_id'])
        db.session.add(msg)
        db.session.commit()
    return redirect(url_for('group_detail', group_id=group_id))


# ----------------- MODULE 8: RESOURCE SHARING -----------------

@app.route('/groups/<int:group_id>/upload', methods=['POST'])
@login_required
def upload_resource(group_id):
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
        
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
        
    if file:
        filename = secure_filename(file.filename)
        # Prevent duplicate filenames inside the uploads folder by appending timestamp
        safe_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        file.save(file_path)
        
        resource = Resource(
            file_name=filename,
            file_path=safe_filename,
            group_id=group_id,
            uploader_id=session['user_id']
        )
        db.session.add(resource)
        db.session.commit()
        flash('Resource uploaded successfully!', 'success')
        
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/download/<int:resource_id>')
@login_required
def download_resource(resource_id):
    import mimetypes
    from flask import send_from_directory
    resource = Resource.query.get_or_404(resource_id)
    
    # Detect the correct MIME type from the original file name
    mime_type, _ = mimetypes.guess_type(resource.file_name)
    if mime_type is None:
        mime_type = 'application/octet-stream'  # Safe fallback for unknown types
    
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        resource.file_path,
        as_attachment=True,
        download_name=resource.file_name,
        mimetype=mime_type
    )

@app.route('/delete/<int:resource_id>')
@login_required
def delete_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    group = Group.query.get_or_404(resource.group_id)
    user_id = session['user_id']

    # Only the uploader or the group creator can delete a resource
    if resource.uploader_id != user_id and group.creator_id != user_id:
        flash('You do not have permission to delete this file.', 'danger')
        return redirect(url_for('group_detail', group_id=resource.group_id))

    # Delete the physical file from the uploads folder
    file_full_path = os.path.join(app.config['UPLOAD_FOLDER'], resource.file_path)
    if os.path.exists(file_full_path):
        os.remove(file_full_path)

    # Delete the database record
    db.session.delete(resource)
    db.session.commit()
    flash('Resource deleted successfully.', 'success')
    return redirect(url_for('group_detail', group_id=group.id))
# ----------------- MODULE 9: STUDY SESSION SCHEDULING -----------------

@app.route('/groups/<int:group_id>/session', methods=['POST'])
@login_required
def schedule_session(group_id):
    topic = request.form.get('topic')
    date = request.form.get('date')
    time = request.form.get('time')
    
    if topic and date and time:
        session_obj = StudySession(
            topic=topic,
            date=date,
            time=time,
            group_id=group_id,
            organizer_id=session['user_id']
        )
        db.session.add(session_obj)
        db.session.commit()
        flash('Study session scheduled!', 'success')
        
    return redirect(url_for('group_detail', group_id=group_id))





# ----------------- CUSTOM ERROR HANDLERS -----------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    db.session.rollback()  # Rollback session in case of DB error
    return render_template('500.html'), 500

# ----------------- SETUP AND RUN -----------------

# Ensure database tables are created before the app starts
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, port=80)
