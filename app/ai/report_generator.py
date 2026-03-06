
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

            value = r.get(c, "") if isinstance(r, dict) else ""

            if c == "tss" and value not in ("", None):
                value = round(float(value), 2)

            text_align = "left" if c == "sport" else "right"

            html += (
                "<td "
                f"style=\"border:1px solid #cfcfcf;padding:6px 10px;text-align:{text_align}\""
                f">{value}</td>"
            )

        html += "</tr>"

    return html




def generate_html_report(data):

    table_style = (
        "border-collapse:collapse;"
        "width:auto;"
        "border:1px solid #cfcfcf;"
        "margin:0 0 14px 0"
    )
    header_cell_style = (
        "border:1px solid #cfcfcf;"
        "padding:6px 10px;"
        "background:#f6f6f6;"
        "text-align:left"
    )

    yesterday_rows = build_table_rows(
        data.get("yesterday", []),
        ["sport", "distance", "duration", "tss"]
    )

    weekly_rows = build_table_rows(
        data.get("weekly", []),
        ["sport", "count", "distance", "tss"]
    )

    chart7 = tss_chart(data.get("last7_daily", []))
    chart30 = tss_chart(data.get("last30", []))

    html = f"""
        <h2>Včera</h2>

    <table style="{table_style}">
    <tr>
    <th style="{header_cell_style}">Sport</th>
    <th style="{header_cell_style}">Vzdálenost</th>
    <th style="{header_cell_style}">Čas</th>
    <th style="{header_cell_style}">TSS</th>
    </tr>

    {yesterday_rows}

    </table>

    <h3>AI hodnocení</h3>

    <p style="white-space: pre-line">
    {data.get("analysis_yesterday","")}
    </p>


    <h2>Posledních 7 dní</h2>

    <img src="data:image/png;base64,{chart7}" />

    <table style="{table_style}">
    <tr>
    <th style="{header_cell_style}">Sport</th>
    <th style="{header_cell_style}">Počet</th>
    <th style="{header_cell_style}">Vzdálenost</th>
    <th style="{header_cell_style}">TSS</th>
    </tr>

    {weekly_rows}

    </table>

    <h3>AI hodnocení</h3>

    <p style="white-space: pre-line">
    {data.get("analysis_week","")}
    </p>


    <h2>Posledních 30 dní</h2>

    <table style="{table_style}">
    <tr>
    <th style="{header_cell_style}">Sport</th>
    <th style="{header_cell_style}">Počet</th>
    <th style="{header_cell_style}">Vzdálenost</th>
    <th style="{header_cell_style}">TSS</th>
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
