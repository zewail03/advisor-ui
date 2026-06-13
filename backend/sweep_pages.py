# Per-page endpoint sweep. Logs in as 25100045 and hits each page's backend
# endpoint, classifying real-data / empty / error.
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"


def req(method, path, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode())
        except Exception:
            detail = None
        return e.code, detail
    except Exception as e:
        return -1, str(e)


def shape(payload):
    """Human summary of payload size/emptiness."""
    if payload is None:
        return "null"
    if isinstance(payload, list):
        return f"list[{len(payload)}]"
    if isinstance(payload, dict):
        # find the main list-bearing key if any
        for k, v in payload.items():
            if isinstance(v, list):
                return f"dict{{{k}: list[{len(v)}], ...}}"
        return "dict{" + ", ".join(list(payload.keys())[:4]) + ("..." if len(payload) > 4 else "") + "}"
    return type(payload).__name__


def verdict(status, payload):
    if status == 200:
        s = shape(payload)
        # empty-ish?
        if isinstance(payload, list) and len(payload) == 0:
            return "OK(empty)", s
        if isinstance(payload, dict):
            for v in payload.values():
                if isinstance(v, list) and len(v) > 0:
                    return "OK(data)", s
            # has scalar data
            if any(v not in (None, "", 0) for v in payload.values()):
                return "OK(data)", s
            return "OK(empty)", s
        return "OK(data)", s
    if status == -1:
        return "CONN-ERR", payload
    return f"HTTP {status}", (payload.get("detail") if isinstance(payload, dict) else payload)


# login
st, tok = req("POST", "/auth/login", body={"student_code": "25100045", "password": "changeme123"})
assert st == 200, f"login failed: {st} {tok}"
token = tok["access_token"]
print(f"Logged in as 25100045  (HTTP {st})\n")

# page -> (method, path, [body])
pages = [
    ("Dashboard",            "GET",  "/auth/me"),
    ("Profile",              "GET",  "/students/me"),
    ("GPA Sim (gpa)",        "GET",  "/students/me/gpa"),
    ("GPA Sim (req)",        "GET",  "/students/me/requirements"),
    ("Academic Records (tx)","GET",  "/students/me/transcript"),
    ("Academic Records (grad)","GET","/students/me/graduation-countdown"),
    ("Standing",             "GET",  "/students/me/standing"),
    ("Study Plan (plan)",    "GET",  "/students/me/study-plan"),
    ("Study Plan (gradchk)", "GET",  "/students/me/graduation-check"),
    ("Recovery Plan",        "GET",  "/students/me/recovery-plan"),
    ("Course Recs",          "GET",  "/students/me/course-recommendations"),
    ("My Classes (sched)",   "GET",  "/enrollments/me/schedule"),
    ("Requirements",         "GET",  "/students/me/requirements"),
    ("Advisor (me)",         "GET",  "/advisor/me"),
    ("Advisor (approvals)",  "GET",  "/advisor/me/approvals"),
    ("Petitions (elig)",     "GET",  "/petitions/me/eligibility"),
    ("Petitions (me)",       "GET",  "/petitions/me"),
    ("Capstone (elig)",      "GET",  "/capstone/me/eligibility"),
    ("Capstone (me)",        "GET",  "/capstone/me"),
    ("Attendance",           "GET",  "/attendance/me"),
    ("Evaluations",          "GET",  "/evaluations/me/pending"),
    ("Financial (balance)",  "GET",  "/financial/balance"),
    ("Financial (invoices)", "GET",  "/financial/invoices"),
    ("Financial (payments)", "GET",  "/financial/payment-history"),
    ("Financial (scholar)",  "GET",  "/financial/scholarships"),
    ("Notifications",        "GET",  "/notifications"),
    ("Retakes",              "GET",  "/retakes/me"),
    ("Audit",                "GET",  "/audit/me"),
    ("Settings (me)",        "GET",  "/auth/me"),
]

post_pages = [
    ("Schedule Generator", "POST", "/schedule/generate", {"semester_code": "Fall-2025"}),
    ("GPA Simulate (POST)", "POST", "/gpa/simulate", {"scenarios": [{"course_code": "CSE131", "predicted_grade": "A"}]}),
]

rows = []
for name, method, path in pages:
    st, payload = req(method, path, token)
    v, detail = verdict(st, payload)
    rows.append((name, path, v, detail))

for name, method, path, body in post_pages:
    st, payload = req(method, path, token, body)
    v, detail = verdict(st, payload)
    rows.append((name, path, v, detail))

w1 = max(len(r[0]) for r in rows)
w2 = max(len(r[1]) for r in rows)
print(f"{'PAGE/ENDPOINT'.ljust(w1)}  {'PATH'.ljust(w2)}  VERDICT")
print("-" * (w1 + w2 + 30))
for name, path, v, detail in rows:
    line = f"{name.ljust(w1)}  {path.ljust(w2)}  {v}"
    if not v.startswith("OK"):
        line += f"  -> {detail}"
    print(line)

bad = [r for r in rows if not r[2].startswith("OK")]
empty = [r for r in rows if r[2] == "OK(empty)"]
print(f"\nTOTAL {len(rows)}  |  OK(data) {len(rows)-len(bad)-len(empty)}  |  OK(empty) {len(empty)}  |  ERRORS {len(bad)}")
