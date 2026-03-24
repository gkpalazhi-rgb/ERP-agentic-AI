from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
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
        admin = db.query(User).filter(User.id == 1).first()
        if not admin:
            admin = User(id=1, username="admin", role="admin")
            db.add(admin)
            db.commit()
            print("Admin user seeded.")
    except Exception as e:
        print(f"Seeding error: {e}")
    finally:
        db.close()

seed_data()

# Preload the semantic intent classifier model at startup
try:
    from app.services.intent_classifier import preload_model
    preload_model()
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
# Root Endpoint
# -------------------------------
@app.get("/")
def read_root():
    return {"message": "ERP Agent is running"}


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
