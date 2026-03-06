from app.database import db
from app.database import engine


def get_last7_daily_tss():

    with engine.connect() as conn:

        result = conn.execute("""
            SELECT
                DATE(start_date) as day,
                SUM(tss) as tss
            FROM activities
            WHERE start_date > NOW() - INTERVAL '7 days'
            AND duration BETWEEN 300 AND 28800
            GROUP BY DATE(start_date)
            ORDER BY day
        """)

        rows = result.fetchall()

    data = []

    for r in rows:
        data.append({
            "day": str(r[0]),
            "tss": float(r[1] or 0)
        })

    return data


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
            sport_type AS sport,
            COUNT(*) AS count,
            SUM(distance) AS distance,
            SUM(tss) AS tss
        FROM activities
        WHERE start_date > NOW() - INTERVAL '30 days'
        AND duration BETWEEN 300 AND 28800
        GROUP BY sport_type
        ORDER BY sport_type
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