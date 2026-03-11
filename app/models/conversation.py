from sqlalchemy import Column, Integer, Text, DateTime
from datetime import datetime
from app.database.db import Base

class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    session_id = Column(Text, index=True)
    session_title = Column(Text)
    user_query = Column(Text)
    agent_response = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
