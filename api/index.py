# EduConnect v1.0.2 - Monolithic Vercel Optimization
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message as MailMessage
from itsdangerous import URLSafeTimedSerializer
import requests as http_requests
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.objectid import ObjectId
import certifi
import urllib.parse

# Load Environment Variables
load_dotenv()

# Monolithic Recommendations (Inline to avoid import issues on Vercel)
def recommend_groups(user, all_groups, top_k=5):
    if not all_groups: return []
    user_interests = set((user.subjects or "").lower().replace(',', ' ').split())
    scored_groups = []
    for group in all_groups:
        group_text = f"{group.name} {group.subject} {group.description}".lower()
        score = sum(1 for word in user_interests if word in group_text)
        if user.subjects and group.subject and group.subject.lower() in user.subjects.lower():
            score += 2
        scored_groups.append((score, group))
    scored_groups.sort(key=lambda x: x[0], reverse=True)
    return [g[1] for g in scored_groups[:top_k] if g[0] > 0] or all_groups[:top_k]

def recommend_partners(current_user, all_users, top_k=5):
    user_interests = set((current_user.subjects or "").lower().replace(',', ' ').split())
    scored_partners = []
    for other_user in all_users:
        if other_user.id == current_user.id: continue
        other_interests = set((other_user.subjects or "").lower().replace(',', ' ').split())
        overlap = len(user_interests.intersection(other_interests))
        if overlap > 0 or (current_user.skill_level == other_user.skill_level):
            score = (overlap * 20) + (10 if current_user.skill_level == other_user.skill_level else 0)
            scored_partners.append({'user': other_user, 'score': min(score, 99)})
    scored_partners.sort(key=lambda x: x['score'], reverse=True)
    return scored_partners[:top_k]

# Flask App Initialization
# Force instance_path to /tmp to avoid Read-Only errors
app = Flask(__name__, 
            instance_path='/tmp', 
            template_folder='../templates', 
            static_folder='../static')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'educonnect_secret_key_123')

# MongoDB Configuration
MONGO_URI = os.environ.get('MONGO_URI')
if not MONGO_URI:
    MONGO_URI = 'mongodb://localhost:27017/educonnect'
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client.educonnect
else:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
    try:
        db = client.get_default_database()
    except:
        db = client.educonnect

# Config
is_vercel = os.environ.get('VERCEL') == '1'
app.config['UPLOAD_FOLDER'] = '/tmp/uploads' if is_vercel else os.path.join(os.getcwd(), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Mail
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME', 'mock.educonnect@gmail.com'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD', 'dummy_password'),
    MAIL_DEFAULT_SENDER=os.environ.get('MAIL_USERNAME', 'mock.educonnect@gmail.com')
)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Ensure UI works
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except:
    pass

class MongoObject:
    def __init__(self, data):
        if data:
            for key, value in data.items(): setattr(self, key, value)
            self.id = str(data.get('_id'))

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
            if user_data: return dict(current_user=MongoObject(user_data))
        except: pass
    return dict(current_user=None)

@app.route('/health')
def health():
    return "EduConnect is healthy! v1.0.2"

# --- ROUTES ---
@app.route('/')
def index():
    try:
        total_users = db.users.count_documents({})
        active_users = db.users.count_documents({'is_active': True})
        total_groups = db.groups.count_documents({})
    except:
        return render_template('500.html', error_message="DB Error"), 500
    
    our_features = [
        {"icon": "🎯", "color": "indigo", "title": "Smart Matching", "desc": "Perfect study partners based on goals."},
        {"icon": "💬", "color": "teal", "title": "Real-Time chat", "desc": "Collaborate in live virtual rooms."},
        {"icon": "🧠", "color": "emerald", "title": "AI Recommendations", "desc": "Tailored groups and resources."},
        {"icon": "📁", "color": "blue", "title": "Resource Sharing", "desc": "Upload and share materials easily."}
    ]
    return render_template('index.html', total_users=total_users, active_users=active_users, total_groups=total_groups, our_features=our_features)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        if db.users.find_one({'email': email}):
            flash('Email already registered!', 'danger')
            return redirect(url_for('login'))
        
        user_id = db.users.insert_one({
            'name': request.form.get('name'),
            'email': email,
            'password_hash': generate_password_hash(request.form.get('password')),
            'subjects': request.form.get('subjects'),
            'skill_level': request.form.get('skill_level'),
            'availability': request.form.get('availability'),
            'is_active': True, 'is_verified': True
        }).inserted_id
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = db.users.find_one({'email': request.form.get('email')})
        if user and check_password_hash(user['password_hash'], request.form.get('password')):
            session['user_id'] = str(user['_id'])
            db.users.update_one({'_id': user['_id']}, {'$set': {'last_login': datetime.utcnow(), 'is_active': True}})
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    uid = ObjectId(session['user_id'])
    user = MongoObject(db.users.find_one({'_id': uid}))
    group_ids = [m['group_id'] for m in db.group_members.find({'user_id': uid})]
    joined_groups = [MongoObject(g) for g in db.groups.find({'_id': {'$in': group_ids}})]
    recommended_groups = recommend_groups(user, [MongoObject(g) for g in db.groups.find({})])
    return render_template('dashboard.html', user=user, joined_groups=joined_groups, recommended_groups=recommended_groups)

@app.route('/groups')
@login_required
def groups():
    uid = ObjectId(session['user_id'])
    all_groups = [MongoObject(g) for g in db.groups.find({})]
    joined_ids = [str(m['group_id']) for m in db.group_members.find({'user_id': uid})]
    return render_template('groups.html', groups=all_groups, joined_group_ids=joined_ids)

@app.route('/groups/create', methods=['GET', 'POST'])
@login_required
def create_group():
    if request.method == 'POST':
        gid = db.groups.insert_one({
            'name': request.form.get('name'),
            'subject': request.form.get('subject'),
            'description': request.form.get('description'),
            'creator_id': ObjectId(session['user_id'])
        }).inserted_id
        db.group_members.insert_one({'group_id': gid, 'user_id': ObjectId(session['user_id']), 'joined_at': datetime.utcnow()})
        return redirect(url_for('group_detail', group_id=str(gid)))
    return render_template('create_group.html')

@app.route('/groups/<group_id>')
@login_required
def group_detail(group_id):
    gid = ObjectId(group_id)
    group_data = db.groups.find_one({'_id': gid})
    if not group_data: return "Group not found", 404
    
    group = MongoObject(group_data)
    uid = ObjectId(session['user_id'])
    is_member = db.group_members.find_one({'group_id': gid, 'user_id': uid}) is not None
    
    messages = [MongoObject(m) for m in db.messages.find({'group_id': gid}).sort('timestamp', 1)]
    for m in messages:
        sender = db.users.find_one({'_id': ObjectId(m.user_id)})
        m.sender = MongoObject(sender) if sender else None
        
    resources = [MongoObject(r) for r in db.resources.find({'group_id': gid}).sort('upload_time', -1)]
    
    user_data = db.users.find_one({'_id': uid})
    recommended_partners = recommend_partners(MongoObject(user_data), [MongoObject(u) for u in db.users.find({})])
    
    return render_template('group_detail.html', group=group, is_member=is_member, messages=messages, resources=resources, recommended_partners=recommended_partners)

@app.route('/groups/<group_id>/join')
@login_required
def join_group(group_id):
    db.group_members.update_one(
        {'group_id': ObjectId(group_id), 'user_id': ObjectId(session['user_id'])},
        {'$setOnInsert': {'joined_at': datetime.utcnow()}},
        upsert=True
    )
    return redirect(url_for('group_detail', group_id=group_id))

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

@app.route('/groups/<group_id>/upload', methods=['POST'])
@login_required
def upload_resource(group_id):
    file = request.files.get('file')
    if file and file.filename:
        filename = secure_filename(file.filename)
        safe_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], safe_name))
        db.resources.insert_one({
            'file_name': filename,
            'file_path': safe_name,
            'group_id': ObjectId(group_id),
            'uploader_id': ObjectId(session['user_id']),
            'upload_time': datetime.utcnow()
        })
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/download/<resource_id>')
@login_required
def download_resource(resource_id):
    from flask import send_from_directory
    res = db.resources.find_one({'_id': ObjectId(resource_id)})
    if not res: return "File not found", 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], res['file_path'], as_attachment=True, download_name=res['file_name'])

# Vercel entry point
def handler(request):
    return app(request)

if __name__ == '__main__':
    app.run(debug=True, port=80)
