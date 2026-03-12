# EduConnect v1.0.1 - Vercel Optimized
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models.recommendation_model import recommend_groups, recommend_partners
from flask_mail import Mail, Message as MailMessage
from itsdangerous import URLSafeTimedSerializer
import requests as http_requests
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.objectid import ObjectId
import certifi

# Load Environment Variables from .env file
load_dotenv()

app = Flask(__name__, instance_path='/tmp')
# Ensure secret key works locally and safely in production
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'educonnect_secret_key_123')

# MongoDB Configuration
MONGO_URI = os.environ.get('MONGO_URI')

if not MONGO_URI:
    # Local fallback for development
    MONGO_URI = 'mongodb://localhost:27017/educonnect'
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client.educonnect
else:
    # Production with SSL certificates
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
    try:
        db = client.get_default_database()
    except:
        db = client.educonnect
    if db is None:
        db = client.educonnect

# Handle Read-Only Filesystem on Vercel
is_vercel = os.environ.get('VERCEL') == '1'
if is_vercel:
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
else:
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Configuration for Flask-Mail
# ... (rest of the mail config)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'mock.educonnect@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'dummy_password')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'mock.educonnect@gmail.com')
mail = Mail(app)

serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Ensure upload directory exists - Wrapped in try-except for Vercel stability
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except Exception as e:
    print(f"Directory creation warning: {e}")

# ----------------- HELPER CLASSES (To keep code clean) -----------------
class MongoObject:
    def __init__(self, data):
        if data:
            for key, value in data.items():
                setattr(self, key, value)
            self.id = str(data.get('_id'))

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
        try:
            user_data = db.users.find_one({'_id': ObjectId(session['user_id'])})
            if user_data:
                return dict(current_user=MongoObject(user_data))
        except Exception as e:
            print(f"Database Error in inject_user: {e}")
    return dict(current_user=None)

@app.route('/health')
def health():
    return "EduConnect is healthy! DB status: UP" if db is not None else "EduConnect is healthy! DB status: PENDING"


# ----------------- MODULE 1: HOME PAGE -----------------

@app.route('/')
def index():
    try:
        total_users = db.users.count_documents({})
        active_users = db.users.count_documents({'is_active': True})
        inactive_users = total_users - active_users
        total_groups = db.groups.count_documents({})
    except Exception as e:
        print(f"Database connection error: {e}")
        return render_template('500.html', error_message="Database is currently unavailable. Please check your MONGO_URI configuration."), 500
    
    our_features = [
        {"icon": "🎯", "color": "indigo", "title": "Smart Matching", "desc": "Our ML engine finds the perfect study partners and groups based on your subject, skill level, and schedule."},
        {"icon": "💬", "color": "teal", "title": "Real-Time Collaboration", "desc": "Virtual discussion rooms allow students to share ideas, chat in real time, and learn together effectively."},
        {"icon": "🧠", "color": "emerald", "title": "AI-Powered Recommendations", "desc": "Our AI system recommends groups and resources tailored to your interests and abilities."},
        {"icon": "📁", "color": "blue", "title": "Resource Sharing", "desc": "Easily upload and access shared study materials. Build a comprehensive knowledge base together with your group."}
    ]
    
    return render_template('index.html',
                           total_users=total_users,
                           active_users=active_users,
                           inactive_users=inactive_users,
                           total_groups=total_groups,
                           our_features=our_features)

@app.route('/api/stats')
def api_stats():
    total_users = db.users.count_documents({})
    active_users = db.users.count_documents({'is_active': True})
    inactive_users = total_users - active_users
    total_groups = db.groups.count_documents({})
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

        existing_user = db.users.find_one({'email': email})
        if existing_user:
            flash('Email already registered! Please log in.', 'danger')
            return redirect(url_for('login'))

        hashed_pw = generate_password_hash(password)
        new_user = {
            'name': name,
            'email': email,
            'password_hash': hashed_pw,
            'subjects': subjects,
            'skill_level': skill_level,
            'availability': availability,
            'learning_goals': "",
            'is_active': True,
            'is_verified': True, # Auto-verify for easier setup
            'last_login': None
        }
        user_id = db.users.insert_one(new_user).inserted_id
        
        token = serializer.dumps(email, salt='email-confirm-salt')
        confirm_url = url_for('confirm_email', token=token, _external=True)
        
        try:
            msg = MailMessage("Confirm your EduConnect Email", recipients=[email])
            msg.body = f"Welcome {name}! Please click the link to verify your email endpoint:\n\n{confirm_url}"
            
            if app.config['MAIL_USERNAME'] == 'mock.educonnect@gmail.com' and not is_vercel:
                try:
                    with open(os.path.join(app.root_path, 'latest_email.txt'), 'w') as f:
                        f.write(msg.body)
                except:
                    pass
                flash('Registration successful! Please check your email to verify your account.', 'success')
            else:
                try:
                    mail.send(msg)
                except:
                    pass
                flash('Registration successful! Please check your email to verify your account.', 'success')
        except Exception as e:
            flash('Registration successful! (Email verify in offline safe-mode. You can login)', 'warning')
            db.users.update_one({'_id': user_id}, {'$set': {'is_verified': True}})

        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = db.users.find_one({'email': email})
        if user and check_password_hash(user['password_hash'], password):
            if not user.get('is_verified', True):
                flash('Please check your email and verify your account before logging in.', 'warning')
                return redirect(url_for('login'))
                
            session['user_id'] = str(user['_id'])
            db.users.update_one({'_id': user['_id']}, {'$set': {'last_login': datetime.utcnow(), 'is_active': True}})
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
        
    user = db.users.find_one({'email': email})
    if not user:
        return "User not found", 404
        
    if user.get('is_verified', False):
        flash('Account already verified securely. Please login.', 'info')
    else:
        db.users.update_one({'_id': user['_id']}, {'$set': {'is_verified': True}})
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
    user_data = db.users.find_one({'_id': ObjectId(session['user_id'])})
    if request.method == 'POST':
        updated_data = {
            'subjects': request.form.get('subjects'),
            'skill_level': request.form.get('skill_level'),
            'availability': request.form.get('availability'),
            'learning_goals': request.form.get('learning_goals')
        }
        db.users.update_one({'_id': ObjectId(session['user_id'])}, {'$set': updated_data})
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
        
    return render_template('profile.html', user=MongoObject(user_data))


# ----------------- MODULE 4: DASHBOARD -----------------

@app.route('/dashboard')
@login_required
def dashboard():
    user_data = db.users.find_one({'_id': ObjectId(session['user_id'])})
    user = MongoObject(user_data)
    
    # Joined groups
    memberships = list(db.group_members.find({'user_id': ObjectId(session['user_id'])}))
    group_ids = [m['group_id'] for m in memberships]
    joined_groups_data = list(db.groups.find({'_id': {'$in': group_ids}}))
    joined_groups = [MongoObject(g) for g in joined_groups_data]
    
    # Upcoming sessions
    upcoming_sessions_data = list(db.study_sessions.find({'group_id': {'$in': group_ids}}))
    upcoming_sessions = [MongoObject(s) for s in upcoming_sessions_data]
    
    # Smart Recommendations
    all_groups_data = list(db.groups.find({}))
    all_groups = [MongoObject(g) for g in all_groups_data]
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
    all_groups_data = list(db.groups.find({}))
    all_groups = [MongoObject(g) for g in all_groups_data]
    
    memberships = list(db.group_members.find({'user_id': ObjectId(session['user_id'])}))
    joined_group_ids = [str(m['group_id']) for m in memberships]
    
    return render_template('groups.html', groups=all_groups, joined_group_ids=joined_group_ids)

@app.route('/groups/create', methods=['GET', 'POST'])
@login_required
def create_group():
    if request.method == 'POST':
        new_group = {
            'name': request.form.get('name'),
            'subject': request.form.get('subject'),
            'description': request.form.get('description'),
            'meeting_time': request.form.get('meeting_time'),
            'creator_id': ObjectId(session['user_id'])
        }
        group_id = db.groups.insert_one(new_group).inserted_id
        
        # Add creator as a member automatically
        db.group_members.insert_one({
            'group_id': group_id,
            'user_id': ObjectId(session['user_id']),
            'joined_at': datetime.utcnow()
        })
        
        flash('Study group created successfully!', 'success')
        return redirect(url_for('group_detail', group_id=str(group_id)))
        
    return render_template('create_group.html')

@app.route('/groups/<group_id>')
@login_required
def group_detail(group_id):
    gid = ObjectId(group_id)
    group_data = db.groups.find_one({'_id': gid})
    if not group_data:
        return "Group not found", 404
        
    # Get creator name
    creator = db.users.find_one({'_id': group_data['creator_id']})
    group_data['creator'] = MongoObject(creator) if creator else None
    group = MongoObject(group_data)
    
    user_id = ObjectId(session['user_id'])
    is_member = db.group_members.find_one({'group_id': gid, 'user_id': user_id}) is not None
    
    messages_data = list(db.messages.find({'group_id': gid}).sort('timestamp', 1))
    for m in messages_data:
        sender = db.users.find_one({'_id': m['user_id']})
        m['sender'] = MongoObject(sender) if sender else None
    messages = [MongoObject(m) for m in messages_data]
    
    resources_data = list(db.resources.find({'group_id': gid}).sort('upload_time', -1))
    resources = [MongoObject(r) for r in resources_data]
    
    sessions_data = list(db.study_sessions.find({'group_id': gid}).sort('date', 1))
    sessions = [MongoObject(s) for s in sessions_data]
    
    # Recommend partners
    user_data = db.users.find_one({'_id': user_id})
    all_users_data = list(db.users.find({}))
    recommended_partners = recommend_partners(MongoObject(user_data), [MongoObject(u) for u in all_users_data])
    
    return render_template('group_detail.html', 
                           group=group, 
                           is_member=is_member,
                           messages=messages,
                           resources=resources,
                           sessions=sessions,
                           recommended_partners=recommended_partners)

@app.route('/groups/<group_id>/join')
@login_required
def join_group(group_id):
    gid = ObjectId(group_id)
    user_id = ObjectId(session['user_id'])
    
    existing = db.group_members.find_one({'group_id': gid, 'user_id': user_id})
    if not existing:
        db.group_members.insert_one({
            'group_id': gid,
            'user_id': user_id,
            'joined_at': datetime.utcnow()
        })
        flash('You have successfully joined the group!', 'success')
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/groups/<group_id>/leave')
@login_required
def leave_group(group_id):
    gid = ObjectId(group_id)
    user_id = ObjectId(session['user_id'])
    
    db.group_members.delete_one({'group_id': gid, 'user_id': user_id})
    flash('You have left the group.', 'info')
    return redirect(url_for('dashboard'))


# ----------------- MODULE 7: REAL TIME DISCUSSION -----------------

@app.route('/groups/<group_id>/message', methods=['POST'])
@login_required
def send_message(group_id):
    content = request.form.get('content')
    if content:
        db.messages.insert_one({
            'content': content,
            'group_id': ObjectId(group_id),
            'user_id': ObjectId(session['user_id']),
            'timestamp': datetime.utcnow()
        })
    return redirect(url_for('group_detail', group_id=group_id))


# ----------------- MODULE 8: RESOURCE SHARING -----------------

@app.route('/groups/<group_id>/upload', methods=['POST'])
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
        safe_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        file.save(file_path)
        
        db.resources.insert_one({
            'file_name': filename,
            'file_path': safe_filename,
            'group_id': ObjectId(group_id),
            'uploader_id': ObjectId(session['user_id']),
            'upload_time': datetime.utcnow()
        })
        flash('Resource uploaded successfully!', 'success')
        
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/download/<resource_id>')
@login_required
def download_resource(resource_id):
    import mimetypes
    from flask import send_from_directory
    resource = db.resources.find_one({'_id': ObjectId(resource_id)})
    if not resource:
        return "File not found", 404
        
    mime_type, _ = mimetypes.guess_type(resource['file_name'])
    if mime_type is None:
        mime_type = 'application/octet-stream'
    
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        resource['file_path'],
        as_attachment=True,
        download_name=resource['file_name'],
        mimetype=mime_type
    )

@app.route('/delete/<resource_id>')
@login_required
def delete_resource(resource_id):
    resource = db.resources.find_one({'_id': ObjectId(resource_id)})
    if not resource:
        flash('Resource not found.', 'danger')
        return redirect(url_for('dashboard'))
        
    group = db.groups.find_one({'_id': resource['group_id']})
    user_id = ObjectId(session['user_id'])

    if resource['uploader_id'] != user_id and group['creator_id'] != user_id:
        flash('You do not have permission to delete this file.', 'danger')
        return redirect(url_for('group_detail', group_id=str(resource['group_id'])))

    file_full_path = os.path.join(app.config['UPLOAD_FOLDER'], resource['file_path'])
    if os.path.exists(file_full_path):
        os.remove(file_full_path)

    db.resources.delete_one({'_id': resource['_id']})
    flash('Resource deleted successfully.', 'success')
    return redirect(url_for('group_detail', group_id=str(resource['group_id'])))

# ----------------- MODULE 9: STUDY SESSION SCHEDULING -----------------

@app.route('/groups/<group_id>/session', methods=['POST'])
@login_required
def schedule_session(group_id):
    topic = request.form.get('topic')
    date = request.form.get('date')
    time = request.form.get('time')
    
    if topic and date and time:
        db.study_sessions.insert_one({
            'topic': topic,
            'date': date,
            'time': time,
            'group_id': ObjectId(group_id),
            'organizer_id': ObjectId(session['user_id'])
        })
        flash('Study session scheduled!', 'success')
        
    return redirect(url_for('group_detail', group_id=group_id))

# ----------------- CUSTOM ERROR HANDLERS -----------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    # MongoDB doesn't require session rollback in the same way as SQL
    return render_template('500.html'), 500

# ----------------- SETUP AND RUN -----------------

if __name__ == '__main__':
    app.run(debug=True, port=80)
