# test_backend.py
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

print("🧪 TESTING MANAGE CLASSES BACKEND")
print("=" * 60)

# Test 1: Health Check
print("\n1️⃣ Testing Health Check...")
response = requests.get(f"{BASE_URL}/")
print(f"   Status: {response.status_code}")
print(f"   Response: {response.json()}")
assert response.status_code == 200, "Health check failed!"
print("   ✅ PASSED")

# Test 2: Login
print("\n2️⃣ Testing Login...")
login_data = {
    "student_id": "20100243",
    "password": "1234"
}
response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
print(f"   Status: {response.status_code}")
print(f"   Response: {response.json()}")
assert response.status_code == 200, "Login failed!"

# Get token
token = response.json()["token"]
print(f"   Token: {token}")
print("   ✅ PASSED")

# Headers for authenticated requests
headers = {
    "Authorization": f"Bearer {token}"
}

# Test 3: Get Enrolled Classes
print("\n3️⃣ Testing Get Enrolled Classes...")
response = requests.get(f"{BASE_URL}/me/enrolled-classes", headers=headers)
print(f"   Status: {response.status_code}")
data = response.json()
print(f"   Found {len(data.get('classes', []))} enrolled classes")
for cls in data.get('classes', []):
    print(f"   - {cls['course_code']}: {cls['course_title']}")
assert response.status_code == 200, "Get enrolled classes failed!"
print("   ✅ PASSED")

# Test 4: Get Requirements
print("\n4️⃣ Testing Get Requirements...")
response = requests.get(f"{BASE_URL}/me/requirements", headers=headers)
print(f"   Status: {response.status_code}")
data = response.json()
print(f"   Found {len(data.get('requirements', []))} requirement categories")
for req in data.get('requirements', []):
    print(f"   - {req['category']}: {req['completion_percentage']}% complete")
assert response.status_code == 200, "Get requirements failed!"
print("   ✅ PASSED")

# Test 5: Search Courses
print("\n5️⃣ Testing Search Courses...")
response = requests.get(f"{BASE_URL}/courses/search?term=Fall 2025-2026")
print(f"   Status: {response.status_code}")
data = response.json()
print(f"   Found {data.get('count', 0)} available courses")
for course in data.get('courses', [])[:3]:  # Show first 3
    print(f"   - {course['course_code']}: {course['course_title']} ({course['available_seats']} seats)")
assert response.status_code == 200, "Search courses failed!"
print("   ✅ PASSED")

# Test 6: Get Course Sections
print("\n6️⃣ Testing Get Course Sections...")
response = requests.get(f"{BASE_URL}/courses/AIE322/sections")
print(f"   Status: {response.status_code}")
data = response.json()
print(f"   Course: {data['course']['title']}")
print(f"   Found {len(data.get('sections', []))} sections")
for section in data.get('sections', []):
    print(f"   - Section {section['section_number']}: {section['status']} ({section['available_seats']} seats)")
assert response.status_code == 200, "Get course sections failed!"
print("   ✅ PASSED")

# Test 7: Get Enrollment Stats
print("\n7️⃣ Testing Get Enrollment Stats...")
response = requests.get(f"{BASE_URL}/me/enrollment-stats", headers=headers)
print(f"   Status: {response.status_code}")
data = response.json()
print(f"   Enrolled Classes: {data.get('enrolled_classes')}")
print(f"   Units Completed: {data.get('units_completed')}")
print(f"   Completion: {data.get('completion_percentage')}%")
print(f"   Available to Enroll: {data.get('available_to_enroll')}")
assert response.status_code == 200, "Get enrollment stats failed!"
print("   ✅ PASSED")

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\n🎉 Your backend is ready for frontend integration!")