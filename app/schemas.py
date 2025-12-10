from pydantic import BaseModel
from typing import Optional, Dict

class CharacterOut(BaseModel):
    id: str
    name: str
    role: str
    personality: Optional[str]
    progress: int = 0  # Progress percentage 0-100 for the user
    total_questions: int = 0  # Total questions in all lessons for this character
    completed_questions: int = 0  # Questions completed by the user for this character
    emotion: str = "happy"  # Current emotion based on last chat interaction

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None  # If None, starts new conversation
    user_id: Optional[str]
    message: str
    language: str  # "english" | "roman" | "gurmukhi"

class AnswerResponse(BaseModel):
    valid: bool
    advance: bool
    feedback: str
    retry: bool = False
    emotion: str = "normal"  # Emotion determined from the feedback content

class ChatReply(BaseModel):
    character_id: str
    conversation_id: str
    expression: str
    reply: Dict[str, str]  # {"english": ..., "roman": ..., "gurmukhi": ...}

class UserSignup(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: str
    email: str
    created_at: str
