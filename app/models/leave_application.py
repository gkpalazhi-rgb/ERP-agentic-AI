from sqlalchemy import Column, Integer, String, Date, Text, DateTime
from datetime import datetime
from app.database.db import Base

class LeaveApplication(Base):
    __tablename__ = "leave_applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    username = Column(String)  # Automatically filled from users table
    reason = Column(Text)
    leave_date = Column(Date)
    leave_type = Column(String)  # Full Day, 1st Half, 2nd Half
    status = Column(String, default="Pending")
    created_at = Column(DateTime, default=datetime.utcnow)
