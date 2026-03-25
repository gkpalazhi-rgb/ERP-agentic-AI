from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone
from app.database.db import Base


class ERPAPILog(Base):
    __tablename__ = "erp_api_logs"

    id = Column(Integer, primary_key=True, index=True)
    tool_name = Column(String)
    request_payload = Column(String)
    response_status = Column(String)
    plan_id = Column(String, nullable=True)
    step_index = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))