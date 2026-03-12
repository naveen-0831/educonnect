import requests
import json

BASE_URL = 'http://127.0.0.1:5003'
session = requests.Session()

def run_tests():
    print("--- Starting End-to-End API Tests ---")
    
    # 1. Test Home Page
    res = session.get(BASE_URL + '/')
    print(f"1. Home Page GET: {res.status_code == 200}")
    
    import time
    ts = int(time.time())
    email = f"test_{ts}@example.com"
    
    # 2. Test Registration
    reg_data = {
        'name': 'Test User',
        'email': email,
        'password': 'password123',
        'subjects': 'Math, Computer Science',
        'skill_level': 'Intermediate',
        'availability': 'Weekends'
    }
    res = session.post(BASE_URL + '/register', data=reg_data)
    print(f"2. Registration POST: {res.status_code == 200 or res.status_code == 302}")
    
    # 3. Test Login
    login_data = {
        'email': email,
        'password': 'password123'
    }
    res = session.post(BASE_URL + '/login', data=login_data, allow_redirects=True)
    print(f"3. Login POST: {res.status_code == 200}")
    if "Logged in successfully" not in res.text:
        print("Login failed message not found in response")
    
    # 4. Test Dashboard Accessibility (Logged In)
    res = session.get(BASE_URL + '/dashboard')
    dashboard_ok = res.status_code == 200 and 'Welcome back, Test User!' in res.text
    print(f"4. Dashboard GET: {dashboard_ok}")
    if not dashboard_ok:
        print(f"Dashboard status: {res.status_code}")
        # print(res.text[:500]) # Too long usually
    
    # 5. Create a Study Group
    group_data = {
        'name': 'Python Beginners',
        'subject': 'Computer Science',
        'description': 'Let\'s learn Python together.',
        'meeting_time': 'Sundays 10 AM'
    }
    res = session.post(BASE_URL + '/groups/create', data=group_data)
    print(f"5. Create Group POST: {res.status_code == 200} (Redirected to group detail)")
    
    # 6. Verify Group Exists in Groups List
    res = session.get(BASE_URL + '/groups')
    print(f"6. Groups List GET: {res.status_code == 200 and 'Python Beginners' in res.text}")
    
    # 7. Edit Profile Dashboard
    prof_data = {
        'subjects': 'Math, Physics, CS',
        'skill_level': 'Advanced',
        'availability': 'Anytime',
        'learning_goals': 'Master data structures.'
    }
    res = session.post(BASE_URL + '/profile', data=prof_data)
    print(f"7. Profile Update POST: {res.status_code == 200} (Redirected to profile)")
    
    # 8. Test ML Recommendations in Dashboard
    res = session.get(BASE_URL + '/dashboard')
    print(f"8. Recommendation Engine Load POST: {res.status_code == 200} (No exceptions)")
    
    # 9. Test Logout
    res = session.get(BASE_URL + '/logout')
    print(f"9. Logout GET: {res.status_code == 200} (Redirected to home)")
    
    # 10. Dashboard Access (Logged Out)
    res = session.get(BASE_URL + '/dashboard', allow_redirects=False)
    print(f"10. Dashboard Protected GET (Expected 302): {res.status_code == 302}")
    
    print("--- Tests Completed ---")

if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print(f"Test failed: {e}")
