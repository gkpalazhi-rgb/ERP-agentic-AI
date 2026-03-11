from sqlalchemy import Column, Integer, String, Float
from app.database.db import Base

class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    vendor_name = Column(String)
    item_name = Column(String)
    price = Column(Float)