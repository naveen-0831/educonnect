# EduConnect v1.0.3 - Final Vercel Push
import os
import sys
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
    user_subjects = (user.subjects or "").lower()
    scored = []
    for g in all_groups:
        score = sum(1 for w in user_subjects.split() if w in f"{g.name} {g.subject}".lower())
        scored.append((score, g))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[:top_k]]

def recommend_partners(current_user, all_users, top_k=5):
    user_subjects = set((current_user.subjects or "").lower().split())
    scored = []
    for u in all_users:
        if str(u.id) == str(current_user.id): continue
        overlap = len(user_subjects.intersection(set((u.subjects or "").lower().split())))
        scored.append({'user': u, 'score': overlap * 10})
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:top_k]

# Flask Initialization
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, 
            instance_path='/tmp',
            template_folder=os.path.join(basedir, '../templates'),
            static_folder=os.path.join(basedir, '../static'))

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'edu-secret-789')
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

# MongoDB - Robust Connection
MONGO_URI = os.environ.get('MONGO_URI')
try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=2000)
        db = client.get_default_database()
        if db is None: db = client.educonnect
    else:
        client = MongoClient('mongodb://localhost:27017/educonnect', serverSelectionTimeoutMS=2000)
        db = client.educonnect
except Exception as e:
    print(f"DB CONNECTION ERROR: {e}")
    db = None

# Mail
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD')
)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Classes
class MongoObject:
    def __init__(self, data):
        if data:
            for k, v in data.items(): setattr(self, k, v)
            self.id = str(data.get('_id'))

# Middleware
@app.context_processor
def inject_user():
    if 'user_id' in session and db:
        try:
            u = db.users.find_one({'_id': ObjectId(session['user_id'])})
            if u: return dict(current_user=MongoObject(u))
        except: pass
    return dict(current_user=None)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# Routes
@app.route('/')
def index():
    t_users, t_groups = 0, 0
    if db:
        try:
            t_users = db.users.count_documents({})
            t_groups = db.groups.count_documents({})
        except: pass
    return render_template('index.html', total_users=t_users, active_users=t_users, total_groups=t_groups)

@app.route('/health')
def health():
    return f"OK - DB {'UP' if db else 'DOWN'}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and db:
        u = db.users.find_one({'email': request.form.get('email')})
        if u and check_password_hash(u['password_hash'], request.form.get('password')):
            session['user_id'] = str(u['_id'])
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    uid = ObjectId(session['user_id'])
    user = MongoObject(db.users.find_one({'_id': uid}))
    gids = [m['group_id'] for m in db.group_members.find({'user_id': uid})]
    joined = [MongoObject(g) for g in db.groups.find({'_id': {'$in': gids}})]
    return render_template('dashboard.html', user=user, joined_groups=joined)

# Add other routes minimally if needed, or redirect them
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST' and db:
        hashed = generate_password_hash(request.form.get('password'))
        db.users.insert_one({'name': request.form.get('name'), 'email': request.form.get('email'), 'password_hash': hashed, 'is_verified': True})
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Error
@app.errorhandler(500)
def err500(e):
    return render_template('500.html', error_message=str(e)), 500

# Vercel expects the Flask instance to be 'app'
# No 'handler' function needed
if __name__ == "__main__":
    app.run(debug=True)
