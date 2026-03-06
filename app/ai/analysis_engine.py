import os
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

RECOVERY:
Sleep score: {data.get("sleep")}
HRV: {data.get("hrv")}
Body battery: {data.get("battery")}
Stress: {data.get("stress")}

Napiš krátké hodnocení:

1) zhodnoť včerejší trénink
2) zhodnoť posledních 7 dní
3) zhodnoť recovery
4) dej krátké doporučení

max 8 vět
česky
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    return response.choices[0].message.content