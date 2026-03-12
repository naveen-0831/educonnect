# educonnect - Smart Collaborative Learning Platform

educonnect is a fully-featured online platform aimed at connecting college and university students with similar academic interests, enabling them to construct dynamic study groups, message in real-time, share resources, and receive AI-powered group recommendations.

## Project Structure
```
educonnect/
│
├── app.py                      # Main Flask Backend application
├── requirements.txt            # Python dependencies
├── database/
│   └── database.db             # SQLite database file (auto-generated)
│
├── templates/                  # Jinja2 HTML Templates
│   ├── base.html               # Main base layout template
│   ├── index.html              # Landing page
│   ├── login.html              # Login functionality
│   ├── register.html           # Registration & preferences
│   ├── profile.html            # Profile edit capability
│   ├── dashboard.html          # Student Dashboard
│   ├── groups.html             # Explore all study groups
│   ├── create_group.html       # Group creation wizard
│   └── group_detail.html       # Group workspace (Chat, Resources, Sessions)
│
├── static/
│   ├── css/
│   │   └── style.css           # Custom styling with variables and dark theme
│   └── js/
│       └── script.js           # Frontend interactivity (chats, alerts)
│
├── models/
│   └── recommendation_model.py # ML Recommendation Engine (TF-IDF/Cosine Similarity)
│
└── uploads/                    # Stores uploaded resources (auto-generated)
```

## Setup & Deployment Instructions

Follow these steps to deploy and run the project locally.

### 1. Install Dependencies
Make sure you have Python 3.8+ installed. Navigate to the project directory and install the required modules directly from the `requirements.txt` file.

```bash
cd c:\educonnect
pip install -r requirements.txt
```

### 2. Run the Application
Start the Flask application. Upon running the app for the first time, it automatically sets up the SQLite database and necessary configuration folders (`/uploads` & `/database`).

```bash
python app.py
```

### 3. Access the Platform
Once your Flask app is running, typically, it outputs a local address. Open a web browser and navigate to:
[http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Features Supported
- **Authentication**: Safe hashed passwords and session management.
- **Smart Recs Engine**: Matches user descriptions, topics of interest, and availabilities to group topics and schedules using Scikit-Learn TF-IDF vectorization.
- **Modern UI Framework**: fully custom, variable-driven CSS structure reflecting advanced modern designs.
- **Workspace Tooling**: In-app chatting schemas, file transfer (secure upload handling), and scheduling.
- **AI Assistant**: Global chatbot with Google Search grounding powered by Gemini 1.5, capable of searching the web to answer academic queries and provide study resources.

## Environment Configuration
The AI Chatbot requires a Google Gemini API Key. Reference `.env_template` for setup.
