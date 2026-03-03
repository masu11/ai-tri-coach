from sqlalchemy import Column, Integer, String, Float, Date, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    tss = Column(Float)
    start_date = Column(DateTime)

class ActivityStream(Base):
    __tablename__ = "activity_streams"

    activity_id = Column(BigInteger, primary_key=True)
    stream_data = Column(JSONB)

class GarminDailyMetrics(Base):
    __tablename__ = "garmin_daily_metrics"

    id = Column(Integer, primary_key=True)
    date = Column(Date)
    avg_hrv = Column(Float)
    resting_hr = Column(Float)
    sleep_score = Column(Float)