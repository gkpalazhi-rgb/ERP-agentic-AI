from sqlalchemy import Column, Integer, String, Float
from app.database.db import Base

class Vendor(Base):
    __tablename__ = "vendors"

    vendor_code = Column(String, primary_key=True, index=True)
    vendor_name = Column(String)
    location = Column(String)
    item_category = Column(String)
    email = Column(String, nullable=True)