import os

from app.ai.metrics_builder import (
    get_last_activities,
    get_last7_summary,
    get_last30_summary,
    get_last7_summary_by_day
)
from app.ai.recovery_model import get_latest_recovery
from app.ai.plan_generator import generate_plan
from app.ai.report_generator import create_and_send_report
from app.ai.analysis_engine import generate_ai_analysis


def run_ai_coach():

    # poslední aktivity
    activities = get_last_activities()

    # souhrn posledních 7 dní
    weekly_summary = get_last7_summary()

    total_tss = sum((r.get("tss") or 0) for r in weekly_summary) if weekly_summary else 0


    # recovery data z Garminu
    recovery = get_latest_recovery()

    sleep_score = recovery.get("sleep_score", 0)
    hrv = recovery.get("avg_hrv", 0)
    body_battery = recovery.get("body_battery", 0)
    stress = recovery.get("stress_avg", 0)


    # rozhodování AI trenéra
    if sleep_score < 60 or body_battery < 40:
        recommendation = "Nízká regenerace → doporučen lehký trénink"

    elif total_tss > 600:
        recommendation = "Velká tréninková zátěž → doporučen recovery den"

    elif total_tss < 250:
        recommendation = "Nízký tréninkový objem → doporučen kvalitní trénink"

    else:
        recommendation = "Optimální tréninková zátěž"




    # včerejší aktivity
    yesterday_rows = []

    if activities:

        last = activities[0]

        yesterday_rows.append({
            "sport": last.get("sport_type"),
            "distance": round((last.get("distance") or 0) / 1000, 2),
            "duration": round((last.get("duration") or 0) / 60, 1),
            "tss": last.get("tss")
        })


    # weekly rows pro report
    weekly_rows = []

    for r in weekly_summary:

        weekly_rows.append({
            "sport": r["sport_type"],
            "count": r["activities"],
            "distance": round((r["distance"] or 0) / 1000, 2),
            "tss": r["tss"]
        })


    # data pro HTML report
    last30 = get_last30_summary()
    last7_daily = get_last7_summary_by_day()

    data = {
        "yesterday": yesterday_rows,
        "weekly": weekly_rows,
        "last30": last30,
        "last7_daily": last7_daily,
        "sleep": sleep_score,
        "hrv": hrv,
        "battery": body_battery,
        "stress": stress,
        "recommendation": recommendation,
    }

    analysis = generate_ai_analysis(data)

    data["analysis_yesterday"] = analysis["yesterday"]
    data["analysis_week"] = analysis["week"]
    data["analysis_month"] = analysis["month"]

    data["analysis"] = analysis
    data["load_status"] = training_light(total_tss, sleep_score)

    email_config = {
        "to": os.getenv("EMAIL_TO")
    }



    # odeslání reportu
    create_and_send_report(data, email_config)


    return {
        "weekly_tss": total_tss,
        "sleep": sleep_score,
        "hrv": hrv,
        "body_battery": body_battery,
        "recommendation": recommendation,
        "plan": plan
    }

def training_light(total_tss, sleep_score):

    if sleep_score < 60 or total_tss > 700:
        return "🔴 Přetížení"

    if total_tss > 450:
        return "🟡 Zvýšená zátěž"

    return "🟢 Optimální zátěž"