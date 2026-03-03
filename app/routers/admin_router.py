from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Activity, ActivityStream, GarminDailyMetrics
import os

router = APIRouter()

ADMIN_KEY = os.getenv("ADMIN_KEY")

def serialize(model):
    return {
        column.name: getattr(model, column.name)
        for column in model.__table__.columns
    }

def check_key(key: str):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/admin/export-all")
def export_all(admin_key: str):
    check_key(admin_key)

    db: Session = SessionLocal()

    activities = db.query(Activity).all()
    streams = db.query(ActivityStream).all()
    garmin = db.query(GarminDailyMetrics).all()

    return {
        "activities": [serialize(a) for a in activities],
        "activity_streams": [serialize(s) for s in streams],
        "garmin_daily_metrics": [serialize(g) for g in garmin]
    }


from fastapi.responses import FileResponse
import json
import zipfile
import os
from tempfile import NamedTemporaryFile

@router.get("/admin/export-zip")
def export_zip(admin_key: str):
    check_key(admin_key)

    db: Session = SessionLocal()

    data = {
        "activities": [serialize(a) for a in db.query(Activity).all()],
        "activity_streams": [serialize(s) for s in db.query(ActivityStream).all()],
        "garmin_daily_metrics": [serialize(g) for g in db.query(GarminDailyMetrics).all()],
    }

    # vytvořit dočasný JSON soubor
   with NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8") as json_file:
    json.dump(data, json_file, default=str)
    json_path = json_file.name

    # vytvořit ZIP
    zip_path = json_path.replace(".json", ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(json_path, arcname="export.json")

    os.remove(json_path)

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="ai-tri-coach-export.zip"
    )