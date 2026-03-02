from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import os
import requests
import time
import psycopg
from datetime import datetime, timedelta, date
from garminconnect import Garmin
from psycopg.types.json import Json

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

            # TOKENS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    id SERIAL PRIMARY KEY,
                    access_token TEXT,
                    refresh_token TEXT,
                    expires_at BIGINT
                )
            """)

            # GARMIN DAILY METRICS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS garmin_daily_metrics (
                    date DATE PRIMARY KEY,
                    sleep_seconds INTEGER,
                    resting_hr INTEGER,
                    avg_hrv DOUBLE PRECISION,
                    body_battery INTEGER,
                    stress_avg INTEGER,
                    vo2max_run DOUBLE PRECISION,
                    vo2max_bike DOUBLE PRECISION,
                    weight DOUBLE PRECISION
                )
            """)

            # ACTIVITIES (EXTENDED)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id SERIAL PRIMARY KEY,
                    strava_id BIGINT UNIQUE,
                    name TEXT,
                    sport_type TEXT,
                    start_date TIMESTAMP,
                    duration INTEGER,
                    elapsed_time INTEGER,
                    distance DOUBLE PRECISION,
                    total_elevation_gain DOUBLE PRECISION,
                    avg_hr DOUBLE PRECISION,
                    max_hr DOUBLE PRECISION,
                    avg_power DOUBLE PRECISION,
                    avg_speed DOUBLE PRECISION,
                    max_speed DOUBLE PRECISION,
                    avg_cadence DOUBLE PRECISION,
                    calories DOUBLE PRECISION,
                    suffer_score DOUBLE PRECISION,
                    raw_json JSONB
                )
            """)

            # STREAMS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS activity_streams (
                    activity_id BIGINT PRIMARY KEY,
                    stream_data JSONB
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
# SYNC STRAVA
# ---------------------------

@app.get("/sync_strava")
def sync_strava():

    access_token = get_valid_token()
    if not access_token:
        return {"error": "Not authenticated"}

    total_processed = 0
    total_streams = 0

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("SELECT MAX(start_date) FROM activities")
            last_date = cur.fetchone()[0]

            params = {"per_page": 200}
            # pokud chceš full sync, zakomentuj after
            # if last_date:
            #     params["after"] = int(last_date.timestamp())

            page = 1

            while True:
                params["page"] = page

                r = requests.get(
                    "https://www.strava.com/api/v3/athlete/activities",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params
                )

                if r.status_code != 200:
                    return {"error": r.text}

                activities = r.json()
                if not activities:
                    break

                for act in activities:

                    # ---- DETAIL FETCH ----
                    detail_res = requests.get(
                        f"https://www.strava.com/api/v3/activities/{act['id']}",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )

                    if detail_res.status_code != 200:
                        continue

                    detail = detail_res.json()

                    cur.execute("""
                        INSERT INTO activities
                        (strava_id, name, sport_type, start_date,
                         duration, elapsed_time, distance,
                         total_elevation_gain,
                         avg_hr, max_hr,
                         avg_power, avg_speed, max_speed,
                         avg_cadence, calories, suffer_score,
                         raw_json)
                        VALUES (%s,%s,%s,%s,
                                %s,%s,%s,
                                %s,
                                %s,%s,
                                %s,%s,%s,
                                %s,%s,%s,
                                %s)
                        ON CONFLICT (strava_id) DO NOTHING
                    """, (
                        detail["id"],
                        detail["name"],
                        detail["sport_type"],
                        detail["start_date"],
                        detail["moving_time"],
                        detail.get("elapsed_time"),
                        detail["distance"],
                        detail.get("total_elevation_gain"),
                        detail.get("average_heartrate"),
                        detail.get("max_heartrate"),
                        detail.get("average_watts"),
                        detail.get("average_speed"),
                        detail.get("max_speed"),
                        detail.get("average_cadence"),
                        detail.get("calories"),
                        detail.get("suffer_score"),
                        Json(detail)
                    ))

                    total_processed += 1

                    # ---- STREAM FETCH (ALL STREAMS) ----
                    streams = requests.get(
                        f"https://www.strava.com/api/v3/activities/{detail['id']}/streams",
                        headers={"Authorization": f"Bearer {access_token}"},
                        params={
                            "keys": "time,heartrate,altitude,velocity_smooth,watts,cadence",
                            "key_by_type": "true"
                        }
                    )

                    if streams.status_code == 200:
                        stream_json = streams.json()

                        cur.execute("""
                            INSERT INTO activity_streams (activity_id, stream_data)
                            VALUES (%s, %s)
                            ON CONFLICT (activity_id) DO NOTHING
                        """, (
                            detail["id"],
                            Json(stream_json)
                        ))

                        total_streams += 1

                    time.sleep(0.6)

                page += 1

    return {
        "activities_processed": total_processed,
        "streams_saved": total_streams
    }




# ---------------------------
# GARMIN-BACKFILL
# volám např. /garmin-backfill?start=2023-01-01, když chci historii
# pro denní volání stačí takto /garmin-backfill
# ---------------------------

@app.get("/garmin-backfill")
def garmin_backfill(start: str | None = None):

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    today = date.today()

    api = Garmin(email, password)
    api.login()

    total_days = 0
    errors = 0

    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:

            # ---- 1️⃣ Určení startu ----
            cur.execute("SELECT MAX(date) FROM garmin_daily_metrics")
            last_saved = cur.fetchone()[0]

            if last_saved:
                current = last_saved + timedelta(days=1)
            else:
                if not start:
                    return {"error": "Provide start=YYYY-MM-DD for first run"}
                current = datetime.strptime(start, "%Y-%m-%d").date()

            # ---- 2️⃣ Smyčka ----
            while current <= today:

                try:
                    sleep = api.get_sleep_data(current.isoformat())
                    stats = api.get_stats(current.isoformat())
                    hrv = api.get_hrv_data(current.isoformat())
                    stress = api.get_stress_data(current.isoformat())

                    # ---- SAFE EXTRACTION ----

                    sleep_seconds = (
                        sleep.get("dailySleepDTO", {}).get("sleepTimeSeconds")
                        if isinstance(sleep, dict) else None
                    )

                    sleep_score = (
                        sleep.get("dailySleepDTO", {})
                             .get("sleepScores", {})
                             .get("overall")
                        if isinstance(sleep, dict) else None
                    )

                    resting_hr = stats.get("restingHeartRate") if isinstance(stats, dict) else None
                    recovery_time = stats.get("recoveryTime") if isinstance(stats, dict) else None
                    training_status = stats.get("trainingStatus") if isinstance(stats, dict) else None
                    vo2max_run = stats.get("vo2MaxValue") if isinstance(stats, dict) else None
                    acute_load = stats.get("acuteTrainingLoad") if isinstance(stats, dict) else None
                    chronic_load = stats.get("chronicTrainingLoad") if isinstance(stats, dict) else None

                    avg_hrv = (
                        hrv.get("hrvSummary", {}).get("lastNightAvg")
                        if isinstance(hrv, dict) else None
                    )

                    stress_avg = (
                        stress.get("overallStressLevel")
                        if isinstance(stress, dict) else None
                    )

                    # ---- UPSERT ----

                    cur.execute("""
                        INSERT INTO garmin_daily_metrics
                        (date, sleep_seconds, sleep_score,
                         resting_hr, avg_hrv, stress_avg,
                         vo2max_run, recovery_time,
                         training_status, acute_load, chronic_load)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (date) DO UPDATE SET
                            sleep_seconds = EXCLUDED.sleep_seconds,
                            sleep_score = EXCLUDED.sleep_score,
                            resting_hr = EXCLUDED.resting_hr,
                            avg_hrv = EXCLUDED.avg_hrv,
                            stress_avg = EXCLUDED.stress_avg,
                            vo2max_run = EXCLUDED.vo2max_run,
                            recovery_time = EXCLUDED.recovery_time,
                            training_status = EXCLUDED.training_status,
                            acute_load = EXCLUDED.acute_load,
                            chronic_load = EXCLUDED.chronic_load
                    """, (
                        current,
                        sleep_seconds,
                        sleep_score,
                        resting_hr,
                        avg_hrv,
                        stress_avg,
                        vo2max_run,
                        recovery_time,
                        training_status,
                        acute_load,
                        chronic_load
                    ))

                    total_days += 1

                except Exception as e:
                    print(f"Error on {current}: {e}")
                    errors += 1

                # ---- RATE LIMIT PROTECTION ----
                time.sleep(0.4)

                current += timedelta(days=1)

    return {
        "days_processed": total_days,
        "errors": errors
    }
