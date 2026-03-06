import matplotlib.pyplot as plt
import base64
from io import BytesIO

def tss_chart(rows):

    days = [r["day"] for r in rows]
    tss = [r["tss"] for r in rows]

    plt.figure(figsize=(6,3))
    plt.plot(days, tss)
    plt.xticks(rotation=45)
    plt.ylabel("TSS")

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close()

    img = base64.b64encode(buf.getvalue()).decode()

    return img
