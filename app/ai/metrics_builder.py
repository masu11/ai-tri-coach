from app.database import db

def get_last_runs():
    rows = db.fetch_all("""
    SELECT
    distance,
    duration,
    average_heartrate AS hr
FROM activities
WHERE duration BETWEEN 300 AND 28800
ORDER BY start_date DESC
LIMIT 20
    """)
    return rows

def get_last7_tss():
    rows = db.fetch_all("""
    SELECT
    sport_type,
    DATE(start_date) AS day,
    COUNT(*) AS activities,
    SUM(distance) AS distance,
    SUM(moving_time) AS duration,
    SUM(tss) AS tss
FROM activities
WHERE duration BETWEEN 300 AND 28800
AND start_date > NOW() - INTERVAL '7 days'
GROUP BY sport_type, day
ORDER BY day
    """)
    return rows
