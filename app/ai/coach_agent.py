from app.ai.metrics_builder import get_last_runs, get_last7_tss
from app.ai.recovery_model import get_latest_recovery
from app.ai.performance_model import detect_performance_trend
from app.ai.plan_generator import generate_plan
from app.ai.report_generator import create_and_send_report


def run_ai_coach():

    runs = get_last_runs()

    trend = detect_performance_trend(runs)

    recovery = get_latest_recovery()

    tss7 = get_last7_tss()

    total_tss = sum(r["tss"] for r in tss7) if tss7 else 0


    # doporučení trenéra
    if recovery < 2:
        recommendation = "Doporučen regenerační trénink"

    elif total_tss > 500:
        recommendation = "Vysoká zátěž → lehčí trénink"

    elif trend == "improving":
        recommendation = "Dobrá forma → kvalitní trénink"

    else:
        recommendation = "Normální vytrvalostní trénink"


    plan = generate_plan(recommendation)


    # -----------------------
    # DATA PRO REPORT
    # -----------------------

    data = {
        "yesterday": [],
        "weekly": [],

        "sleep": 80,
        "hrv": 65,
        "battery": 70,
        "stress": 25,

        "recommendation": recommendation,

        "plan": plan
    }


   import os

email_config = {
    "to": os.getenv("EMAIL_TO"),
    "user": os.getenv("EMAIL_FROM"),
    "password": os.getenv("EMAIL_PASSWORD")
}


    # odeslání reportu
    create_and_send_report(data, email_config)


    return {
        "trend": trend,
        "recovery_score": recovery,
        "tss7": total_tss,
        "recommendation": recommendation,
        "plan": plan
    }
