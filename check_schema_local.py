from sqlalchemy import inspect, text
from app.database.db import engine

inspector = inspect(engine)
try:
    columns = [col['name'] for col in inspector.get_columns('purchase_orders')]
    print(f"Columns in purchase_orders: {columns}")
except Exception as e:
    print(f"Error checking purchase_orders: {e}")

try:
    columns_leave = [col['name'] for col in inspector.get_columns('leave_applications')]
    print(f"Columns in leave_applications: {columns_leave}")
except Exception as e:
    print(f"Error checking leave_applications: {e}")
