from sqlalchemy import Column, Integer, String
from app.database.db import Base

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    item_code = Column(String)
    item_name = Column(String)
    category = Column(String)
    quantity = Column(Integer)