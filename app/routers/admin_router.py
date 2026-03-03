from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Activity, ActivityStream, GarminDailyMetrics
import os

router = APIRouter()

ADMIN_KEY = os.getenv("ADMIN_KEY")


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
        "activities": [a.__dict__ for a in activities],
        "activity_streams": [s.__dict__ for s in streams],
        "garmin_daily_metrics": [g.__dict__ for g in garmin]
    }