import os
import requests
import json

def test_ai():
    url = "http://127.0.0.1:5002/api/chat"
    payload = {"message": "Hello, explain AI in 10 words."}
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ai()
