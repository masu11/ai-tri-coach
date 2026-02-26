from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import os
import requests

app = FastAPI()

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
    global ACCESS_TOKEN

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
    ACCESS_TOKEN = token_data["access_token"]

    return {"message": "Strava connected successfully"}

@app.get("/sync")
def full_sync():
    global ACCESS_TOKEN

    if not ACCESS_TOKEN:
        return {"error": "Not authenticated"}

    page = 1
    total_activities = 0

    while True:
        response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
            params={"per_page": 200, "page": page},
        )

        activities = response.json()

        if not activities:
            break

        total_activities += len(activities)
        page += 1

    return {"total_activities": total_activities}
