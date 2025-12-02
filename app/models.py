from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Message(BaseModel):
    id: Optional[str] = None
    conversation_id: str
    user_id: Optional[str] = None
    character_id: str
    user_message: str
    ai_message_english: str
    ai_message_roman: str
    ai_message_gurmukhi: str
    language: str
    timestamp: datetime = datetime.utcnow()
