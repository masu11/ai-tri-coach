from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Float,
    Text,
    Date,
    DateTime
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

from app.database import Base


# =========================
# ACTIVITIES
# =========================

class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)

    tss = Column(Float)
    strava_id = Column(BigInteger)
    raw_json = Column(JSONB)

    start_date = Column(DateTime)
    duration = Column(Integer)
    elapsed_time = Column(Integer)

    distance = Column(Float)
    total_elevation_gain = Column(Float)

    avg_hr = Column(Float)
    max_hr = Column(Float)

    avg_power = Column(Float)
    avg_speed = Column(Float)
    max_speed = Column(Float)

    avg_cadence = Column(Float)
    calories = Column(Float)
    suffer_score = Column(Float)

    name = Column(Text)
    sport_type = Column(Text)


# =========================
# ACTIVITY_STREAMS
# =========================

class ActivityStream(Base):
    __tablename__ = "activity_streams"

    activity_id = Column(BigInteger, primary_key=True)
    stream_data = Column(JSONB)


# =========================
# GARMIN DAILY METRICS
# =========================

class GarminDailyMetrics(Base):
    __tablename__ = "garmin_daily_metrics"

    date = Column(Date, primary_key=True)

    muscle_mass = Column(Float)
    sleep_seconds = Column(Integer)
    resting_hr = Column(Integer)
    avg_hrv = Column(Float)

    body_battery = Column(Integer)
    stress_avg = Column(Integer)

    vo2max_run = Column(Float)
    weight = Column(Float)

    sleep_score = Column(Integer)
    deep_sleep = Column(Integer)
    rem_sleep = Column(Integer)

    recovery_time = Column(Integer)

    acute_load = Column(Float)
    chronic_load = Column(Float)

    body_fat = Column(Float)
    training_status = Column(Text)