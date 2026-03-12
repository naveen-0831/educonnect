from app import app, db, User
from werkzeug.security import generate_password_hash

def add_sample_user():
    with app.app_context():
        # Create a sample user
        sample_user = User(
            name="Alice Smith",
            email="alice.smith@college.edu",
            password_hash=generate_password_hash("secure_password_123"),
            subjects="Computer Science, Machine Learning, Calculus",
            skill_level="Intermediate",
            availability="Evenings and Weekends",
            learning_goals="Looking to find a group for my AI final project and study for finals."
        )
        
        # Add to database
        db.session.add(sample_user)
        try:
            db.session.commit()
            print("Successfully added sample user 'Alice Smith' to the database.")
        except Exception as e:
            db.session.rollback()
            print(f"Error adding user: {e}")

if __name__ == "__main__":
    add_sample_user()
