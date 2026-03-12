import requests
import json
import os

BASE_URL = 'http://127.0.0.1:5000'

def test_upload():
    session = requests.Session()
    
    # 1. Login as an existing user
    login_data = {
        'email': 'test@example.com',
        'password': 'password123'
    }
    session.post(BASE_URL + '/login', data=login_data)
    print("Logged in")
    
    # 2. Get the group ID (assuming at least one group exists from earlier tests)
    # We can just upload to group 1
    group_id = 1
    
    # 3. Upload a file
    file_path = 'c:/EduConnect/dummy.txt'
    with open(file_path, 'rb') as f:
        files = {'file': f}
        upload_res = session.post(f"{BASE_URL}/groups/{group_id}/upload", files=files)
        
    print(f"Upload Status Code: {upload_res.status_code}")
    
    # 4. Check the uploads directory manually
    upload_dir = 'c:/EduConnect/uploads'
    uploaded_files = os.listdir(upload_dir)
    print(f"Files in uploads dir: {uploaded_files}")
    
    if not uploaded_files:
        print("Upload failed: No files found in uploads directory.")
        return
        
    # Get the latest uploaded file
    latest_file = max([os.path.join(upload_dir, f) for f in uploaded_files], key=os.path.getctime)
    file_name = os.path.basename(latest_file)
    print(f"Latest uploaded file: {file_name}")
    
    # Need to find the resource ID to download via the app. Let's just read the file directly first
    # to see if it's corrupted on the server side.
    with open(latest_file, 'r') as f:
        content = f.read()
        print(f"Content on server:\n{content}")
        
if __name__ == "__main__":
    test_upload()
