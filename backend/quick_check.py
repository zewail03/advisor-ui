# quick_check.py
import sqlite3
import os

print("🔍 QUICK DIAGNOSTIC CHECK")
print("=" * 60)

# 1. Check database file
print("\n1. Checking database file...")
if os.path.exists('aiu.db'):
    size = os.path.getsize('aiu.db')
    print(f"   ✅ aiu.db exists ({size} bytes)")
    
    # Check if it has new tables
    conn = sqlite3.connect('aiu.db')
    cursor = conn.cursor()
    
    new_tables = ['courses_catalog', 'course_sections', 'enrollments', 
                  'degree_requirements', 'enrollment_stats']
    
    for table in new_tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if cursor.fetchone():
            print(f"   ✅ Table '{table}' exists")
        else:
            print(f"   ❌ Table '{table}' MISSING!")
    
    conn.close()
else:
    print("   ❌ aiu.db NOT FOUND!")

# 2. Check models.py
print("\n2. Checking models.py...")
if os.path.exists('models.py'):
    with open('models.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'CoursesCatalog' in content:
            print("   ✅ CoursesCatalog model found")
        else:
            print("   ❌ CoursesCatalog model MISSING!")
        
        if 'Enrollment' in content:
            print("   ✅ Enrollment model found")
        else:
            print("   ❌ Enrollment model MISSING!")
else:
    print("   ❌ models.py NOT FOUND!")

# 3. Check main.py imports
print("\n3. Checking main.py imports...")
if os.path.exists('main.py'):
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'CoursesCatalog' in content:
            print("   ✅ CoursesCatalog imported")
        else:
            print("   ❌ CoursesCatalog NOT imported!")
        
        if '/me/enrolled-classes' in content:
            print("   ✅ Enrolled classes endpoint found")
        else:
            print("   ❌ Enrolled classes endpoint MISSING!")
        
        if 'from datetime import datetime' in content:
            print("   ✅ datetime imported")
        else:
            print("   ⚠️  datetime import MISSING (needed for some endpoints)")
else:
    print("   ❌ main.py NOT FOUND!")

print("\n" + "=" * 60)
print("📊 Diagnostic complete. Check for ❌ marks above.")