def generate_plan(recommendation):

    if "Recovery" in recommendation or "easy" in recommendation:
        return [
            "Mon easy run",
            "Tue easy swim",
            "Wed bike endurance",
            "Thu easy run",
            "Fri rest",
            "Sat long ride",
            "Sun recovery jog"
        ]

    if "intensity" in recommendation or "progress" in recommendation:
        return [
            "Mon recovery",
            "Tue bike intervals",
            "Wed swim endurance",
            "Thu run tempo",
            "Fri recovery",
            "Sat long ride",
            "Sun brick workout"
        ]

    return [
        "Mon easy run",
        "Tue bike endurance",
        "Wed swim",
        "Thu run tempo",
        "Fri recovery",
        "Sat long ride",
        "Sun easy run"
    ]
