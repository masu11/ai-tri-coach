from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import os
import requests
import time
import psycopg

app = FastAPI()

CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI")
DATABASE_URL = os.getenv("DATABASE_URL")


# ---------------------------
# DATABASE INIT
# ---------------------------

def init_db():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    id SERIAL PRIMARY KEY,
                    access_token TEXT,
                    refresh_token TEXT,
                    expires_at BIGINT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id SERIAL PRIMARY KEY,
                    strava_id BIGINT UNIQUE,
                    name TEXT,
                    sport_type TEXT,
                    start_date TIMESTAMP,
                    duration INTEGER,
                    distance DOUBLE PRECISION,
                    avg_hr DOUBLE PRECISION,
                    avg_power DOUBLE PRECISION
                )
            """)

init_db()


# ---------------------------
# ROOT
# ---------------------------

@app.get("/")
def root():
    return {"status": "AI Tri Coach running (Postgres)"}


# ---------------------------
# LOGIN
# ---------------------------

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


# ---------------------------
# CALLBACK
# ---------------------------

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

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tokens")
            cur.execute(
                "INSERT INTO tokens (access_token, refresh_token, expires_at) VALUES (%s, %s, %s)",
                (access_token, refresh_token, expires_at),
            )

    return {"message": "Strava connected and token stored in Postgres"}


# ---------------------------
# TOKEN MANAGEMENT
# ---------------------------

def get_valid_token():

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("SELECT access_token, refresh_token, expires_at FROM tokens LIMIT 1")
            row = cur.fetchone()

            if not row:
                return None

            access_token, refresh_token, expires_at = row

            if time.time() > expires_at:

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

                cur.execute("DELETE FROM tokens")
                cur.execute(
                    "INSERT INTO tokens (access_token, refresh_token, expires_at) VALUES (%s, %s, %s)",
                    (access_token, refresh_token, expires_at),
                )

    return access_token


# ---------------------------
# SYNC
# ---------------------------

@app.get("/sync")
def incremental_sync():

    access_token = get_valid_token()

    if not access_token:
        return {"error": "Not authenticated"}

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            # zjisti nejnovější datum v DB
            cur.execute("SELECT MAX(start_date) FROM activities")
            result = cur.fetchone()
            last_date = result[0]

            params = {"per_page": 200}

            if last_date:
                # převod na timestamp
                timestamp = int(last_date.timestamp())
                params["after"] = timestamp

            total_new = 0
            page = 1

            while True:

                params["page"] = page

                response = requests.get(
                    "https://www.strava.com/api/v3/athlete/activities",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params,
                )

                activities = response.json()

                if not activities:
                    break

                for act in activities:
                    cur.execute("""
                        INSERT INTO activities
                        (strava_id, name, sport_type, start_date, duration, distance, avg_hr, avg_power)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (strava_id) DO NOTHING
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

                    total_new += 1

                page += 1

    return {"new_activities_synced": total_new}


# ---------------------------
# DB COUNT
# ---------------------------

@app.get("/db-count")
def db_count():

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM activities")
            count = cur.fetchone()[0]

    return {"db_activity_count": count}

# ---------------------------
# SUMMARY
# ---------------------------

@app.get("/summary")
def summary():

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            # celkový počet
            cur.execute("SELECT COUNT(*) FROM activities")
            total = cur.fetchone()[0]

            # podle sportu
            cur.execute("""
                SELECT sport_type, COUNT(*)
                FROM activities
                GROUP BY sport_type
            """)
            by_sport = dict(cur.fetchall())

            # celkový čas (v hodinách)
            cur.execute("SELECT SUM(duration) FROM activities")
            total_seconds = cur.fetchone()[0] or 0
            total_hours = round(total_seconds / 3600, 1)

            # celková vzdálenost (v km)
            cur.execute("SELECT SUM(distance) FROM activities")
            total_distance = cur.fetchone()[0] or 0
            total_km = round(total_distance / 1000, 1)

            # poslední aktivita
            cur.execute("""
                SELECT name, sport_type, start_date
                FROM activities
                ORDER BY start_date DESC
                LIMIT 1
            """)
            last_activity = cur.fetchone()

    return {
        "total_activities": total,
        "by_sport": by_sport,
        "total_hours": total_hours,
        "total_km": total_km,
        "last_activity": last_activity
    }
