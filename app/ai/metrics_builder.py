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

def get_last30_summary():

    rows = db.fetch_all("""
    SELECT
        DATE(start_date) as day,
        SUM(tss) as tss
    FROM activities
    WHERE start_date > NOW() - INTERVAL '30 days'
    GROUP BY day
    ORDER BY day
    """)

    return rows    

def get_last7_summary_by_day():

    rows = db.fetch_all("""
    SELECT
        DATE(start_date) as day,
        SUM(tss) as tss
    FROM activities
    WHERE start_date > NOW() - INTERVAL '7 days'
    GROUP BY day
    ORDER BY day
    """)

    return rows
