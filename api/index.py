from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return "VERIFIED: EduConnect is Live (v1.0.4)"

@app.route('/health')
def health():
    return "OK"
