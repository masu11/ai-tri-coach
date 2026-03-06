from statistics import mean

def compute_run_efficiency(runs):
    efficiency_scores = []

    for r in runs:
        if r.get("hr") and r.get("distance") and r["distance"] > 0:
            pace = r["duration"] / r["distance"]  # sec per meter
            efficiency = pace * r["hr"]
            efficiency_scores.append(efficiency)

    if not efficiency_scores:
        return None

    return mean(efficiency_scores)


def detect_performance_trend(last_runs):

    if len(last_runs) < 4:
        return "unknown"

    first = compute_run_efficiency(last_runs[:3])
    last = compute_run_efficiency(last_runs[-3:])

    if first is None or last is None:
        return "unknown"

    if last < first * 0.97:
        return "improving"

    if last > first * 1.03:
        return "declining"

    return "stable"
