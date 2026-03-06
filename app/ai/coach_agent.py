from app.ai.metrics_builder import get_last_runs, get_last7_tss
from app.ai.recovery_model import get_latest_recovery
from app.ai.performance_model import detect_performance_trend
from app.ai.plan_generator import generate_plan

def run_ai_coach():

    runs = get_last_runs()

    trend = detect_performance_trend(runs)

    recovery = get_latest_recovery()

    tss7 = get_last7_tss()

    total_tss = sum(r["tss"] for r in tss7) if tss7 else 0

    if recovery < 2:
        recommendation = "Recovery training recommended"

    elif total_tss > 500:
        recommendation = "High load week → easy training"

    elif trend == "improving":
        recommendation = "Good progress → keep intensity"

    else:
        recommendation = "Normal endurance training"

    plan = generate_plan(recommendation)

    return {
        "trend": trend,
        "recovery_score": recovery,
        "tss7": total_tss,
        "recommendation": recommendation,
        "plan": plan
    }
