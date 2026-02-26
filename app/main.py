from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import os
import requests
import sqlite3
import time

app = FastAPI()

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            expires_at INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY,
            strava_id INTEGER UNIQUE,
            name TEXT,
            sport_type TEXT,
            start_date TEXT,
            duration INTEGER,
            distance REAL,
            avg_hr REAL,
            avg_power REAL
        )
    """)

    conn.commit()
    conn.close()

init_db()

CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI")

ACCESS_TOKEN = None

@app.get("/")
def root():
    return {"status": "AI Tri Coach running"}

@app.get("/login")
def login():
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&approval_prompt=auto"
        f"&scope=activity:read_all"
    )
    return RedirectResponse(auth_url)

@app.get("/callback")
def callback(code: str):
    token_response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        },
    )

    token_data = token_response.json()

    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_at = token_data["expires_at"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM tokens")
    cursor.execute(
        "INSERT INTO tokens (access_token, refresh_token, expires_at) VALUES (?, ?, ?)",
        (access_token, refresh_token, expires_at),
    )

    conn.commit()
    conn.close()

    return {"message": "Strava connected and token stored"}

def get_valid_token():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT access_token, refresh_token, expires_at FROM tokens LIMIT 1")
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    access_token, refresh_token, expires_at = row

    if time.time() > expires_at:
        # token expired → refresh
        response = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

        token_data = response.json()
        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]
        expires_at = token_data["expires_at"]

        cursor.execute("DELETE FROM tokens")
        cursor.execute(
            "INSERT INTO tokens (access_token, refresh_token, expires_at) VALUES (?, ?, ?)",
            (access_token, refresh_token, expires_at),
        )

        conn.commit()

    conn.close()
    return access_token

@app.get("/sync")
def full_sync():
    access_token = get_valid_token()

    if not access_token:
        return {"error": "Not authenticated"}

    page = 1
    total_activities = 0

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    while True:
        response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"per_page": 200, "page": page},
        )

        activities = response.json()

        if not activities:
            break

        for act in activities:
            cursor.execute("""
                INSERT OR IGNORE INTO activities
                (strava_id, name, sport_type, start_date, duration, distance, avg_hr, avg_power)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                act["id"],
                act["name"],
                act["sport_type"],
                act["start_date"],
                act["moving_time"],
                act["distance"],
                act.get("average_heartrate"),
                act.get("average_watts"),
            ))

        total_activities += len(activities)
        page += 1

    conn.commit()
    conn.close()

    return {"synced_activities": total_activities}
