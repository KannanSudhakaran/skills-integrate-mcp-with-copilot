"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}

# --- Simple admin/teacher support (temporary, file-backed credentials + in-memory sessions)
current_dir = Path(__file__).parent
_creds_file = current_dir / "teacher_credentials.json"
TEACHER_CREDS = {"teachers": []}
if _creds_file.exists():
    try:
        with open(_creds_file, "r") as f:
            TEACHER_CREDS = json.load(f)
    except Exception:
        # If the file is malformed, keep empty creds to avoid accidental lockout
        TEACHER_CREDS = {"teachers": []}

# token -> expiry (ISO timestamp string)
ADMIN_SESSIONS: dict = {}


def _create_admin_token() -> str:
    token = uuid.uuid4().hex
    expiry = datetime.utcnow() + timedelta(hours=8)
    ADMIN_SESSIONS[token] = expiry.isoformat()
    return token


def _validate_admin_token(token: Optional[str]) -> bool:
    if not token:
        return False
    # strip possible "Bearer " prefix
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]
    expiry_iso = ADMIN_SESSIONS.get(token)
    if not expiry_iso:
        return False
    try:
        expiry = datetime.fromisoformat(expiry_iso)
    except Exception:
        return False
    if datetime.utcnow() > expiry:
        # expired - remove
        ADMIN_SESSIONS.pop(token, None)
        return False
    return True


def require_admin(authorization: Optional[str] = Header(None)):
    """Dependency for endpoints that require a logged-in teacher (admin)."""
    if not _validate_admin_token(authorization or ""):
        raise HTTPException(status_code=401, detail="Admin authentication required")


@app.post("/admin/login")
def admin_login(credentials: dict):
    """Login as a teacher. Body: {"username":"...","password":"..."}

    Returns a temporary token that should be used in Authorization: Bearer <token>
    """
    username = credentials.get("username")
    password = credentials.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    for t in TEACHER_CREDS.get("teachers", []):
        if t.get("username") == username and t.get("password") == password:
            token = _create_admin_token()
            return {"token": token, "expires_in_hours": 8}

    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/admin/logout")
def admin_logout(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=400, detail="Authorization header required")
    token = authorization.split(" ", 1)[1] if authorization.startswith("Bearer ") else authorization
    ADMIN_SESSIONS.pop(token, None)
    return {"detail": "logged out"}



@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, _admin=Depends(require_admin)):
    """Unregister a student from an activity. Only teachers (admins) may unregister students."""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
