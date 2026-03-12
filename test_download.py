import requests

BASE_URL = 'http://127.0.0.1:5000'
session = requests.Session()

def test_download():
    # Login
    login_data = {
        'email': 'test@example.com',
        'password': 'password123'
    }
    session.post(BASE_URL + '/login', data=login_data)
    
    # We find the file ID to download. In the database, the latest resource is likely ID 1 or 2.
    # We can try ID 1 (which corresponds to your PDF) and ID 2 (which corresponds to dummy.txt)
    try:
        res = session.get(BASE_URL + '/download/1')
        print(f"File 1 Resource Exists: {res.status_code == 200}")
        if res.status_code == 200:
            print(f"File 1 Headers: {res.headers.get('Content-Disposition')}")
            print(f"File 1 Size Bytes: {len(res.content)}")
            
            with open('c:/EduConnect/downloaded_file1.pdf', 'wb') as f:
                f.write(res.content)
            print("Successfully saved file 1.")
            
        res2 = session.get(BASE_URL + '/download/2')
        print(f"File 2 Resource Exists: {res2.status_code == 200}")
        if res2.status_code == 200:
            with open('c:/EduConnect/downloaded_file2.txt', 'wb') as f:
                f.write(res2.content)
            print("Successfully saved file 2.")
            
    except Exception as e:
        print(f"Error during download test: {e}")

if __name__ == "__main__":
    test_download()
