from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase
import datetime

class Base(DeclarativeBase):
    pass

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=True)
    character_id = Column(String(64), nullable=False)
    user_message = Column(Text, nullable=False)
    ai_message_english = Column(Text, nullable=False)
    ai_message_roman = Column(Text, nullable=False)
    ai_message_gurmukhi = Column(Text, nullable=False)
    language = Column(String(16), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
