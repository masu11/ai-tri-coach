from app.database import db


def get_last_activities():

    rows = db.fetch_all("""
    SELECT
        sport_type,
        distance,
        duration,
        avg_hr,
        avg_power,
        tss
    FROM activities
    WHERE duration BETWEEN 300 AND 28800
    ORDER BY start_date DESC
    LIMIT 30
    """)

    return rows

def get_last7_summary():

    rows = db.fetch_all("""
    SELECT
        sport_type,
        COUNT(*) as activities,
        SUM(distance) as distance,
        SUM(duration) as duration,
        SUM(tss) as tss
    FROM activities
    WHERE start_date > NOW() - INTERVAL '7 days'
    AND duration BETWEEN 300 AND 28800
    GROUP BY sport_type
    """)

    return rows
