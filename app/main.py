from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
from typing import Optional

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
from sqlalchemy import text, inspect as sa_inspect

def run_migrations():
    inspector = sa_inspect(engine)
    with engine.connect() as conn:
        # Add 'status' to purchase_orders if missing
        if 'purchase_orders' in inspector.get_table_names():
            existing_cols = [c['name'] for c in inspector.get_columns('purchase_orders')]
            if 'status' not in existing_cols:
                conn.execute(text("ALTER TABLE purchase_orders ADD COLUMN status VARCHAR DEFAULT 'Pending'"))
                conn.commit()
                print("Migration: added 'status' to purchase_orders")

        # Add 'username' to leave_applications if missing
        if 'leave_applications' in inspector.get_table_names():
            existing_cols = [c['name'] for c in inspector.get_columns('leave_applications')]
            if 'username' not in existing_cols:
                conn.execute(text("ALTER TABLE leave_applications ADD COLUMN username VARCHAR"))
                conn.commit()
                print("Migration: added 'username' to leave_applications")

try:
    run_migrations()
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
            "session_id": session_id,
            "session_title": session_title
        }

    except Exception as e: 
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