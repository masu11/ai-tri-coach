import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_ai_analysis(data):

    prompt = f"""
Jsi triatlonový trenér.

Analyzuj tréninková data.

VČERA:
{data.get("yesterday")}

POSLEDNÍCH 7 DNÍ:
{data.get("weekly")}

POSLEDNÍCH 30 DNÍ:
{data.get("monthly")}

RECOVERY:
Sleep score: {data.get("sleep")}
HRV: {data.get("hrv")}
Body battery: {data.get("battery")}
Stress: {data.get("stress")}

Vrať výstup POUZE jako JSON objekt se strukturou:
{{
  "yesterday": "krátké hodnocení včerejška",
  "week": "krátké hodnocení posledních 7 dní",
  "month": "krátké hodnocení posledních 30 dní",
  "recovery": "zhodnocení recovery + krátké doporučení"
}}

Každé pole max 2 krátké věty. Česky.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.4
    )

    content = response.choices[0].message.content or "{}"

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {
            "yesterday": "AI hodnocení se nepodařilo vygenerovat.",
            "week": "AI hodnocení se nepodařilo vygenerovat.",
            "month": "AI hodnocení se nepodařilo vygenerovat.",
            "recovery": "AI hodnocení se nepodařilo vygenerovat."
        }

    return {
        "yesterday": parsed.get("yesterday", ""),
        "week": parsed.get("week", ""),
        "month": parsed.get("month", ""),
        "recovery": parsed.get("recovery", "")
    }
