# FTP constants

FTP_BIKE = 210
FTP_RUN = 400

THRESHOLD_HR_BIKE = 165
THRESHOLD_HR_RUN = 170


def tss_from_power(duration, power, ftp):

    if not power or not ftp:
        return None

    intensity = power / ftp

    tss = duration * power * intensity / (ftp * 3600) * 100

    return round(tss, 1)


def tss_from_hr(duration, avg_hr, threshold_hr):

    if not avg_hr or not threshold_hr:
        return None

    hours = duration / 3600

    intensity = avg_hr / threshold_hr

    tss = hours * intensity * intensity * 100

    return round(tss, 1)


def tss_from_duration(duration):

    hours = duration / 3600

    return round(hours * 50, 1)


def compute_tss(activity):

    duration = activity.get("duration")
    sport = activity.get("sport_type")

    power = (
        activity.get("weighted_average_watts")
        or activity.get("avg_power")
    )

    avg_hr = activity.get("avg_hr")

    if sport == "cycling":

        ftp = FTP_BIKE
        threshold_hr = THRESHOLD_HR_BIKE

    elif sport == "running":

        ftp = FTP_RUN
        threshold_hr = THRESHOLD_HR_RUN

    else:

        ftp = None
        threshold_hr = THRESHOLD_HR_RUN

    if power:

        tss = tss_from_power(duration, power, ftp)

        if tss:
            return tss, "power"

    if avg_hr:

        tss = tss_from_hr(duration, avg_hr, threshold_hr)

        if tss:
            return tss, "hr"

    tss = tss_from_duration(duration)

    return tss, "duration"
