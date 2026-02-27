from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import os
import requests
import time
import psycopg
from datetime import datetime, timedelta, date
from garminconnect import Garmin

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

            # ACTIVITIES
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

init_db()

# ---------------------------
# DB MIGRATION
# ---------------------------

@app.get("/migrate-db")
def migrate_db():

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                ALTER TABLE garmin_daily_metrics
                ADD COLUMN IF NOT EXISTS vo2max_run DOUBLE PRECISION
            """)

            cur.execute("""
                ALTER TABLE garmin_daily_metrics
                ADD COLUMN IF NOT EXISTS weight DOUBLE PRECISION
            """)

    return {"status": "migration done"}

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

# ---------------------------
# DAILY REPORT
# ---------------------------
@app.get("/daily-report")
def daily_report():

    sport_factors = {
        "Run": 1.2,
        "Ride": 1.0,
        "VirtualRide": 1.0,
        "GravelRide": 1.0,
        "MountainBikeRide": 1.0,
        "Swim": 1.3
    }

    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            # -------- VČEREJŠÍ AKTIVITY --------
            cur.execute("""
                SELECT sport_type, duration, name
                FROM activities
                WHERE DATE(start_date) = %s
            """, (yesterday,))
            rows = cur.fetchall()

            yesterday_activities = []
            yesterday_load = 0

            for sport, duration, name in rows:
                hours = duration / 3600
                factor = sport_factors.get(sport, 0.7)
                load = hours * factor

                yesterday_load += load

                yesterday_activities.append({
                    "name": name,
                    "sport": sport,
                    "duration_min": round(duration / 60, 1),
                    "load": round(load, 2)
                })

            # -------- ATL / CTL --------
            cur.execute("""
                SELECT sport_type, duration, start_date
                FROM activities
                ORDER BY start_date
            """)
            all_rows = cur.fetchall()

    # výpočet daily load
    daily_load = {}

    for sport, duration, date in all_rows:
        hours = duration / 3600
        factor = sport_factors.get(sport, 0.7)
        load = hours * factor
        day = date.date()

        if day not in daily_load:
            daily_load[day] = 0
        daily_load[day] += load

    sorted_days = sorted(daily_load.keys())

    ATL_DAYS = 7
    CTL_DAYS = 42

    atl_values = []
    ctl_values = []

    for i in range(len(sorted_days)):
        recent_7 = sorted_days[max(0, i-ATL_DAYS+1):i+1]
        recent_42 = sorted_days[max(0, i-CTL_DAYS+1):i+1]

        atl = sum(daily_load[d] for d in recent_7) / ATL_DAYS
        ctl = sum(daily_load[d] for d in recent_42) / CTL_DAYS

        atl_values.append(atl)
        ctl_values.append(ctl)

    current_atl = round(atl_values[-1], 2) if atl_values else 0
    current_ctl = round(ctl_values[-1], 2) if ctl_values else 0
    form = round(current_ctl - current_atl, 2)

    # -------- TÝDENNÍ LOAD --------
    week_start = today - timedelta(days=today.weekday())
    prev_week_start = week_start - timedelta(days=7)

    current_week_load = sum(
        v for d, v in daily_load.items()
        if d >= week_start
    )

    previous_week_load = sum(
        v for d, v in daily_load.items()
        if prev_week_start <= d < week_start
    )

    change_pct = 0
    if previous_week_load > 0:
        change_pct = round(
            ((current_week_load - previous_week_load) / previous_week_load) * 100,
            1
        )

    return {
        "date": str(yesterday),
        "yesterday_activities": yesterday_activities,
        "yesterday_load": round(yesterday_load, 2),
        "ATL_7d": current_atl,
        "CTL_42d": current_ctl,
        "form": form,
        "current_week_load": round(current_week_load, 2),
        "previous_week_load": round(previous_week_load, 2),
        "week_change_pct": change_pct
    }

# ---------------------------
# GARMIN SYNC
# ---------------------------

@app.get("/garmin-sync")
def garmin_sync():

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    today = date.today()
    yesterday = today - timedelta(days=1)

    try:
        api = Garmin(email, password)
        api.login()

        sleep = api.get_sleep_data(yesterday.isoformat())
        rhr = api.get_rhr_day(yesterday.isoformat())
        hrv = api.get_hrv_data(yesterday.isoformat())
        body = api.get_body_battery(yesterday.isoformat())
        stress = api.get_stress_data(yesterday.isoformat())

         # ---- SAFE EXTRACTION ----
        
        sleep_seconds = None
        if isinstance(sleep, dict):
            sleep_seconds = sleep.get("dailySleepDTO", {}).get("sleepTimeSeconds")
        
        resting_hr = None
        if isinstance(rhr, dict):
            resting_hr = rhr.get("restingHeartRate")
        
        avg_hrv = None
        if isinstance(hrv, dict):
            avg_hrv = hrv.get("hrvSummary", {}).get("lastNightAvg")
        
        body_battery = None
        if isinstance(body, dict):
            bb = body.get("bodyBattery")
            if isinstance(bb, list) and bb:
                body_battery = bb[-1].get("bodyBatteryLevel")
        
        stress_avg = None
        if isinstance(stress, dict):
            stress_avg = stress.get("overallStressLevel")
    
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO garmin_daily_metrics
                    (date, sleep_seconds, resting_hr, avg_hrv, body_battery, stress_avg)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date) DO UPDATE SET
                        sleep_seconds = EXCLUDED.sleep_seconds,
                        resting_hr = EXCLUDED.resting_hr,
                        avg_hrv = EXCLUDED.avg_hrv,
                        body_battery = EXCLUDED.body_battery,
                        stress_avg = EXCLUDED.stress_avg
                """, (
                    yesterday,
                    sleep_seconds,
                    resting_hr,
                    avg_hrv,
                    body_battery,
                    stress_avg
                ))

        return {
            "date": str(yesterday),
            "sleep_hours": round(sleep_seconds / 3600, 2) if sleep_seconds else None,
            "resting_hr": resting_hr,
            "avg_hrv": avg_hrv,
            "body_battery": body_battery,
            "stress_avg": stress_avg
        }

    except Exception as e:
        return {"error": str(e)}

# ---------------------------
# GARMIN FULL SYNC
# ---------------------------

@app.get("/garmin-full-sync")
def garmin_full_sync():

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    today = date.today()
    yesterday = today - timedelta(days=1)

    try:
        api = Garmin(email, password)
        api.login()

        # ---- DATA FETCH ----
        sleep_data = api.get_sleep_data(yesterday.isoformat())
        stats = api.get_stats(yesterday.isoformat())
        hrv = api.get_hrv_data(yesterday.isoformat())

        # ---- SLEEP ----
        sleep_seconds = None
        if isinstance(sleep_data, dict):
            sleep_seconds = sleep_data.get("dailySleepDTO", {}).get("sleepTimeSeconds")

        # ---- STATS ----
        resting_hr = None
        body_battery = None
        stress_avg = None
        vo2max_run = None

        if isinstance(stats, dict):
            resting_hr = stats.get("restingHeartRate")
            body_battery = stats.get("bodyBatteryAverage")
            stress_avg = stats.get("averageStressLevel")
            vo2max_run = stats.get("vo2MaxValue")

        # ---- HRV ----
        avg_hrv = None
        if isinstance(hrv, dict):
            avg_hrv = hrv.get("hrvSummary", {}).get("lastNightAvg")

        # ---- WEIGHT ----
        weight = None
        try:
            body = api.get_body_composition(
                yesterday.isoformat(),
                yesterday.isoformat()
            )
            if isinstance(body, list) and body:
                weight = body[0].get("weight")
        except:
            pass

        # ---- DB UPSERT ----
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO garmin_daily_metrics
                    (date, sleep_seconds, resting_hr, avg_hrv, body_battery,
                     stress_avg, vo2max_run, weight)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date) DO UPDATE SET
                        sleep_seconds = EXCLUDED.sleep_seconds,
                        resting_hr = EXCLUDED.resting_hr,
                        avg_hrv = EXCLUDED.avg_hrv,
                        body_battery = EXCLUDED.body_battery,
                        stress_avg = EXCLUDED.stress_avg,
                        vo2max_run = EXCLUDED.vo2max_run,
                        weight = EXCLUDED.weight
                """, (
                    yesterday,
                    sleep_seconds,
                    resting_hr,
                    avg_hrv,
                    body_battery,
                    stress_avg,
                    vo2max_run,
                    weight
                ))

        return {
            "date": str(yesterday),
            "sleep_h": round(sleep_seconds / 3600, 2) if sleep_seconds else None,
            "rhr": resting_hr,
            "hrv": avg_hrv,
            "body_battery": body_battery,
            "stress_avg": stress_avg,
            "vo2_run": vo2max_run,
            "weight": weight
        }

    except Exception as e:
        return {"error": str(e)}

# ---------------------------
# READINESS SCORE
# ---------------------------

@app.get("/readiness")
def readiness_score():

    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            # posledních 7 dní Garmin dat
            cur.execute("""
                SELECT sleep_seconds, resting_hr, avg_hrv, stress_avg
                FROM garmin_daily_metrics
                WHERE date >= %s
                ORDER BY date
            """, (yesterday - timedelta(days=7),))

            rows = cur.fetchall()

    if not rows:
        return {"error": "No Garmin data"}

    sleeps = []
    rhrs = []
    hrvs = []
    stress_vals = []

    for sleep, rhr, hrv, stress in rows:
        if sleep:
            sleeps.append(sleep / 3600)
        if rhr:
            rhrs.append(rhr)
        if hrv:
            hrvs.append(hrv)
        if stress:
            stress_vals.append(stress)

    score = 70

    # ---- Sleep ----
    if sleeps:
        last_sleep = sleeps[-1]
        if last_sleep >= 7.5:
            score += 10
        elif last_sleep >= 6:
            score += 5
        else:
            score -= 10

    # ---- HRV ----
    if len(hrvs) >= 3:
        avg_hrv = sum(hrvs[:-1]) / max(1, len(hrvs[:-1]))
        last_hrv = hrvs[-1]
        if last_hrv > avg_hrv * 1.05:
            score += 10
        elif last_hrv < avg_hrv * 0.95:
            score -= 10

    # ---- RHR ----
    if len(rhrs) >= 3:
        avg_rhr = sum(rhrs[:-1]) / max(1, len(rhrs[:-1]))
        last_rhr = rhrs[-1]
        if last_rhr < avg_rhr:
            score += 5
        elif last_rhr > avg_rhr + 3:
            score -= 10

    # ---- Stress ----
    if stress_vals:
        last_stress = stress_vals[-1]
        if last_stress < 25:
            score += 5
        elif last_stress > 35:
            score -= 10

    score = max(0, min(100, score))

    # ---- Recommendation ----
    if score >= 85:
        recommendation = "Hard intervals OK"
    elif score >= 70:
        recommendation = "Quality training"
    elif score >= 50:
        recommendation = "Moderate / tempo"
    else:
        recommendation = "Recovery / easy day"

    return {
        "date": str(yesterday),
        "readiness_score": score,
        "recommendation": recommendation
    }

# ---------------------------
# AI DAILY + WEEKLY REPORT
# ---------------------------

@app.get("/generate-ai-report")
def generate_ai_report():

    import requests
    import openai
    import smtplib
    from email.mime.text import MIMEText

    openai.api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("BASE_URL")

    # ---- fetch data ----
    daily = requests.get(f"{base_url}/daily-report").json()
    readiness = requests.get(f"{base_url}/readiness").json()
    weekly = requests.get(f"{base_url}/weekly-load").json()

    prompt = f"""
You are an experienced triathlon coach.

Daily data:
Yesterday load: {daily.get("yesterday_load")}
ATL: {daily.get("ATL_7d")}
CTL: {daily.get("CTL_42d")}
Form: {daily.get("form")}
Week change %: {daily.get("week_change_pct")}

Readiness score: {readiness.get("readiness_score")}
Recommendation: {readiness.get("recommendation")}

Weekly loads:
{weekly}

Give:
- Comment on yesterday
- Fatigue evaluation
- Recommendation for today
- Short weekly summary
"""

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional endurance coach."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
    )

    ai_text = response["choices"][0]["message"]["content"]

    # ---------------------------
    # EMAIL SEND SECTION  ← TADY
    # ---------------------------

    msg = MIMEText(ai_text)
    msg["Subject"] = "Daily AI Tri Coach Report"
    msg["From"] = os.getenv("EMAIL_FROM")
    msg["To"] = os.getenv("EMAIL_TO")

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(
            os.getenv("EMAIL_FROM"),
            os.getenv("EMAIL_PASSWORD")
        )
        server.send_message(msg)

    # ---- return for manual testing ----
    return {
        "date": daily.get("date"),
        "ai_report": ai_text
    }

# ---------------------------
# COACH EXPORT (FULL LIVE SYNC)
# ---------------------------

@app.get("/coach-export")
def coach_export():

    import requests

    base_url = os.getenv("BASE_URL")

    result = {}

    # ---- 1️⃣ STRAVA SYNC ----
    try:
        sync_res = requests.get(f"{base_url}/sync", timeout=60).json()
        result["strava_sync"] = sync_res
    except Exception as e:
        result["strava_sync_error"] = str(e)

    # ---- 2️⃣ GARMIN SYNC ----
    try:
        garmin_res = requests.get(f"{base_url}/garmin-full-sync", timeout=60).json()
        result["garmin_sync"] = garmin_res
    except Exception as e:
        result["garmin_sync_error"] = str(e)

    # ---- 3️⃣ FETCH ANALYTICS ----
    try:
        daily = requests.get(f"{base_url}/daily-report").json()
        readiness = requests.get(f"{base_url}/readiness").json()
        weekly = requests.get(f"{base_url}/weekly-load").json()
        load = requests.get(f"{base_url}/load").json()

        result["daily_report"] = daily
        result["readiness"] = readiness
        result["load_status"] = load
        result["weekly_load"] = weekly

    except Exception as e:
        result["analytics_error"] = str(e)

    return result

# ---------------------------
# PERFORMANCE EXPORT (30 DAYS HISTORY)
# ---------------------------

@app.get("/performance-export")
def performance_export():

    from datetime import date, timedelta
    import psycopg

    today = date.today()
    start_date = today - timedelta(days=30)

    result = {}

    sport_factors = {
        "Run": 1.2,
        "Ride": 1.0,
        "VirtualRide": 1.0,
        "GravelRide": 1.0,
        "MountainBikeRide": 1.0,
        "Swim": 1.3
    }

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            # 1️⃣ Activities last 30 days
            cur.execute("""
                SELECT sport_type, duration, start_date
                FROM activities
                WHERE start_date >= %s
                ORDER BY start_date
            """, (start_date,))
            activities = cur.fetchall()

            # 2️⃣ Garmin metrics last 30 days
            cur.execute("""
                SELECT date, sleep_seconds, resting_hr, avg_hrv
                FROM garmin_daily_metrics
                WHERE date >= %s
                ORDER BY date
            """, (start_date,))
            garmin = cur.fetchall()

    # ---- DAILY LOAD CALC ----
    daily_load = {}

    for sport, duration, dt in activities:
        day = dt.date()
        hours = duration / 3600
        factor = sport_factors.get(sport, 0.7)
        load = hours * factor

        if day not in daily_load:
            daily_load[day] = 0
        daily_load[day] += load

    # fill empty days
    current = start_date
    while current <= today:
        if current not in daily_load:
            daily_load[current] = 0
        current += timedelta(days=1)

    sorted_days = sorted(daily_load.keys())

    # ---- ATL / CTL TREND ----
    ATL_DAYS = 7
    CTL_DAYS = 42

    atl_trend = []
    ctl_trend = []

    for i in range(len(sorted_days)):
        recent_7 = sorted_days[max(0, i-ATL_DAYS+1):i+1]
        recent_42 = sorted_days[max(0, i-CTL_DAYS+1):i+1]

        atl = sum(daily_load[d] for d in recent_7) / ATL_DAYS
        ctl = sum(daily_load[d] for d in recent_42) / CTL_DAYS

        atl_trend.append({
            "date": str(sorted_days[i]),
            "atl": round(atl, 2)
        })

        ctl_trend.append({
            "date": str(sorted_days[i]),
            "ctl": round(ctl, 2)
        })

    # ---- FORMAT OUTPUT ----

    result["daily_load_30d"] = [
        {"date": str(d), "load": round(daily_load[d], 2)}
        for d in sorted_days
    ]

    result["atl_trend_30d"] = atl_trend
    result["ctl_trend_30d"] = ctl_trend

    result["garmin_30d"] = [
        {
            "date": str(d),
            "sleep_h": round(s/3600, 2) if s else None,
            "rhr": r,
            "hrv": h
        }
        for d, s, r, h in garmin
    ]

    return result
