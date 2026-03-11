import sys
import os

# Append the project root to sys.path
sys.path.append(os.getcwd())

try:
    from app.database.db import SessionLocal
    from app.models.user import User
    from app.models.purchase_order import PurchaseOrder
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        print("Testing DB connection...")
        db.execute(text("SELECT 1"))
        print("DB ok.")
        
        print("Testing User query...")
        u = db.query(User).first()
        print(f"User ok: {u}")
        
        print("Testing PO query...")
        po = db.query(PurchaseOrder).first()
        print(f"PO ok: {po}")
        if po:
            print(f"PO Status: {getattr(po, 'status', 'MISSING')}")

    except Exception as db_e:
        print(f"DB Error: {db_e}")
    finally:
        db.close()
except Exception as e:
    print(f"Import/Setup Error: {e}")
    import traceback
    traceback.print_exc()
