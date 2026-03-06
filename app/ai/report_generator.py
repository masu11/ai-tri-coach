from datetime import date

def generate_html_report(data):

    html = f"""
    <html>
    <head>
    <style>
        body {{
            font-family: Arial;
            margin: 20px;
        }}

        h2 {{
            color: #2c3e50;
        }}

        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 25px;
        }}

        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: center;
        }}

        th {{
            background-color: #f4f6f7;
        }}

        .good {{
            color: green;
        }}

        .warn {{
            color: orange;
        }}

        .bad {{
            color: red;
        }}

    </style>
    </head>

    <body>

    <h1>AI TRI COACH REPORT</h1>
    <p>Datum: {date.today()}</p>

    <h2>Včerejší trénink</h2>

    <table>
        <tr>
            <th>Sport</th>
            <th>Vzdálenost</th>
            <th>Čas</th>
            <th>TSS</th>
        </tr>

        {data["yesterday_rows"]}

    </table>


    <h2>Souhrn posledních 7 dní</h2>

    <table>
        <tr>
            <th>Sport</th>
            <th>Počet aktivit</th>
            <th>Celková vzdálenost</th>
            <th>TSS</th>
        </tr>

        {data["weekly_rows"]}

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
            <td>{data["sleep"]}</td>
            <td>{data["hrv"]}</td>
            <td>{data["battery"]}</td>
            <td>{data["stress"]}</td>
        </tr>

    </table>


    <h2>Doporučení trenéra</h2>

    <p><b>{data["recommendation"]}</b></p>


    <h2>Plán na dalších 7 dní</h2>

    <table>
        <tr>
            <th>Den</th>
            <th>Trénink</th>
        </tr>

        {data["plan_rows"]}

    </table>

    </body>
    </html>
    """

    return html
