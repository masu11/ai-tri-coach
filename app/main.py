from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import os
import requests
import time
import psycopg
from datetime import datetime, timedelta, date
from garminconnect import Garmin
from psycopg.types.json import Json
from app.routers import admin_router
from fastapi import BackgroundTasks


app = FastAPI()
app.include_router(admin_router.router)

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

@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "AI Tri Coach running (Postgres)"}

# ---------------------------
# HEALTH - slouží k ping, aby render neusnul
# ---------------------------

@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok"}
# ---------------------------
# CRON_SYNC - slouží k synchromizaci se STRAVA a GARMIN 
# ---------------------------

@app.api_route("/cron_sync", methods=["GET", "HEAD"])
def cron_sync(background_tasks: BackgroundTasks):

    background_tasks.add_task(run_sync)

    return {"status": "cron triggered"}


# ---------------------------
# RUN_SYNC
# ---------------------------


sync_running = False
last_sync_date = None


def run_sync():
    global sync_running, last_sync_date

    today = datetime.utcnow().date()

    if sync_running:
        print("Sync already running")
        return

    if last_sync_date == today:
        print("Sync already done today")
        return

    sync_running = True

    try:
        print("Starting Garmin + Strava sync")

        sync_garmin()
        sync_strava()

        last_sync_date = today

        print("Sync completed")

    finally:
        sync_running = False

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
# calculate_tss - počítá TSS pro insert do activities
# ---------------------------

def calculate_tss(activity):

    duration = activity.get("moving_time")
    sport = activity.get("sport_type")
    power = activity.get("average_watts")
    hr = activity.get("average_heartrate")

    if not duration:
        return None

    hours = duration / 3600

    # Bike power TSS
    if sport in ["Ride", "VirtualRide", "GravelRide", "MountainBikeRide"] and power:
        ftp = 250  # nastavíš podle sebe
        return hours * (power / ftp) ** 2 * 100

    # Run hrTSS
    if sport == "Run" and hr:
        threshold_hr = 170
        intensity = hr / threshold_hr
        return hours * intensity**2 * 100

    # Swim approximace
    if sport == "Swim":
        return hours * 60

    return hours * 50

# ---------------------------
# SYNC STRAVA
# ---------------------------

@app.get("/sync_strava")
def sync_strava(full: int = 0):

    access_token = get_valid_token()
    if not access_token:
        return {"error": "Not authenticated"}

    total_processed = 0

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("SELECT MAX(start_date) FROM activities")
            last_date = cur.fetchone()[0]

            params = {
                "per_page": 200
            }

            if not full and last_date:
                params["after"] = int(last_date.timestamp())

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

                    tss = calculate_tss(detail)

                    cur.execute("""
                    INSERT INTO activities
                    (strava_id, name, sport_type, start_date,
                    duration, elapsed_time, distance,
                    total_elevation_gain,
                    avg_hr, max_hr,
                    avg_power, avg_speed, max_speed,
                    avg_cadence, calories, suffer_score,
                    raw_json, tss)
                    VALUES (%s,%s,%s,%s,
                            %s,%s,%s,
                            %s,
                            %s,%s,
                            %s,%s,%s,
                            %s,%s,%s,
                            %s,%s)
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
                        Json(detail),
                        tss
                    ))

                    total_processed += 1

                page += 1

                time.sleep(1.2)

    return {
        "activities_processed": total_processed
    }





# ---------------------------
# SYNC GARMIN
# normální běh /sync_garmin
# první běh /sync_garmin?start=2023-01-01
# DEBUG jednoho dne: /sync_garmin?start=2024-06-01&debug_date=2024-06-01
# ---------------------------

@app.get("/sync_garmin")
def sync_garmin(start: str | None = None, debug_date: str | None = None):

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    today = date.today()

    api = Garmin(email, password)
    api.login()

    total_days = 0
    errors = 0

    debug_target = None
    if debug_date:
        debug_target = datetime.strptime(debug_date, "%Y-%m-%d").date()

    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:

            # ---- START DATE ----
            #cur.execute("SELECT MAX(date) FROM garmin_daily_metrics")
            #last_saved = cur.fetchone()[0]

            #if debug_target:
            #    current = debug_target
            #elif last_saved:
            #   current = last_saved + timedelta(days=1)
            #else:
            #    if not start:
            #        return {"error": "Provide start=YYYY-MM-DD for first run"}
            #    current = datetime.strptime(start, "%Y-%m-%d").date()

            # ---- START DATE ----
            if debug_target:
                current = debug_target
            elif start:
                current = datetime.strptime(start, "%Y-%m-%d").date()
            elif last_saved:
                current = last_saved + timedelta(days=1)
            else:
                return {"error": "Provide start=YYYY-MM-DD for first run"}                

            # ---- LOOP ----
            while current <= today:

                try:
                    sleep = api.get_sleep_data(current.isoformat())
                    stats = api.get_stats(current.isoformat())
                    hrv = api.get_hrv_data(current.isoformat())
                    stress = api.get_stress_data(current.isoformat())

                    # ---- DEBUG MODE ----
                    if debug_target:
                        return {
                            "date": str(current),
                            "sleep": sleep,
                            "stats": stats,
                            "hrv": hrv,
                            "stress": stress
                        }

                    # ---- SAFE EXTRACTION ----

                    sleep_seconds = (
                        sleep.get("dailySleepDTO", {}).get("sleepTimeSeconds")
                        if isinstance(sleep, dict)
                        else None
                    )

                    sleep_score = (
                        sleep.get("dailySleepDTO", {})
                             .get("sleepScores", {})
                             .get("overall", {})
                             .get("value")
                        if isinstance(sleep, dict)
                        else None
                    )

                    deep_sleep = (
                        sleep.get("dailySleepDTO", {}).get("deepSleepSeconds")
                        if isinstance(sleep, dict)
                        else None
                    )

                    rem_sleep = (
                        sleep.get("dailySleepDTO", {}).get("remSleepSeconds")
                        if isinstance(sleep, dict)
                        else None
                    )

                    resting_hr = stats.get("restingHeartRate") if isinstance(stats, dict) else None
                    recovery_time = stats.get("recoveryTime") if isinstance(stats, dict) else None
                    training_status = stats.get("trainingStatus") if isinstance(stats, dict) else None
                    vo2max_run = stats.get("vo2MaxValue") if isinstance(stats, dict) else None
                    acute_load = stats.get("acuteTrainingLoad") if isinstance(stats, dict) else None
                    chronic_load = stats.get("chronicTrainingLoad") if isinstance(stats, dict) else None
                    body_battery = stats.get("bodyBatteryMostRecentValue") if isinstance(stats, dict) else None

                    avg_hrv = (
                        hrv.get("hrvSummary", {}).get("lastNightAvg")
                        if isinstance(hrv, dict)
                        else None
                    )

                    stress_avg = (
                        stress.get("avgStressLevel")
                        if isinstance(stress, dict)
                        else None
                    )

                    # ---- BODY COMPOSITION ----
                    weight = None
                    body_fat = None
                    muscle_mass = None

                    try:
                        body = api.get_body_composition(
                            current.isoformat(),
                            current.isoformat()
                        )
                        if isinstance(body, list) and body:
                            weight = body[0].get("weight")
                            body_fat = body[0].get("bodyFat")
                            muscle_mass = body[0].get("muscleMass")
                    except:
                        pass

                    # ---- UPSERT ----

                    cur.execute("""
                        INSERT INTO garmin_daily_metrics
                        (date, sleep_seconds, sleep_score,
                         deep_sleep, rem_sleep,
                         resting_hr, avg_hrv, stress_avg,
                         body_battery,
                         vo2max_run, recovery_time,
                         training_status, acute_load, chronic_load,
                         weight, body_fat, muscle_mass)
                        VALUES (%s,%s,%s,
                                %s,%s,
                                %s,%s,%s,
                                %s,
                                %s,%s,
                                %s,%s,%s,
                                %s,%s,%s)
                        ON CONFLICT (date) DO UPDATE SET
                            sleep_seconds = EXCLUDED.sleep_seconds,
                            sleep_score = EXCLUDED.sleep_score,
                            deep_sleep = EXCLUDED.deep_sleep,
                            rem_sleep = EXCLUDED.rem_sleep,
                            resting_hr = EXCLUDED.resting_hr,
                            avg_hrv = EXCLUDED.avg_hrv,
                            stress_avg = EXCLUDED.stress_avg,
                            body_battery = EXCLUDED.body_battery,
                            vo2max_run = EXCLUDED.vo2max_run,
                            recovery_time = EXCLUDED.recovery_time,
                            training_status = EXCLUDED.training_status,
                            acute_load = EXCLUDED.acute_load,
                            chronic_load = EXCLUDED.chronic_load,
                            weight = EXCLUDED.weight,
                            body_fat = EXCLUDED.body_fat,
                            muscle_mass = EXCLUDED.muscle_mass
                    """, (
                        current,
                        sleep_seconds,
                        sleep_score,
                        deep_sleep,
                        rem_sleep,
                        resting_hr,
                        avg_hrv,
                        stress_avg,
                        body_battery,
                        vo2max_run,
                        recovery_time,
                        training_status,
                        acute_load,
                        chronic_load,
                        weight,
                        body_fat,
                        muscle_mass
                    ))

                    total_days += 1

                except Exception as e:
                    return {
                        "error_on_date": str(current),
                        "error_message": str(e)
                    }

                time.sleep(0.4)
                current += timedelta(days=1)

    return {
        "days_processed": total_days,
        "errors": errors
    }
