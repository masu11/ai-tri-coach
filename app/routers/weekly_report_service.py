from datetime import date, timedelta
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Activity, GarminDailyMetrics


def get_weekly_report():
    db = SessionLocal()

    today = date.today()
    start_7 = today - timedelta(days=7)
    start_28 = today - timedelta(days=28)

    # ---------- LOAD ----------
    weekly_tss = db.query(
        func.coalesce(func.sum(Activity.tss), 0)
    ).filter(Activity.start_date >= start_7).scalar()

    acute_load = weekly_tss

    chronic_load = db.query(
        func.coalesce(func.sum(Activity.tss), 0)
    ).filter(Activity.start_date >= start_28).scalar() / 4

    load_ratio = (
        acute_load / chronic_load if chronic_load > 0 else 0
    )

    # ---------- GARMIN ----------
    weekly_garmin = db.query(
        func.avg(GarminDailyMetrics.avg_hrv),
        func.avg(GarminDailyMetrics.resting_hr),
        func.avg(GarminDailyMetrics.sleep_score),
        func.avg(GarminDailyMetrics.sleep_seconds),
        func.avg(GarminDailyMetrics.body_battery),
        func.avg(GarminDailyMetrics.stress_avg)
    ).filter(
        GarminDailyMetrics.date >= start_7
    ).first()

    hrv_avg, rhr_avg, sleep_score_avg, sleep_sec_avg, bb_avg, stress_avg = weekly_garmin

    baseline_hrv = db.query(
        func.avg(GarminDailyMetrics.avg_hrv)
    ).filter(
        GarminDailyMetrics.date >= start_28
    ).scalar()

    baseline_rhr = db.query(
        func.avg(GarminDailyMetrics.resting_hr)
    ).filter(
        GarminDailyMetrics.date >= start_28
    ).scalar()

    hrv_delta_pct = (
        ((hrv_avg - baseline_hrv) / baseline_hrv) * 100
        if baseline_hrv else 0
    )

    sleep_hours = sleep_sec_avg / 3600 if sleep_sec_avg else 0

    # ---------- READINESS ----------
    readiness_score = calculate_readiness(
        hrv_delta_pct,
        rhr_avg,
        baseline_rhr,
        sleep_score_avg,
        bb_avg,
        load_ratio
    )

    color = get_color(readiness_score)

    return {
        "period": f"{start_7} → {today}",
        "weekly_tss": round(weekly_tss, 1),
        "acute_load": round(acute_load, 1),
        "chronic_load": round(chronic_load, 1),
        "load_ratio": round(load_ratio, 2),
        "hrv_avg": round(hrv_avg or 0, 1),
        "hrv_baseline_28d": round(baseline_hrv or 0, 1),
        "hrv_delta_pct": round(hrv_delta_pct, 1),
        "resting_hr_avg": round(rhr_avg or 0, 1),
        "resting_hr_baseline_28d": round(baseline_rhr or 0, 1),
        "sleep_avg_score": round(sleep_score_avg or 0, 1),
        "sleep_avg_hours": round(sleep_hours, 2),
        "body_battery_avg": round(bb_avg or 0, 1),
        "stress_avg": round(stress_avg or 0, 1),
        "readiness_score": readiness_score,
        "color_status": color
    }
