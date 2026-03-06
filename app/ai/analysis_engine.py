import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_ai_analysis(data):

    prompt = f"""
Jsi triatlonový trenér.

Analyzuj trénink.

DATA:

Včera:
{data["yesterday"]}

Posledních 7 dní:
{data["weekly"]}

Recovery:
Sleep score: {data["sleep"]}
HRV: {data["hrv"]}
Body battery: {data["battery"]}
Stress: {data["stress"]}

Vytvoř stručné hodnocení:

1) zhodnoť včerejší trénink
2) zhodnoť posledních 7 dní
3) zhodnoť recovery
4) napiš doporučení

max 8 vět
česky
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    return response.choices[0].message.content
