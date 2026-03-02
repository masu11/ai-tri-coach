from fastapi import APIRouter
from app.services.weekly_report_service import get_weekly_report

router = APIRouter()

@router.get("/weekly-report")
def weekly_report():
    return get_weekly_report()
