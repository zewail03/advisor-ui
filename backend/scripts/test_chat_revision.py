"""E2E chat test: plan request then the exact 'lighter Fall 2027' follow-up.

Run:  cd backend && .\\venv\\Scripts\\python.exe scripts\\test_chat_revision.py
"""
import json
import sys

import requests

BASE = "http://localhost:8000"


def login() -> str:
    r = requests.post(f"{BASE}/auth/login",
                      json={"student_code": "25100002", "password": "changeme123"})
    r.raise_for_status()
    return r.json()["access_token"]


def chat(token: str, message: str, session_id=None):
    r = requests.post(
        f"{BASE}/chat/message",
        json={"message": message, "session_id": session_id, "language": "en"},
        headers={"Authorization": f"Bearer {token}"},
        stream=True, timeout=120,
    )
    r.raise_for_status()
    sid, intent, text = session_id, None, []
    event = None
    for raw in r.iter_lines(decode_unicode=True):
        if raw is None or raw == "":
            continue
        if raw.startswith("event:"):
            event = raw.split(":", 1)[1].strip()
        elif raw.startswith("data:"):
            data = raw.split(":", 1)[1].strip()
            if event == "session":
                obj = json.loads(data)
                sid, intent = obj.get("session_id"), obj.get("intent")
            elif event == "token":
                try:
                    text.append(json.loads(data)["t"])
                except Exception:
                    text.append(data)
    return sid, intent, "".join(text)


if __name__ == "__main__":
    token = login()
    sid, intent1, a1 = chat(token, "i finish first year and i wanna you make plan to early gradution")
    print(f"--- Q1 intent={intent1} ---\n{a1}\n")
    sid, intent2, a2 = chat(token, "can i make Fall 2027 more lightly load", sid)
    print(f"--- Q2 intent={intent2} ---\n{a2}\n")

    bad = []
    if intent2 != "graduation_planning":
        bad.append(f"follow-up intent={intent2}, expected graduation_planning")
    if "10" in a2 and "Summer 2027" in a2 and "10 CH" in a2:
        bad.append("possible 10-CH summer in answer")
    print("RESULT:", "; ".join(bad) if bad else "OK (inspect answers above)")
    sys.exit(1 if bad else 0)
