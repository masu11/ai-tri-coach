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

# ---------------------------
# LOAD
# ---------------------------


@app.get("/load")
def training_load():

    sport_factors = {
        "Run": 1.2,
        "Ride": 1.0,
        "VirtualRide": 1.0,
        "GravelRide": 1.0,
        "MountainBikeRide": 1.0,
        "Swim": 1.3
    }

    activities = []

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sport_type, duration, start_date
                FROM activities
                ORDER BY start_date
            """)
            rows = cur.fetchall()

    daily_load = {}

    for sport, duration, date in rows:

        hours = duration / 3600
        factor = sport_factors.get(sport, 0.7)

        load = hours * factor

        day = date.date()

        if day not in daily_load:
            daily_load[day] = 0

        daily_load[day] += load

    # seřadíme dny
    sorted_days = sorted(daily_load.keys())

    atl_values = []
    ctl_values = []

    ATL_DAYS = 7
    CTL_DAYS = 42

    for i in range(len(sorted_days)):

        recent_7 = sorted_days[max(0, i-ATL_DAYS+1):i+1]
        recent_42 = sorted_days[max(0, i-CTL_DAYS+1):i+1]

        atl = sum(daily_load[d] for d in recent_7) / ATL_DAYS
        ctl = sum(daily_load[d] for d in recent_42) / CTL_DAYS

        atl_values.append(atl)
        ctl_values.append(ctl)

    if not atl_values:
        return {"error": "No data"}

    current_atl = round(atl_values[-1], 2)
    current_ctl = round(ctl_values[-1], 2)
    form = round(current_ctl - current_atl, 2)

    return {
        "current_ATL_7d": current_atl,
        "current_CTL_42d": current_ctl,
        "form": form
    }

from datetime import timedelta

# ---------------------------
# WEEKLY-LOAD
# ---------------------------


@app.get("/weekly-load")
def weekly_load():

    sport_factors = {
        "Run": 1.2,
        "Ride": 1.0,
        "VirtualRide": 1.0,
        "GravelRide": 1.0,
        "MountainBikeRide": 1.0,
        "Swim": 1.3
    }

    weekly = {}

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sport_type, duration, start_date
                FROM activities
            """)
            rows = cur.fetchall()

    for sport, duration, date in rows:

        hours = duration / 3600
        factor = sport_factors.get(sport, 0.7)
        load = hours * factor

        # pondělí jako začátek týdne
        week_start = (date - timedelta(days=date.weekday())).date()

        if week_start not in weekly:
            weekly[week_start] = 0

        weekly[week_start] += load

    # seřadíme týdny
    sorted_weeks = sorted(weekly.keys())

    result = []

    for w in sorted_weeks[-12:]:  # posledních 12 týdnů
        result.append({
            "week_start": str(w),
            "load": round(weekly[w], 2)
        })

    return result

# ---------------------------
# WEEKLY-LOAD-BY-SPORT
# ---------------------------


@app.get("/weekly-load-by-sport")
def weekly_load_by_sport():

    sport_factors = {
        "Run": 1.2,
        "Ride": 1.0,
        "VirtualRide": 1.0,
        "GravelRide": 1.0,
        "MountainBikeRide": 1.0,
        "Swim": 1.3
    }

    weekly = {}

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sport_type, duration, start_date
                FROM activities
            """)
            rows = cur.fetchall()

    for sport, duration, date in rows:

        hours = duration / 3600
        factor = sport_factors.get(sport, 0.7)
        load = hours * factor

        week_start = (date - timedelta(days=date.weekday())).date()

        if week_start not in weekly:
            weekly[week_start] = {}

        if sport not in weekly[week_start]:
            weekly[week_start][sport] = 0

        weekly[week_start][sport] += load

    sorted_weeks = sorted(weekly.keys())

    result = []

    for w in sorted_weeks[-8:]:  # posledních 8 týdnů
        sport_data = {
            sport: round(load, 2)
            for sport, load in weekly[w].items()
        }

        result.append({
            "week_start": str(w),
            "sports": sport_data
        })

    return result

# ---------------------------
# DEBUG-SWIM-WEE
# ---------------------------


@app.get("/debug-swim-week")
def debug_swim_week():

    from datetime import date

    target_week = date(2026, 1, 12)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT name, duration, start_date
                FROM activities
                WHERE sport_type = 'Swim'
                  AND start_date >= %s
                  AND start_date < %s
                ORDER BY duration DESC
            """, (target_week, target_week + timedelta(days=7)))

            rows = cur.fetchall()

    result = []

    for name, duration, start_date in rows:
        result.append({
            "name": name,
            "duration_minutes": round(duration / 60, 1),
            "duration_hours": round(duration / 3600, 2),
            "date": str(start_date)
        })

    return result
