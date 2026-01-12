from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random
import os
from dotenv import load_dotenv
import requests
import database as db
from urllib.parse import quote

# -------------------------------
# App setup
# -------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Load GROQ API key
# -------------------------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# -------------------------------
# Pydantic models
# -------------------------------
class ChatRequest(BaseModel):
    message: str
    username: str = "guest"

class CarbonRequest(BaseModel):
    username: str
    carbon_saved: float
    activity: str

class ReminderRequest(BaseModel):
    username: str
    habit: str
    frequency: str

# -------------------------------
# Chat endpoint
# -------------------------------
@app.post("/chat")
def chat(req: ChatRequest):
    # Ensure user exists
    user = db.get_user(req.username)
    if not user:
        db.create_user(req.username)

    # If GROQ key not set, fallback to static tips
    if not GROQ_API_KEY:
        tips = [
            "🌱 Reduce single-use plastics whenever possible.",
            "💧 Save water by taking shorter showers.",
            "🚶‍♂️ Walk, bike, or use public transport to reduce carbon emissions.",
        ]
        reply = f"{random.choice(tips)} You asked: {req.message}"
        return {"reply": reply, "carbon_saved": 0}

    # GROQ query for eco tips
    query = '*[_type=="ecoTip"]{tip}'
    encoded_query = quote(query)
    # Use Sanity API URL without project ID/dataset in code
    url = f"https://api.sanity.io/v2026-01-12/data/query?query={encoded_query}"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json().get("result", [])
        tip = random.choice(data).get("tip", "🌱 Live sustainably!") if data else "🌱 Live sustainably!"
        reply = f"{tip} You asked: {req.message}"
        return {"reply": reply, "carbon_saved": 0}
    except requests.exceptions.RequestException as e:
        return {"reply": f"🌱 Error fetching tips: {str(e)}", "carbon_saved": 0}

# -------------------------------
# Daily challenge endpoint (static fallback)
# -------------------------------
@app.get("/challenge/daily")
def daily_challenge():
    challenge_id = db.get_challenge_of_day()
    if challenge_id:
        conn = db.sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM challenges WHERE id = ?", (challenge_id,))
        challenge = cursor.fetchone()
        conn.close()
        if challenge:
            return {
                "title": challenge[1],
                "description": challenge[2],
                "carbon_value": challenge[3]
            }

    # fallback static challenges
    static_challenges = [
        {"title":"Use Public Transport","description":"Use bus or train today","carbon_value":5},
        {"title":"Plant a Tree","description":"Plant one tree","carbon_value":10},
        {"title":"Save Water","description":"Take a short shower","carbon_value":2},
        {"title":"No Plastic","description":"Avoid plastic today","carbon_value":3}
    ]
    return random.choice(static_challenges)

# -------------------------------
# Carbon tracker endpoints
# -------------------------------
@app.post("/carbon/log")
def log_carbon(req: CarbonRequest):
    user = db.get_user(req.username)
    if not user:
        user_id = db.create_user(req.username)
    else:
        user_id = user["id"]

    db.log_carbon(user_id, req.carbon_saved, req.activity)
    return {"message": "Logged successfully"}

@app.get("/user/{username}")
def get_user(username: str):
    user = db.get_user(username)
    if not user:
        return {"total": 0, "streak": 0}
    return {"total": user["total_carbon_saved"], "streak": user["streak"]}

# -------------------------------
# Leaderboard endpoint
# -------------------------------
@app.get("/leaderboard")
def leaderboard():
    return db.get_leaderboard()

# -------------------------------
# Reminders endpoints
# -------------------------------
@app.post("/reminder/add")
def add_reminder(req: ReminderRequest):
    user = db.get_user(req.username)
    if not user:
        user_id = db.create_user(req.username)
    else:
        user_id = user["id"]

    db.add_reminder(user_id, req.habit, req.frequency)
    return {"message": "Reminder added"}

@app.get("/reminders/{username}")
def get_reminders(username: str):
    user = db.get_user(username)
    if not user:
        return []
    return db.get_user_reminders(user["id"])

# -------------------------------
# Health check
# -------------------------------
@app.get("/")
def home():
    return {"message": "Eco Coach API running"}
