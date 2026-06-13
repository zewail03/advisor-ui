# debug_test.py
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

print("🔍 DEBUGGING ENROLLED CLASSES ENDPOINT")
print("=" * 60)

# Login first
print("\n1️⃣ Getting token...")
login_data = {
    "student_id": "20100243",
    "password": "1234"
}
response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
token = response.json()["token"]
print(f"   Token: {token}")

# Test enrolled classes with detailed error info
print("\n2️⃣ Testing enrolled classes endpoint...")
headers = {
    "Authorization": f"Bearer {token}"
}

response = requests.get(f"{BASE_URL}/me/enrolled-classes", headers=headers)
print(f"   Status Code: {response.status_code}")
print(f"   Response Headers: {dict(response.headers)}")
print(f"\n   Response Text:")
print(f"   {response.text}")

if response.status_code == 500:
    print("\n❌ SERVER ERROR DETECTED!")
    print("Check your FastAPI server logs for the detailed error.")
    print("\nLikely causes:")
    print("1. Missing import in main.py")
    print("2. Database table doesn't exist")
    print("3. Typo in endpoint code")