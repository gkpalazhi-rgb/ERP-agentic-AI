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

        # Step 1: Generate execution plan
        plan = generate_plan(message, chat_history)

        if not plan:
            response = "I did not understand the request."

        else:
            # Step 2: Execute plan
            response = execute_plan(plan, db)

            # Step 3: Log overall ERP execution
            log = ERPAPILog(
                tool_name="plan_execution",
                request_payload=str(plan),
                response_status="SUCCESS"
            )

            db.add(log)
            db.commit()

        # Step 4: Save conversation
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