from pydantic import BaseModel
from typing import Optional, Dict

class CharacterOut(BaseModel):
    id: str
    name: str
    role: str
    personality: Optional[str]

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None  # If None, starts new conversation
    user_id: Optional[str]
    message: str
    language: str  # "english" | "roman" | "gurmukhi"

class ChatReply(BaseModel):
    character_id: str
    conversation_id: str
    expression: str
    reply: Dict[str, str]  # {"english": ..., "roman": ..., "gurmukhi": ...}
