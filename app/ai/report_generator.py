
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os
import resend
from app.ai.chart_builder import tss_chart

def build_table_rows(rows, columns):

    html = ""

    for r in rows:

        html += "<tr>"

        for c in columns:

            value = r.get(c, "")

            if c == "tss" and value != "":
            value = round(float(value), 2)

            html += f"<td>{value}</td>"

        html += "</tr>"

    return html

def build_plan_rows(plan):

    html = ""

    for p in plan:

        if isinstance(p, dict):

            day = p.get("day", "")
            training = p.get("training", "")

        else:

            day = ""
            training = str(p)

        html += f"<tr><td>{day}</td><td>{training}</td></tr>"

    return html




def generate_html_report(data):

    yesterday_rows = build_table_rows(
        data.get("yesterday", []),
        ["sport", "distance", "duration", "tss"]
    )

    weekly_rows = build_table_rows(
        data.get("weekly", []),
        ["sport", "count", "distance", "tss"]
    )

    plan_rows = build_plan_rows(data.get("plan", []))

    chart7 = tss_chart(data.get("last7_daily", []))
    chart30 = tss_chart(data.get("last30", []))

    html = f"""
        <h2>Včera</h2>

    <table style="border-collapse:collapse;width:100%">
    <tr>
    <th>Sport</th>
    <th>Vzdálenost</th>
    <th>Čas</th>
    <th>TSS</th>
    </tr>

    {yesterday_rows}

    </table>

    <h3>AI hodnocení</h3>

    <p style="white-space: pre-line">
    {data.get("analysis_yesterday","")}
    </p>


    <h2>Posledních 7 dní</h2>

    <img src="data:image/png;base64,{chart7}" />

    <table style="border-collapse:collapse;width:100%">
    <tr>
    <th>Sport</th>
    <th>Počet</th>
    <th>Vzdálenost</th>
    <th>TSS</th>
    </tr>

    {weekly_rows}

    </table>

    <h3>AI hodnocení</h3>

    <p style="white-space: pre-line">
    {data.get("analysis_week","")}
    </p>


    <h2>Posledních 30 dní</h2>

    <table style="border-collapse:collapse;width:100%">
    <tr>
    <th style="border:1px solid #ccc;padding:6px;text-align:right">Sport</th>
    <th style="border:1px solid #ccc;padding:6px;text-align:right">Počet</th>
    <th style="border:1px solid #ccc;padding:6px;text-align:right">Vzdálenost</th>
    <th style="border:1px solid #ccc;padding:6px;text-align:right">TSS</th>
    </tr>

    {build_table_rows(data.get("monthly", []), ["sport","count","distance","tss"])}

    </table>

    <h3>AI hodnocení</h3>

    <p style="white-space: pre-line">
    {data.get("analysis_month","")}
    </p>


    <h2>Doporučení trenéra</h2>

    <p style="font-size:20px">
    {data.get("load_status","")}
    </p>

    <p class="rec">{data.get("recommendation","")}</p>
    """

    return html



def send_email_html(
    html,
    subject,
    to_email,
    smtp_user,
    smtp_password,
    smtp_server="smtp.gmail.com",
    smtp_port=587,
):

    msg = MIMEMultipart("alternative")

    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_email

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(smtp_server, smtp_port) as server:

        server.starttls()

        server.login(smtp_user, smtp_password)

        server.send_message(msg)



def create_and_send_report(data, email_config):

    html = generate_html_report(data)

    resend.api_key = os.getenv("RESEND_API_KEY")

    resend.Emails.send({
        "from": "AI TRI COACH <onboarding@resend.dev>",
        "to": [email_config["to"]],
        "subject": f"AI TRI COACH – report {date.today()}",
        "html": html
    })

    return html
