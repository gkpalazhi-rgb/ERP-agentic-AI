import json
import os

from fastapi import FastAPI, Depends, Query, Header, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
from typing import Optional
from datetime import datetime
import smtplib
from email.message import EmailMessage
from html import escape as html_escape
from dotenv import load_dotenv

load_dotenv()

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
from app.services.feature_access import (
    AVAILABLE_FEATURES,
    effective_feature_access,
    normalize_feature_list,
    serialize_feature_access,
)

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def error_payload(code: str, message: str, details: dict | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail_message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    detail_meta = {} if isinstance(exc.detail, str) else {"detail": exc.detail}
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload("HTTP_ERROR", detail_message, detail_meta),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=error_payload("INTERNAL_ERROR", "Unexpected server error", {"exception": str(exc)}),
    )

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
        add_column_if_missing("leave_applications", "admin_remark", "TEXT")
        add_column_if_missing("vendors", "email", "VARCHAR")
        add_column_if_missing("vendors", "item_category", "VARCHAR")
        add_column_if_missing("vendors", "vendor_code", "VARCHAR")
        add_column_if_missing("vendors", "location", "VARCHAR")
        add_column_if_missing("inventory", "mrp", "FLOAT")
        add_column_if_missing("users", "password_hash", "VARCHAR")
        add_column_if_missing("users", "created_at", "TIMESTAMP")
        add_column_if_missing("users", "accessible_features", "TEXT")

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

import threading

# Preload the semantic intent classifier model in the background so it doesn't block server startup
def _async_preload():
    try:
        from app.services.intent_classifier import preload_model
        from app.services.semantic_router import preload_semantic_router
        print("[Intent] Starting background model preload...")
        preload_model()
        preload_semantic_router()
        print("[Intent] Background preload completed successfully.")
    except Exception as e:
        print(f"[Intent] Preload skipped: {e}")

if os.getenv("DISABLE_INTENT_PRELOAD", "0") != "1":
    threading.Thread(target=_async_preload, daemon=True).start()


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
    feature_access: Optional[list[str]] = None


class LoginRequest(BaseModel):
    username: str
    password: str

class VendorCreate(BaseModel):
    vendor_code: str
    vendor_name: str
    location: str
    item_category: str
    email: Optional[str] = None

class VendorUpdate(BaseModel):
    vendor_name: Optional[str] = None
    location: Optional[str] = None
    item_category: Optional[str] = None
    email: Optional[str] = None


class PurchaseOrderCancelRequest(BaseModel):
    reason: Optional[str] = None


class UserFeatureAccessUpdateRequest(BaseModel):
    feature_access: list[str]


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
    result = register_user(
        db,
        req.username,
        req.password,
        req.email,
        req.role,
        req.feature_access,
    )
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
        "feature_access": effective_feature_access(user.role, user.accessible_features),
    }


def _write_chat_audit_log(db: Session, user: User, message: str, plan: dict | None, response: str, status: str) -> None:
    intents: list[str] = []
    chain_name = None
    if isinstance(plan, dict):
        intent_detection = plan.get("intent_detection", {})
        resolved_intents = intent_detection.get("resolved_intents", [])
        if isinstance(resolved_intents, list):
            intents = [entry.get("intent") for entry in resolved_intents if isinstance(entry, dict) and entry.get("intent")]
        if not intents and isinstance(intent_detection.get("intent"), str):
            intents = [intent_detection["intent"]]
        chain = intent_detection.get("chain", {}) if isinstance(intent_detection, dict) else {}
        if isinstance(chain, dict):
            chain_name = chain.get("name")

    payload = {
        "user_id": user.id,
        "role": user.role,
        "message": message,
        "intents": intents,
        "chain": chain_name,
        "response_preview": str(response)[:200],
    }
    db.add(
        ERPAPILog(
            tool_name="agent_chat",
            request_payload=json.dumps(payload, default=str),
            response_status=status,
        )
    )
    db.commit()


def get_current_active_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def get_admin_user(current_user: User = Depends(get_current_active_user)):
    role = (current_user.role or "").strip().lower()
    if role not in ("admin", "administrator", "hr"):
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user


def get_system_admin_user(current_user: User = Depends(get_current_active_user)):
    role = (current_user.role or "").strip().lower()
    if role not in ("admin", "administrator"):
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user


def _require_feature_access(current_user: User, feature: str):
    features = effective_feature_access(
        current_user.role,
        getattr(current_user, "accessible_features", None),
    )
    feature_key = (feature or "").strip().lower().replace("-", "_")
    if feature_key not in set(features):
        raise HTTPException(
            status_code=403,
            detail=f"Feature '{feature_key}' is not enabled for this user.",
        )


def _can_manage_leaves(current_user: User) -> bool:
    role = (current_user.role or "").strip().lower()
    if role in ("admin", "administrator", "hr"):
        return True

    features = set(
        effective_feature_access(
            current_user.role,
            getattr(current_user, "accessible_features", None),
        )
    )
    return "leaves" in features and "dashboard" in features


# -------------------------------
# Chat Endpoint
# -------------------------------
@app.post("/chat")
def chat(
    message: str,
    session_id: Optional[str] = None,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = authorization.split(" ", 1)[1]
    current_user = get_current_user(db, token)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    _require_feature_access(current_user, "chat")

    user_id = current_user.id

    try:
        # If no session_id provided, create a new one
        if not session_id:
            session_id = str(uuid.uuid4())
            session_title = message[:30] + (message[30:] and '...')
        else:
            # Try to get existing session title
            existing_conv = db.query(AIConversation).filter(AIConversation.session_id == session_id).first()
            if existing_conv and existing_conv.user_id != user_id and current_user.role not in ("admin", "administrator"):
                raise HTTPException(status_code=403, detail="Not authorized for this session")
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
            response = execute_plan(plan, db, user_id=user_id, user_role=current_user.role)

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

        _write_chat_audit_log(db, current_user, message, plan if isinstance(plan, dict) else None, str(response), "SUCCESS")

        return {
            "plan": plan,
            "response": response,
            "intent_detection": plan.get("intent_detection") if isinstance(plan, dict) else None,
            "session_id": session_id,
            "session_title": session_title
        }

    except HTTPException as e:
        error_msg = str(e.detail)

        conversation = AIConversation(
            user_id=user_id,
            session_id=session_id or str(uuid.uuid4()),
            session_title=message[:30],
            user_query=message,
            agent_response=error_msg
        )

        db.add(conversation)
        db.commit()
        _write_chat_audit_log(db, current_user, message, None, error_msg, "FAILED")
        raise

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

        _write_chat_audit_log(db, current_user, message, None, error_msg, "FAILED")
        raise HTTPException(status_code=500, detail=error_msg)


# -------------------------------
# History Endpoints
# -------------------------------
@app.get("/history/{user_id}")
def get_history(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    _require_feature_access(current_user, "chat")
    if current_user.id != user_id and current_user.role not in ("admin", "administrator"):
        raise HTTPException(status_code=403, detail="Not authorized")

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
def get_session_chat(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    _require_feature_access(current_user, "chat")
    owner = db.query(AIConversation.user_id).filter(AIConversation.session_id == session_id).first()
    if owner and owner[0] != current_user.id and current_user.role not in ("admin", "administrator"):
        raise HTTPException(status_code=403, detail="Not authorized")

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
def delete_session(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    _require_feature_access(current_user, "chat")
    owner = db.query(AIConversation.user_id).filter(AIConversation.session_id == session_id).first()
    if owner and owner[0] != current_user.id and current_user.role not in ("admin", "administrator"):
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        db.query(AIConversation).filter(AIConversation.session_id == session_id).delete(synchronize_session=False)
        db.commit()
        return {"status": "success", "message": "Session deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------
# Dashboard Stats
# -------------------------------
@app.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    _require_feature_access(current_user, "dashboard")
    total_items = db.query(Inventory).count()
    total_quantity = db.query(func.sum(Inventory.quantity)).scalar() or 0
    low_stock_count = db.query(Inventory).filter(Inventory.quantity < 50).count()

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


@app.get("/users")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_system_admin_user),
):
    users = db.query(User).order_by(User.username.asc()).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "feature_access": effective_feature_access(user.role, user.accessible_features),
        }
        for user in users
    ]


@app.get("/users/features")
def get_feature_catalog(
    current_user: User = Depends(get_system_admin_user),
):
    return {"features": list(AVAILABLE_FEATURES)}


@app.put("/users/{user_id}/features")
def update_user_feature_access(
    user_id: int,
    body: UserFeatureAccessUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_system_admin_user),
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    requested_features = normalize_feature_list(body.feature_access)
    target_user.accessible_features = serialize_feature_access(requested_features)
    db.commit()
    db.refresh(target_user)

    return {
        "id": target_user.id,
        "username": target_user.username,
        "role": target_user.role,
        "feature_access": effective_feature_access(target_user.role, target_user.accessible_features),
    }


# -------------------------------
# Inventory Listing
# -------------------------------
@app.get("/inventory")
def list_inventory(
    search: Optional[str] = None,
    low_stock: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_feature_access(current_user, "inventory")
    query = db.query(Inventory)
    if search:
        query = query.filter(Inventory.item_name.ilike(f"%{search}%"))
    if low_stock:
        query = query.filter(Inventory.quantity < 50)

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
    current_user: User = Depends(get_current_active_user),
):
    _require_feature_access(current_user, "purchase_orders")
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


@app.put("/purchase-orders/{po_ref}/cancel")
def cancel_purchase_order_endpoint(
    po_ref: str,
    body: Optional[PurchaseOrderCancelRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_feature_access(current_user, "purchase_orders")
    from app.services.tools import cancel_purchase_order as cancel_po_tool

    cancellation_reason = body.reason if body else None
    result = cancel_po_tool(
        po_id=po_ref,
        db=db,
        cancellation_reason=cancellation_reason,
        user_id=current_user.id,
    )

    if "error" in result:
        error_text = str(result["error"])
        if "not found" in error_text.lower():
            raise HTTPException(status_code=404, detail=error_text)
        raise HTTPException(status_code=400, detail=error_text)

    return result


# -------------------------------
# Leave Management
# -------------------------------

@app.get("/leaves")
def list_all_leaves(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """List all leave applications (for admin view)."""
    _require_feature_access(current_user, "leaves")
    if not _can_manage_leaves(current_user):
        raise HTTPException(status_code=403, detail="Not authorized")
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
            "admin_remark": leave.admin_remark,
            "created_at": str(leave.created_at),
        }
        for leave in leaves
    ]


@app.get("/leaves/{user_id}")
def list_leaves(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """List leave applications for a specific user."""
    _require_feature_access(current_user, "leaves")
    if current_user.id != user_id and not _can_manage_leaves(current_user):
        raise HTTPException(status_code=403, detail="Not authorized")
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
            "admin_remark": leave.admin_remark,
            "created_at": str(leave.created_at),
        }
        for leave in leaves
    ]


class LeaveStatusUpdate(BaseModel):
    status: str  # "Approved" or "Rejected"
    admin_remark: Optional[str] = None


def send_real_email(to_email: str, subject: str, message: str, html_message: str | None = None):
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_from = os.environ.get("SMTP_FROM_EMAIL") or smtp_user

    if not smtp_user or not smtp_password:
        print("Real email skipped: SMTP credentials not found in env.")
        return

    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = smtp_from
        msg['To'] = to_email
        msg.set_content(message)
        if html_message:
            msg.add_alternative(html_message, subtype="html")

        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        print(f"Real email successfully sent to {to_email}")
    except Exception as e:
        print(f"Error sending email: {e}")


@app.put("/leaves/{leave_id}/status")
def update_leave_status(
    leave_id: int,
    body: LeaveStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Approve or reject a leave application."""
    _require_feature_access(current_user, "leaves")
    if not _can_manage_leaves(current_user):
        raise HTTPException(status_code=403, detail="Not authorized")
    if body.status not in ("Approved", "Rejected"):
        raise HTTPException(status_code=400, detail="Status must be 'Approved' or 'Rejected'")

    leave = db.query(LeaveApplication).filter(LeaveApplication.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave application not found")

    leave.status = body.status
    if body.admin_remark:
        leave.admin_remark = body.admin_remark
    db.commit()
    db.refresh(leave)

    # Mock Send Email
    user = db.query(User).filter(User.id == leave.user_id).first()
    to_email = user.email if user and user.email else "erp.major.project@gmail.com"
    company_name = "Thaikkattu Mooss Vaidyaratnam"
    subject = f"{company_name} | Leave Application {body.status} | Ref #{leave.id}"

    submitted_on = leave.created_at.strftime("%d %b %Y, %I:%M %p") if leave.created_at else "N/A"
    reviewed_on = datetime.now().strftime("%d %b %Y, %I:%M %p")
    reviewer_name = current_user.username if current_user and current_user.username else "HR Team"
    remark = (body.admin_remark or leave.admin_remark or "No additional remarks.").strip()
    reason = (leave.reason or "Not provided").strip()
    leave_date_text = str(leave.leave_date)

    decision_label = "Rejection Reason" if body.status == "Rejected" else "Reviewer Remarks"

    msg_lines = [
        f"Dear {leave.username},",
        "",
        f"This is an official update from {company_name} regarding your leave application.",
        "",
        f"Application Status: {body.status}",
        "",
        "Leave Application Details",
        "-------------------------",
        f"Reference ID      : {leave.id}",
        f"Employee          : {leave.username}",
        f"Application Date  : {submitted_on}",
        f"Leave Date        : {leave_date_text}",
        f"Leave Type        : {leave.leave_type}",
        f"Reason Submitted  : {reason}",
        f"Reviewed On       : {reviewed_on}",
        f"Reviewed By       : {reviewer_name}",
        f"{decision_label:<18}: {remark}",
        "",
        "If you have any questions, please contact the HR/Admin team.",
        "",
        f"Regards,",
        f"{company_name}",
        "ERP HR Desk",
    ]

    h_username = html_escape(str(leave.username))
    h_company_name = html_escape(company_name)
    h_status = html_escape(body.status)
    h_leave_id = html_escape(str(leave.id))
    h_submitted_on = html_escape(submitted_on)
    h_leave_date_text = html_escape(leave_date_text)
    h_leave_type = html_escape(str(leave.leave_type))
    h_reason = html_escape(reason)
    h_reviewed_on = html_escape(reviewed_on)
    h_reviewer_name = html_escape(reviewer_name)
    h_decision_label = html_escape(decision_label)
    h_remark = html_escape(remark)

    html_message = f"""
<html>
  <body style="font-family: Arial, Helvetica, sans-serif; color: #1f2937; line-height: 1.5;">
    <p>Dear <strong>{h_username}</strong>,</p>
    <p>This is an official update from <strong>{h_company_name}</strong> regarding your leave application.</p>
    <p><strong>Application Status:</strong> {h_status}</p>
    <table style="border-collapse: collapse; width: 100%; max-width: 640px;">
      <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Reference ID</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{h_leave_id}</td></tr>
      <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Employee</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{h_username}</td></tr>
      <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Application Date</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{h_submitted_on}</td></tr>
      <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Leave Date</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{h_leave_date_text}</td></tr>
      <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Leave Type</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{h_leave_type}</td></tr>
      <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Reason Submitted</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{h_reason}</td></tr>
      <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Reviewed On</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{h_reviewed_on}</td></tr>
      <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Reviewed By</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{h_reviewer_name}</td></tr>
      <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>{h_decision_label}</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{h_remark}</td></tr>
    </table>
    <p>If you have any questions, please contact the HR/Admin team.</p>
    <p>Regards,<br>{h_company_name}<br>ERP HR Desk</p>
  </body>
</html>
""".strip()
        
    print("=======================================")
    print(f"EMAIL TO: {to_email}")
    print(f"SUBJECT: {subject}")
    print("MESSAGE:")
    print("\n".join(msg_lines))
    print("=======================================")
    
    # Send the actual email via background task
    background_tasks.add_task(send_real_email, to_email, subject, "\n".join(msg_lines), html_message)

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
def list_vendors(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    _require_feature_access(current_user, "vendors")
    vendors = db.query(Vendor).order_by(Vendor.vendor_name).all()
    return [
        {
            "vendor_code": v.vendor_code,
            "vendor_name": v.vendor_name,
            "location": v.location,
            "item_category": v.item_category,
            "email": v.email,
        }
        for v in vendors
    ]

@app.post("/vendors")
def create_vendor(vendor: VendorCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    _require_feature_access(current_user, "vendors")
    existing = db.query(Vendor).filter(Vendor.vendor_code == vendor.vendor_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vendor code already exists")
    
    new_vendor = Vendor(
        vendor_code=vendor.vendor_code,
        vendor_name=vendor.vendor_name,
        location=vendor.location,
        item_category=vendor.item_category,
        email=vendor.email
    )
    db.add(new_vendor)
    db.commit()
    db.refresh(new_vendor)
    return new_vendor

@app.put("/vendors/{vendor_code}")
def update_vendor(vendor_code: str, vendor_data: VendorUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    _require_feature_access(current_user, "vendors")
    vendor = db.query(Vendor).filter(Vendor.vendor_code == vendor_code).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
        
    for key, value in vendor_data.dict(exclude_unset=True).items():
        setattr(vendor, key, value)
        
    db.commit()
    db.refresh(vendor)
    return vendor
