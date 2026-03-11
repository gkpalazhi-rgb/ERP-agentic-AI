from sqlalchemy import text
from app.database.db import engine

with engine.connect() as conn:
    print("Checking 'status' in 'purchase_orders'...")
    try:
        conn.execute(text("ALTER TABLE purchase_orders ADD COLUMN status VARCHAR DEFAULT 'Pending';"))
        conn.commit()
        print("Success: added 'status' to 'purchase_orders'.")
    except Exception as e:
        print(f"Skipping: {e}")

    print("Checking 'username' in 'leave_applications'...")
    try:
        conn.execute(text("ALTER TABLE leave_applications ADD COLUMN username VARCHAR;"))
        conn.commit()
        print("Success: added 'username' to 'leave_applications'.")
    except Exception as e:
        print(f"Skipping: {e}")
    
    print("Migration complete.")
