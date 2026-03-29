import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database.db import SessionLocal
from app.models.vendor import Vendor

def update_all_vendor_emails():
    db = SessionLocal()
    try:
        db.query(Vendor).update({Vendor.email: "pruthu15800@gmail.com"})
        db.commit()
        print("Successfully updated all vendor emails to pruthu15800@gmail.com")
    except Exception as e:
        db.rollback()
        print("Failed:", e)
    finally:
        db.close()

if __name__ == "__main__":
    update_all_vendor_emails()
