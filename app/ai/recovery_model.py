from app.database import db

def get_latest_recovery():

    row = db.fetch_one("""
    SELECT
        sleep_score,
        avg_hrv,
        resting_hr,
        body_battery,
        stress_avg
    FROM garmin_daily_metrics
    ORDER BY date DESC
    LIMIT 1
    """)

    if not row:
        return 0

    score = 0

    if row.get("sleep_score", 0) > 75:
        score += 1

    if row.get("avg_hrv", 0) > 60:
        score += 1

    if row.get("body_battery", 0) > 60:
        score += 1

    if row.get("stress_avg", 100) < 30:
        score += 1

    return score
