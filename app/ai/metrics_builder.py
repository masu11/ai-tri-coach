from app.database import db


def get_last7_summary():

    rows = db.fetch_all("""
        SELECT
            sport_type AS sport,
            COUNT(*) AS count,
            SUM(distance) AS distance,
            SUM(tss) AS tss
        FROM activities
        WHERE start_date > NOW() - INTERVAL '7 days'
        AND duration BETWEEN 300 AND 28800
        GROUP BY sport_type
        ORDER BY sport_type
    """)

    return rows



def get_last30_summary():

    rows = db.fetch_all("""
        SELECT
            DATE(start_date) AS day,
            SUM(tss) AS tss
        FROM activities
        WHERE start_date > NOW() - INTERVAL '30 days'
        AND duration BETWEEN 300 AND 28800        
        GROUP BY day
        ORDER BY day
    """)

    return rows



def get_yesterday_activities():

    rows = db.fetch_all("""
        SELECT
            sport_type AS sport,
            distance,
            duration,
            tss
        FROM activities
        WHERE DATE(start_date) = CURRENT_DATE - INTERVAL '1 day'
        AND duration BETWEEN 300 AND 28800        
        ORDER BY start_date
    """)

    return rows