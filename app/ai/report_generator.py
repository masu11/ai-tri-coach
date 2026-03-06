
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

            alignment = "left" if c == "sport" else "right"

            html += (
                "<td "
                "style='padding:10px 12px;"
                "border-bottom:1px solid #e5e7eb;"
                f"text-align:{alignment};'"
                f">{value}</td>"
            )

        html += "</tr>"

    return html


def build_report_table(title, rows):

    heading = ""

    if title:
        heading = f'<h2 style="margin:24px 0 12px;font-size:32px;line-height:1.2;color:#0f172a">{title}</h2>'

    return f"""
    {heading}
    <table style="border-collapse:separate;border-spacing:0;width:80%;max-width:760px;background:#ffffff;border:1px solid #dbe4f0;border-radius:10px;overflow:hidden">
        <thead>
            <tr style="background:#eef4ff">
                <th style="padding:11px 12px;text-align:left;color:#1e3a8a;font-weight:700;border-bottom:1px solid #dbe4f0">Sport</th>
                <th style="padding:11px 12px;text-align:right;color:#1e3a8a;font-weight:700;border-bottom:1px solid #dbe4f0">Počet</th>
                <th style="padding:11px 12px;text-align:right;color:#1e3a8a;font-weight:700;border-bottom:1px solid #dbe4f0">Vzdálenost</th>
                <th style="padding:11px 12px;text-align:right;color:#1e3a8a;font-weight:700;border-bottom:1px solid #dbe4f0">TSS</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
    """




def generate_html_report(data):

    yesterday_rows = build_table_rows(
        data.get("yesterday", []),
        ["sport", "count", "distance", "tss"]
    )

    weekly_rows = build_table_rows(
        data.get("weekly", []),
        ["sport", "count", "distance", "tss"]
    )

    chart7 = tss_chart(data.get("last7_daily", []))

    monthly_rows = build_table_rows(
        data.get("monthly", []),
        ["sport", "count", "distance", "tss"]
    )

    html = f"""
    <div style="font-family:Arial,sans-serif;background:#f8fafc;color:#0f172a;padding:20px 18px">
        {build_report_table("Včera", yesterday_rows)}

        <h3 style="margin:16px 0 8px;font-size:22px;color:#1f2937">AI hodnocení</h3>
        <p style="white-space:pre-line;margin:0 0 10px;line-height:1.5;max-width:760px">
            {data.get("analysis_yesterday","")}
        </p>

        <h2 style="margin:30px 0 12px;font-size:32px;line-height:1.2;color:#0f172a">Posledních 7 dní</h2>
        <img src="data:image/png;base64,{chart7}" style="width:80%;max-width:760px;display:block;margin-bottom:14px;border-radius:10px;border:1px solid #dbe4f0;background:#fff" />
        {build_report_table("", weekly_rows)}

        <h3 style="margin:16px 0 8px;font-size:22px;color:#1f2937">AI hodnocení</h3>
        <p style="white-space:pre-line;margin:0 0 10px;line-height:1.5;max-width:760px">
            {data.get("analysis_week","")}
        </p>

        {build_report_table("Posledních 30 dní", monthly_rows)}

        <h3 style="margin:16px 0 8px;font-size:22px;color:#1f2937">AI hodnocení</h3>
        <p style="white-space:pre-line;margin:0 0 10px;line-height:1.5;max-width:760px">
            {data.get("analysis_month","")}
        </p>

        <h2 style="margin:24px 0 8px;font-size:30px;line-height:1.2;color:#0f172a">Doporučení trenéra</h2>
        <p style="font-size:22px;margin:0 0 8px;color:#0f172a;font-weight:700">
            {data.get("load_status","")}
        </p>

        <p style="margin:0;line-height:1.5;max-width:760px">{data.get("recommendation","")}</p>
    </div>
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
