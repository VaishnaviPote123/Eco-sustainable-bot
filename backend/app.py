from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import os
from dotenv import load_dotenv
import random
from datetime import date

# -------------------------------
# Load environment variables
# -------------------------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# -------------------------------
# FastAPI app setup
# -------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# In-memory database
# -------------------------------
users = {}      # username -> {"total": 0, "streak": 0, "completed_challenges": set()}
reminders = []  # list of {"username":..., "habit":..., "frequency":..., "enabled": True}

# Store daily challenge
daily_challenge_cache = {"date": None, "challenge": None}

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
# Static challenge list
# -------------------------------
challenges = [
    {"title":"Use Public Transport","description":"Use bus or train today","carbon_value":5},
    {"title":"Plant a Tree","description":"Plant one tree","carbon_value":10},
    {"title":"Save Water","description":"Take a short shower","carbon_value":2},
    {"title":"No Plastic","description":"Avoid plastic today","carbon_value":3}
]

# -------------------------------
# Health endpoint
# -------------------------------
@app.get("/")
def home():
    return {"status": "Eco Coach AI (LLaMA) running 🌱"}

# -------------------------------
# Chat endpoint using LLaMA via Groq
# -------------------------------
@app.post("/chat")
def chat(req: ChatRequest):
    prompt = f"""
You are an eco-friendly lifestyle coach.
Give simple, positive, and actionable advice.
User asked: {req.message}
"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a helpful sustainability coach."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        reply = completion.choices[0].message.content
    except Exception:
        reply = "🌱 Try small steps: reduce waste, save energy, and protect nature!"

    return {"reply": reply, "carbon_saved": 0}

# -------------------------------
# Daily challenge endpoint
# -------------------------------
@app.get("/challenge/daily")
def daily_challenge():
    today = str(date.today())
    if daily_challenge_cache["date"] == today and daily_challenge_cache["challenge"]:
        return daily_challenge_cache["challenge"]

    challenge = random.choice(challenges)
    daily_challenge_cache["date"] = today
    daily_challenge_cache["challenge"] = challenge
    return challenge

# -------------------------------
# Complete daily challenge
# -------------------------------
@app.post("/challenge/complete")
def complete_challenge(username: str):
    # Ensure user exists
    if username not in users:
        users[username] = {"total": 0, "streak": 0, "completed_challenges": set()}

    today = str(date.today())
    challenge = daily_challenge_cache.get("challenge")
    if not challenge:
        challenge = random.choice(challenges)
        daily_challenge_cache["date"] = today
        daily_challenge_cache["challenge"] = challenge

    challenge_id = challenge["title"]

    # Check if already completed
    if challenge_id in users[username]["completed_challenges"]:
        return {"message": "You already completed today's challenge!", "carbon_saved": 0}

    # Mark as completed
    users[username]["completed_challenges"].add(challenge_id)
    users[username]["total"] += challenge["carbon_value"]
    users[username]["streak"] += 1

    return {"message": f"Challenge completed! You saved {challenge['carbon_value']} kg CO2", 
            "carbon_saved": challenge["carbon_value"]}

# -------------------------------
# Carbon tracker endpoints
# -------------------------------
@app.post("/carbon/log")
def log_carbon(req: CarbonRequest):
    if req.username not in users:
        users[req.username] = {"total": 0, "streak": 0, "completed_challenges": set()}
    users[req.username]["total"] += req.carbon_saved
    users[req.username]["streak"] += 1
    return {"message": "Logged successfully"}

@app.get("/user/{username}")
def get_user(username: str):
    user = users.get(username)
    if user:
        return {
            "username": username,
            "total_carbon_saved": user["total"],
            "streak": user["streak"]
        }
    else:
        return {
            "username": username,
            "total_carbon_saved": 0,
            "streak": 0
        }

# -------------------------------
# Leaderboard endpoint
# -------------------------------
@app.get("/leaderboard")
def leaderboard():
    data = [{"username": u, "total_carbon_saved": v["total"]} for u, v in users.items()]
    data.sort(key=lambda x: x["total_carbon_saved"], reverse=True)
    return data

# -------------------------------
# Reminders endpoints
# -------------------------------
@app.post("/reminder/add")
def add_reminder(req: ReminderRequest):
    reminders.append({**req.dict(), "enabled": True})
    return {"message": "Reminder added"}

@app.get("/reminders/{username}")
def get_reminders(username: str):
    return [r for r in reminders if r["username"] == username]
