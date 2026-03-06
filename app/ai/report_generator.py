
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

def build_table_rows(rows, columns):

    html = ""

    for r in rows:

        html += "<tr>"

        for c in columns:

            value = r.get(c, "") if isinstance(r, dict) else ""

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

    html = f"""
    <html>
    <head>
    <style>

    body {{
        font-family: Arial;
        margin: 20px;
        background-color:#ffffff;
    }}

    h1 {{
        color:#2c3e50;
    }}

    h2 {{
        margin-top:30px;
        color:#34495e;
    }}

    table {{
        border-collapse: collapse;
        width: 100%;
        margin-top:10px;
    }}

    th, td {{
        border:1px solid #ddd;
        padding:8px;
        text-align:center;
    }}

    th {{
        background:#f4f6f7;
    }}

    .rec {{
        font-size:18px;
        font-weight:bold;
        color:#2c3e50;
    }}

    </style>
    </head>

    <body>

    <h1>AI TRI COACH – denní report</h1>
    <p>Datum: {date.today()}</p>

    <h2>Včerejší aktivity</h2>

    <table>
    <tr>
        <th>Sport</th>
        <th>Vzdálenost</th>
        <th>Čas</th>
        <th>TSS</th>
    </tr>
    {yesterday_rows}
    </table>


    <h2>Souhrn posledních 7 dní</h2>

    <table>
    <tr>
        <th>Sport</th>
        <th>Počet aktivit</th>
        <th>Vzdálenost</th>
        <th>TSS</th>
    </tr>
    {weekly_rows}
    </table>


    <h2>Recovery (Garmin)</h2>

    <table>
    <tr>
        <th>Sleep score</th>
        <th>HRV</th>
        <th>Body Battery</th>
        <th>Stress</th>
    </tr>

    <tr>
        <td>{data.get("sleep","")}</td>
        <td>{data.get("hrv","")}</td>
        <td>{data.get("battery","")}</td>
        <td>{data.get("stress","")}</td>
    </tr>

    </table>


    <h2>Doporučení trenéra</h2>

    <p class="rec">{data.get("recommendation","")}</p>


    <h2>Plán na dalších 7 dní</h2>

    <table>
    <tr>
        <th>Den</th>
        <th>Trénink</th>
    </tr>

    {plan_rows}

    </table>

    </body>
    </html>
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

    send_email_html(
        html,
        f"AI TRI COACH – report {date.today()}",
        email_config["to"],
        email_config["user"],
        email_config["password"],
    )

    return html
