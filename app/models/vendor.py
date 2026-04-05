import uuid
from sqlalchemy import Column, Integer, String, Float
from app.database.db import Base

class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(String, default=lambda: str(uuid.uuid4()), nullable=True) # Adding back to satisfy SQLite schema which wasn't fully migrated
    vendor_code = Column(String, primary_key=True, index=True)
    vendor_name = Column(String)
    location = Column(String)
    item_category = Column(String)
    email = Column(String, nullable=True)