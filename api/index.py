# EduConnect v1.0.5 - Final Consolidated Logic
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message as MailMessage
from itsdangerous import URLSafeTimedSerializer
from pymongo import MongoClient
from bson.objectid import ObjectId
import certifi

# Load Environment Variables
from dotenv import load_dotenv
load_dotenv()

# Helpers
def recommend_groups(user, all_groups, top_k=5):
    if not all_groups: return []
    user_interests = set((user.subjects or "").lower().replace(',', ' ').split())
    scored = []
    for g in all_groups:
        text = f"{g.name} {g.subject} {g.description}".lower()
        score = sum(1 for w in user_interests if w in text)
        if user.subjects and g.subject and g.subject.lower() in user.subjects.lower(): score += 2
        scored.append((score, g))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[:top_k] if x[0] > 0] or all_groups[:top_k]

def recommend_partners(current_user, all_users, top_k=5):
    user_interests = set((current_user.subjects or "").lower().replace(',', ' ').split())
    scored = []
    for u in all_users:
        if str(u.id) == str(current_user.id): continue
        overlap = len(user_interests.intersection(set((u.subjects or "").lower().replace(',', ' ').split())))
        score = (overlap * 20) + (10 if current_user.skill_level == u.skill_level else 0)
        scored.append({'user': u, 'score': min(score, 99)})
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:top_k]

# Flask setup
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, 
            instance_path='/tmp',
            template_folder=os.path.join(basedir, '../templates'),
            static_folder=os.path.join(basedir, '../static'))

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'edu-secret-key-999')
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

# MongoDB
MONGO_URI = os.environ.get('MONGO_URI')
try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
        db = client.get_default_database()
        if db is None: db = client.educonnect
    else:
        client = MongoClient('mongodb://localhost:27017/educonnect', serverSelectionTimeoutMS=5000)
        db = client.educonnect
except:
    db = None

# Mail
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
    MAIL_DEFAULT_SENDER=os.environ.get('MAIL_USERNAME')
)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

class MongoObject:
    def __init__(self, data):
        if data:
            for k, v in data.items(): setattr(self, k, v)
            self.id = str(data.get('_id'))

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_user():
    if 'user_id' in session and db:
        try:
            u = db.users.find_one({'_id': ObjectId(session['user_id'])})
            if u: return dict(current_user=MongoObject(u))
        except: pass
    return dict(current_user=None)

# Standard Routes
@app.route('/')
def index():
    t_users, t_groups = 0, 0
    if db:
        try:
            t_users = db.users.count_documents({})
            t_groups = db.groups.count_documents({})
        except: pass
    
    features = [
        {"icon": "🎯", "color": "indigo", "title": "Smart Matching", "desc": "Perfect study partners find you."},
        {"icon": "💬", "color": "teal", "title": "Real-Time chat", "desc": "Collaborate in live virtual rooms."},
        {"icon": "🧠", "color": "emerald", "title": "AI Logic", "desc": "Tailored group discovery."},
        {"icon": "📁", "color": "blue", "title": "Resources", "desc": "Shared files and knowledge."}
    ]
    return render_template('index.html', total_users=t_users, active_users=t_users, total_groups=t_groups, our_features=features)

@app.route('/health')
def health(): return "OK"

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST' and db:
        if db.users.find_one({'email': request.form.get('email')}):
            flash('Email already registered!', 'danger')
            return redirect(url_for('login'))
        db.users.insert_one({
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'password_hash': generate_password_hash(request.form.get('password')),
            'subjects': request.form.get('subjects'),
            'skill_level': request.form.get('skill_level'),
            'availability': request.form.get('availability'),
            'is_active': True, 'is_verified': True
        })
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and db:
        u = db.users.find_one({'email': request.form.get('email')})
        if u and check_password_hash(u['password_hash'], request.form.get('password')):
            session['user_id'] = str(u['_id'])
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    uid = ObjectId(session['user_id'])
    user = MongoObject(db.users.find_one({'_id': uid}))
    gids = [m['group_id'] for m in db.group_members.find({'user_id': uid})]
    joined = [MongoObject(g) for g in db.groups.find({'_id': {'$in': gids}})]
    reco = recommend_groups(user, [MongoObject(g) for g in db.groups.find({})])
    return render_template('dashboard.html', user=user, joined_groups=joined, recommended_groups=reco)

@app.route('/groups')
@login_required
def groups():
    uid = ObjectId(session['user_id'])
    all_g = [MongoObject(g) for g in db.groups.find({})]
    jids = [str(m['group_id']) for m in db.group_members.find({'user_id': uid})]
    return render_template('groups.html', groups=all_g, joined_group_ids=jids)

@app.route('/groups/create', methods=['GET', 'POST'])
@login_required
def create_group():
    if request.method == 'POST' and db:
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
    g_data = db.groups.find_one({'_id': gid})
    if not g_data: return "NotFound", 404
    group = MongoObject(g_data)
    uid = ObjectId(session['user_id'])
    is_m = db.group_members.find_one({'group_id': gid, 'user_id': uid}) is not None
    msgs = [MongoObject(m) for m in db.messages.find({'group_id': gid}).sort('timestamp', 1)]
    for m in msgs:
        s = db.users.find_one({'_id': ObjectId(m.user_id)})
        m.sender = MongoObject(s) if s else None
    res = [MongoObject(r) for r in db.resources.find({'group_id': gid}).sort('upload_time', -1)]
    user_data = db.users.find_one({'_id': uid})
    reco_p = recommend_partners(MongoObject(user_data), [MongoObject(u) for u in db.users.find({})])
    return render_template('group_detail.html', group=group, is_member=is_m, messages=msgs, resources=res, recommended_partners=reco_p)

@app.route('/groups/<group_id>/join')
@login_required
def join_group(group_id):
    db.group_members.update_one({'group_id': ObjectId(group_id), 'user_id': ObjectId(session['user_id'])}, {'$setOnInsert': {'joined_at': datetime.utcnow()}}, upsert=True)
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/groups/<group_id>/message', methods=['POST'])
@login_required
def send_message(group_id):
    c = request.form.get('content')
    if c: db.messages.insert_one({'content': c, 'group_id': ObjectId(group_id), 'user_id': ObjectId(session['user_id']), 'timestamp': datetime.utcnow()})
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/groups/<group_id>/upload', methods=['POST'])
@login_required
def upload_resource(group_id):
    f = request.files.get('file')
    if f and f.filename:
        safe_n = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(f.filename)}"
        os.makedirs('/tmp/uploads', exist_ok=True)
        f.save(os.path.join('/tmp/uploads', safe_n))
        db.resources.insert_one({'file_name': f.filename, 'file_path': safe_n, 'group_id': ObjectId(group_id), 'uploader_id': ObjectId(session['user_id']), 'upload_time': datetime.utcnow()})
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/download/<resource_id>')
@login_required
def download_resource(resource_id):
    from flask import send_from_directory
    res = db.resources.find_one({'_id': ObjectId(resource_id)})
    if not res: return "404", 404
    return send_from_directory('/tmp/uploads', res['file_path'], as_attachment=True, download_name=res['file_name'])

if __name__ == "__main__":
    app.run(debug=True)
