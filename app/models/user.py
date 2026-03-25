from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone
from app.database.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    role = Column(String, default="employee")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

