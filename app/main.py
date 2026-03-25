from fastapi import FastAPI, Depends, Query, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
from typing import Optional
from datetime import datetime

from app.database.db import engine, SessionLocal, Base
from app.models.conversation import AIConversation
from app.models.erp_logs import ERPAPILog
from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.models.vendor import Vendor
from app.models.leave_application import LeaveApplication
from app.models.user import User

from app.services.execution_engine import execute_plan
from app.services.agent import generate_plan
from app.services.auth import register_user, login_user, get_current_user, hash_password

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Default Vite port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables automatically
Base.metadata.create_all(bind=engine)

# Migrate: add missing columns to existing tables
from sqlalchemy import inspect as sa_inspect, text

def run_migrations():
    inspector = sa_inspect(engine)
    with engine.connect() as conn:
        def add_column_if_missing(table_name: str, column_name: str, ddl: str):
            if table_name not in inspector.get_table_names():
                return

            existing_cols = [c["name"] for c in inspector.get_columns(table_name)]
            if column_name in existing_cols:
                return

            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
            conn.commit()
            print(f"Migration: added '{column_name}' to {table_name}")

        add_column_if_missing("purchase_orders", "status", "VARCHAR DEFAULT 'Pending'")
        add_column_if_missing("purchase_orders", "po_id", "VARCHAR")
        add_column_if_missing("purchase_orders", "item_code", "VARCHAR")
        add_column_if_missing("leave_applications", "username", "VARCHAR")
        add_column_if_missing("vendors", "email", "VARCHAR")
        add_column_if_missing("inventory", "mrp", "FLOAT")
        add_column_if_missing("users", "password_hash", "VARCHAR")
        add_column_if_missing("users", "created_at", "TIMESTAMP")

        # Fix users id sequence (admin was manually seeded with id=1)
        try:
            conn.execute(text(
                "SELECT setval(pg_get_serial_sequence('users', 'id'), "
                "COALESCE((SELECT MAX(id) FROM users), 0) + 1, false)"
            ))
            conn.commit()
        except Exception:
            pass  # SQLite doesn't have sequences


def backfill_purchase_order_fields():
    db = SessionLocal()
    try:
        purchase_orders = db.query(PurchaseOrder).all()
        updated = 0

        for po in purchase_orders:
            changed = False

            if not po.item_code:
                inventory_match = db.query(Inventory).filter(
                    Inventory.item_name.ilike(f"%{po.item_name}%")
                ).first()
                po.item_code = (
                    inventory_match.item_code
                    if inventory_match and inventory_match.item_code
                    else f"GEN-{(po.item_name or 'PO')[:3].upper()}"
                )
                changed = True

            if not po.po_id:
                created_date = po.created_at or datetime.utcnow()
                date_part = created_date.strftime("%y%m%d")
                po.po_id = f"{date_part}-{po.item_code}-{po.id:03d}"
                changed = True

            if changed:
                updated += 1

        if updated:
            db.commit()
            print(f"Migration: backfilled {updated} purchase orders with po_id/item_code")
    except Exception as e:
        db.rollback()
        print(f"Migration backfill warning: {e}")
    finally:
        db.close()

try:
    run_migrations()
    backfill_purchase_order_fields()
except Exception as e:
    print(f"Migration warning: {e}")

# Seed initial data
def seed_data():
    db = SessionLocal()
    try:
        # Check if admin user exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                role="admin",
                password_hash=hash_password("admin123"),
            )
            db.add(admin)
            db.commit()
            print("Admin user seeded (password: admin123).")
        elif not admin.password_hash:
            # Backfill password for existing admin without one
            admin.password_hash = hash_password("admin123")
            db.commit()
            print("Admin password backfilled.")
    except Exception as e:
        print(f"Seeding error: {e}")
    finally:
        db.close()

seed_data()

# Preload the semantic intent classifier model at startup
try:
    from app.services.intent_classifier import preload_model
    from app.services.semantic_router import preload_semantic_router
    preload_model()
    preload_semantic_router()
except Exception as e:
    print(f"[Intent] Preload skipped: {e}")


# -------------------------------
# Database Dependency
# -------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------
# Pydantic schemas for auth
# -------------------------------
class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: str = "employee"


class LoginRequest(BaseModel):
    username: str
    password: str


# -------------------------------
# Root Endpoint
# -------------------------------
@app.get("/")
def read_root():
    return {"message": "ERP Agent is running"}


# -------------------------------
# Auth Endpoints
# -------------------------------
@app.post("/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    result = register_user(db, req.username, req.password, req.email, req.role)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    result = login_user(db, req.username, req.password)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@app.get("/auth/me")
def get_me(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = authorization.split(" ", 1)[1]
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }


# -------------------------------
# Chat Endpoint
# -------------------------------
@app.post("/chat")
def chat(user_id: int, message: str, session_id: Optional[str] = None, db: Session = Depends(get_db)):

    try:
        # If no session_id provided, create a new one
        if not session_id:
            session_id = str(uuid.uuid4())
            session_title = message[:30] + (message[30:] and '...')
        else:
            # Try to get existing session title
            existing_conv = db.query(AIConversation).filter(AIConversation.session_id == session_id).first()
            session_title = existing_conv.session_title if existing_conv else message[:30]

        # Fetch the last 3 conversations for memory (within the same session)
        past_conversations = db.query(AIConversation)\
            .filter(AIConversation.user_id == user_id, AIConversation.session_id == session_id)\
            .order_by(AIConversation.timestamp.desc())\
            .limit(3).all()
            
        chat_history = ""
        if past_conversations:
            # Reverse to chronological order
            for conv in reversed(past_conversations):
                chat_history += f"User: {conv.user_query}\nAgent: {conv.agent_response}\n"

        # Step 1: Generate plan (handles BOTH conversation and ERP actions)
        plan = generate_plan(message, chat_history)

        if not plan:
            response = "I didn't quite understand that. Could you rephrase?"

        elif plan.get("type") == "conversation":
            # LLM handled this as a conversational response (greetings, small talk, etc.)
            response = plan.get("response", "How can I help you today?")

        elif plan.get("type") == "action" or "steps" in plan:
            # ERP tool execution
            response = execute_plan(plan, db, user_id=user_id)

            # Log the ERP execution
            log = ERPAPILog(
                tool_name="plan_execution",
                request_payload=str(plan),
                response_status="SUCCESS"
            )
            db.add(log)
            db.commit()

        else:
            response = "I didn't quite understand that. Could you rephrase?"

        # Save conversation
        conversation = AIConversation(
            user_id=user_id,
            session_id=session_id,
            session_title=session_title,
            user_query=message,
            agent_response=str(response)
        )

        db.add(conversation)
        db.commit()

        return {
            "plan": plan,
            "response": response,
            "intent_detection": plan.get("intent_detection") if isinstance(plan, dict) else None,
            "session_id": session_id,
            "session_title": session_title
        }

    except Exception as e: 
        import traceback
        traceback.print_exc()
        error_msg = str(e)

        conversation = AIConversation(
            user_id=user_id,
            session_id=session_id or str(uuid.uuid4()),
            session_title=message[:30],
            user_query=message,
            agent_response=error_msg
        )

        db.add(conversation)
        db.commit()

        return {"error": error_msg}


# -------------------------------
# History Endpoints
# -------------------------------
@app.get("/history/{user_id}")
def get_history(user_id: int, db: Session = Depends(get_db)):
    # Get unique sessions for the user with the latest timestamp
    sessions = db.query(
        AIConversation.session_id,
        AIConversation.session_title,
        func.max(AIConversation.timestamp).label("last_updated")
    ).filter(AIConversation.user_id == user_id)\
     .group_by(AIConversation.session_id, AIConversation.session_title)\
     .order_by(func.max(AIConversation.timestamp).desc()).all()
    
    return [
        {
            "session_id": s.session_id,
            "title": s.session_title,
            "last_updated": s.last_updated
        } for s in sessions
    ]


@app.get("/history/chat/{session_id}")
def get_session_chat(session_id: str, db: Session = Depends(get_db)):
    messages = db.query(AIConversation)\
        .filter(AIConversation.session_id == session_id)\
        .order_by(AIConversation.timestamp.asc()).all()
    
    result = []
    for msg in messages:
        result.append({
            "id": msg.id,
            "sender": "user",
            "text": msg.user_query,
            "timestamp": msg.timestamp
        })
        result.append({
            "id": msg.id + 1000000, # Just to make it unique
            "sender": "ai",
            "text": msg.agent_response,
            "timestamp": msg.timestamp
        })
    return result

@app.delete("/history/chat/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    try:
        db.query(AIConversation).filter(AIConversation.session_id == session_id).delete()
        db.commit()
        return {"status": "success", "message": "Session deleted"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


# -------------------------------
# Dashboard Stats
# -------------------------------
@app.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_items = db.query(Inventory).count()
    total_quantity = db.query(func.sum(Inventory.quantity)).scalar() or 0
    low_stock_count = db.query(Inventory).filter(Inventory.quantity < 10).count()

    total_pos = db.query(PurchaseOrder).count()
    pending_pos = db.query(PurchaseOrder).filter(PurchaseOrder.status == "Pending").count()
    delivered_pos = db.query(PurchaseOrder).filter(PurchaseOrder.status == "Delivered").count()

    total_vendors = db.query(Vendor).count()
    total_leaves = db.query(LeaveApplication).count()
    total_users = db.query(User).count()

    recent_logs = db.query(ERPAPILog).order_by(ERPAPILog.timestamp.desc()).limit(5).all()
    recent_activity = [
        {
            "tool": log.tool_name,
            "status": log.response_status,
            "timestamp": str(log.timestamp),
        }
        for log in recent_logs
    ]

    return {
        "inventory": {
            "total_items": total_items,
            "total_quantity": total_quantity,
            "low_stock": low_stock_count,
        },
        "purchase_orders": {
            "total": total_pos,
            "pending": pending_pos,
            "delivered": delivered_pos,
        },
        "vendors": total_vendors,
        "leaves": total_leaves,
        "users": total_users,
        "recent_activity": recent_activity,
    }


# -------------------------------
# Inventory Listing
# -------------------------------
@app.get("/inventory")
def list_inventory(
    search: Optional[str] = None,
    low_stock: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Inventory)
    if search:
        query = query.filter(Inventory.item_name.ilike(f"%{search}%"))
    if low_stock:
        query = query.filter(Inventory.quantity < 10)

    items = query.order_by(Inventory.item_name).all()

    return [
        {
            "id": item.id,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "category": item.category,
            "quantity": item.quantity,
            "mrp": item.mrp,
        }
        for item in items
    ]


# -------------------------------
# Purchase Order Listing
# -------------------------------
@app.get("/purchase-orders")
def list_purchase_orders(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(PurchaseOrder)
    if status:
        query = query.filter(PurchaseOrder.status.ilike(status))

    orders = query.order_by(PurchaseOrder.created_at.desc()).all()

    return [
        {
            "id": po.id,
            "po_id": po.po_id,
            "item_name": po.item_name,
            "item_code": po.item_code,
            "quantity": po.quantity,
            "vendor": po.vendor,
            "status": po.status,
            "created_at": str(po.created_at),
        }
        for po in orders
    ]


# -------------------------------
# Leave Management
# -------------------------------
@app.get("/leaves")
def list_all_leaves(db: Session = Depends(get_db)):
    """List all leave applications (for admin view)."""
    leaves = db.query(LeaveApplication).order_by(
        LeaveApplication.created_at.desc()
    ).all()

    return [
        {
            "id": leave.id,
            "user_id": leave.user_id,
            "username": leave.username,
            "reason": leave.reason,
            "leave_date": str(leave.leave_date),
            "leave_type": leave.leave_type,
            "status": leave.status,
            "created_at": str(leave.created_at),
        }
        for leave in leaves
    ]


@app.get("/leaves/{user_id}")
def list_leaves(user_id: int, db: Session = Depends(get_db)):
    """List leave applications for a specific user."""
    leaves = db.query(LeaveApplication).filter(
        LeaveApplication.user_id == user_id
    ).order_by(LeaveApplication.created_at.desc()).all()

    return [
        {
            "id": leave.id,
            "user_id": leave.user_id,
            "username": leave.username,
            "reason": leave.reason,
            "leave_date": str(leave.leave_date),
            "leave_type": leave.leave_type,
            "status": leave.status,
            "created_at": str(leave.created_at),
        }
        for leave in leaves
    ]


class LeaveStatusUpdate(BaseModel):
    status: str  # "Approved" or "Rejected"


@app.put("/leaves/{leave_id}/status")
def update_leave_status(
    leave_id: int,
    body: LeaveStatusUpdate,
    db: Session = Depends(get_db),
):
    """Approve or reject a leave application."""
    if body.status not in ("Approved", "Rejected"):
        raise HTTPException(status_code=400, detail="Status must be 'Approved' or 'Rejected'")

    leave = db.query(LeaveApplication).filter(LeaveApplication.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave application not found")

    leave.status = body.status
    db.commit()
    db.refresh(leave)

    return {
        "id": leave.id,
        "username": leave.username,
        "status": leave.status,
        "leave_date": str(leave.leave_date),
        "message": f"Leave {body.status.lower()} successfully",
    }


# -------------------------------
# Vendor Listing
# -------------------------------
@app.get("/vendors")
def list_vendors(db: Session = Depends(get_db)):
    vendors = db.query(Vendor).order_by(Vendor.vendor_name).all()
    return [
        {
            "id": v.id,
            "vendor_name": v.vendor_name,
            "item_name": v.item_name,
            "price": v.price,
            "email": v.email,
        }
        for v in vendors
    ]
