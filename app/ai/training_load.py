ATL_WINDOW = 7
CTL_WINDOW = 42

def compute_training_load(daily_tss):

    atl = 0
    ctl = 0

    for day in daily_tss:
        tss = day["tss"]

        atl = atl + (tss - atl) / ATL_WINDOW
        ctl = ctl + (tss - ctl) / CTL_WINDOW

    tsb = ctl - atl

    return {
        "ATL": atl,
        "CTL": ctl,
        "TSB": tsb
    }
