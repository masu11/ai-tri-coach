from app.database import db

def get_latest_recovery():

    row = db.fetch_one("""
    SELECT
        sleep_score,
        avg_hrv,
        body_battery,
        stress_avg
    FROM garmin_daily_metrics
    ORDER BY date DESC
    LIMIT 1
    """)

    return row or {}