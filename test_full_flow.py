import requests
import os

BASE_URL = 'http://127.0.0.1:5000'

def full_test():
    session = requests.Session()

    # 1. Login
    session.post(BASE_URL + '/login', data={'email': 'test@example.com', 'password': 'password123'})
    print("1. Logged in as test@example.com")

    # 2. Create a sample file to upload
    test_file_path = 'c:/EduConnect/test_notes.txt'
    with open(test_file_path, 'w') as f:
        f.write("EduConnect Study Notes\n")
        f.write("======================\n\n")
        f.write("Topic: Introduction to Machine Learning\n")
        f.write("Date: March 9, 2026\n\n")
        f.write("Key Points:\n")
        f.write("1. Supervised Learning uses labeled data\n")
        f.write("2. Unsupervised Learning finds hidden patterns\n")
        f.write("3. TF-IDF converts text to numerical vectors\n")
        f.write("4. Cosine Similarity measures text closeness\n")
    print("2. Created test_notes.txt")

    # 3. Upload file to group 1
    with open(test_file_path, 'rb') as f:
        res = session.post(f'{BASE_URL}/groups/1/upload', files={'file': ('test_notes.txt', f, 'text/plain')})
    print(f"3. Upload status: {res.status_code}")

    # 4. Find the resource ID (latest one)
    # Query the database directly
    import sqlite3
    conn = sqlite3.connect('c:/EduConnect/instance/database.db')
    cursor = conn.execute("SELECT id, file_name, file_path FROM resources ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        print("ERROR: No resource found in database after upload!")
        return

    resource_id, file_name, file_path = row
    print(f"4. Found resource in DB: id={resource_id}, name={file_name}")

    # 5. Download the file via the server route
    download_res = session.get(f'{BASE_URL}/download/{resource_id}')
    print(f"5. Download status: {download_res.status_code}")
    print(f"   Content-Type: {download_res.headers.get('Content-Type')}")
    print(f"   Content-Disposition: {download_res.headers.get('Content-Disposition')}")
    print(f"   Downloaded size: {len(download_res.content)} bytes")

    # 6. Save the downloaded file
    downloaded_path = 'c:/EduConnect/downloaded_test_notes.txt'
    with open(downloaded_path, 'wb') as f:
        f.write(download_res.content)
    print(f"6. Saved downloaded file to: {downloaded_path}")

    # 7. Read and verify content matches
    with open(downloaded_path, 'r') as f:
        downloaded_content = f.read()

    with open(test_file_path, 'r') as f:
        original_content = f.read()

    if downloaded_content == original_content:
        print("7. CONTENT MATCH: Downloaded file is IDENTICAL to the original!")
    else:
        print("7. CONTENT MISMATCH!")
        print(f"   Original length: {len(original_content)}")
        print(f"   Downloaded length: {len(downloaded_content)}")

    # 8. Print the downloaded file contents to prove it opens correctly
    print("\n--- DOWNLOADED FILE CONTENTS ---")
    print(downloaded_content)
    print("--- END OF FILE ---")

if __name__ == "__main__":
    full_test()
