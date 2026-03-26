"""Script to recreate the vendors table with the updated schema."""
from app.database.db import Base, engine
from app.models.vendor import Vendor

Base.metadata.create_all(bind=engine)
print("✅ vendors table recreated successfully with new schema!")
