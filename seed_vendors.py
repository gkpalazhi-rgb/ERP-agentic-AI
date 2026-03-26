import uuid
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.db import SessionLocal
from app.models.vendor import Vendor
from app.main import run_migrations

def seed():
    # Run migrations first to ensure columns exist
    run_migrations()
    
    db = SessionLocal()
    vendors_data = [
        ("S00001", "A. AMRATLAL & CO.", "Not Given", "Raw Materials"),
        ("S00002", "A.E.M.INDIAN DRUG HOUSE", "THRISSUR", "Raw Materials"),
        ("S00003", "A.J.EXPORT HOUSE", "NEW DELHI", "Raw Materials"),
        ("S00004", "A.S.CHIDAMBARAM & CO", "VIDURHUNAGAR", "Raw Materials"),
        ("S00005", "M.ARUMAIPRAKASAM", "KOZHINJABARA", "Raw Materials"),
        ("S00006", "ABU THAHIR .M.", "KOZHINJAMPARA", "Raw Materials"),
        ("S00007", "ACCEL FRONTLINE LTD", "COCHIN", "Other Suppliers"),
        ("S00008", "ACE FINEPACK PRIVATE LIMITED", "KOCHI", "Other Suppliers"),
        ("S00009", "ADINATH TRADING COMPANY", "NEEMUCH", "Raw Materials"),
        ("S00010", "VIJAYKANT DAIRY&FOOD (KERALA)", "NULLIPADY", "Raw Materials"),
        ("S00011", "A DOT COMPUTERS WEST FORT", "THRISSUR", "Other Suppliers"),
        ("S00012", "AGRO FARMERS", "KASHMIR", "Raw Materials"),
        ("S00013", "AHMEDABAD KERALA SAMAJAM", "AHMEDABAD", "Other Suppliers"),
        ("S00014", "AIMUTTY", "Not Given", "Raw Materials"),
        ("S00015", "AJAY ENTERPRISES", "AKHARA BAZAR", "Raw Materials"),
        ("S00016", "AKHILANAND PATIDAR-SETTLEMENT", "THAIKKATTUSSERY", "Employee"),
        ("S00017", "AKSHAR ENTERPRISES", "MIRA ROAD EAST", "Raw Materials"),
        ("S00018", "AKSHAR INTERNATIONAL(MUMBAI)", "EAST MUMBAI", "Raw Materials"),
        ("S00019", "AKSHEEN", "PERINTHALMANNA", "Packing Materials"),
        ("S00020", "ALAGAR TRADERS", "POLLACHI", "Raw Materials")
    ]
    
    try:
        updated_count = 0
        added_count = 0
        for code, name, location, category in vendors_data:
            existing = db.query(Vendor).filter(Vendor.vendor_code == code).first()
            if existing:
                existing.vendor_name = name
                existing.location = location
                existing.item_category = category
                updated_count += 1
            else:
                new_vendor = Vendor(
                    id=str(uuid.uuid4()),
                    vendor_code=code,
                    vendor_name=name,
                    location=location,
                    item_category=category
                )
                db.add(new_vendor)
                added_count += 1
                
        db.commit()
        print(f"Successfully seeded vendors. Added: {added_count}, Updated: {updated_count}")
    except Exception as e:
        db.rollback()
        print(f"Error seeding vendors: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
