from pydantic import BaseModel
from typing import Optional, Dict, List, Any
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

class CharacterMessage(BaseModel):
    romanPunjabi: Optional[str] = None
    gurmukhi: Optional[str] = None
    romanEnglish: Optional[str] = None
    additionalNotes: str = ""

class LessonStep(BaseModel):
    lessonType: str
    emotion: Optional[str] = None
    characterMessage: Optional[CharacterMessage] = None
    question: str
    options: List[str]
    correctAnswers: List[str]

class Lesson(BaseModel):
    id: str
    characterId: str
    title: str
    steps: List[LessonStep]

class LessonData(BaseModel):
    characterId: str
    characterName: str
    lessons: List[Lesson]

class Character(BaseModel):
    id: str
    name: str
    nameGurmukhi: Optional[str] = None
    role: str
    personality: Optional[str] = None
    background: Optional[str] = None
    speaking_style: Optional[str] = None
    status: Optional[str] = None
    difficulty: Optional[str] = None
    languages: Optional[List[str]] = None
    prompt_style: Optional[str] = None
    emotion_map: Optional[Dict[str, str]] = None
    conversation_topics: Optional[List[str]] = None

class User(BaseModel):
    id: Optional[str] = None
    email: str
    hashed_password: str
    created_at: datetime = datetime.utcnow()

class UserLessonProgress(BaseModel):
    user_id: str
    character_id: str
    current_lesson_index: int = 0  # Index in character's lessons array
    current_step_index: int = 0    # Index in current lesson's steps array
    completed: bool = False
    id: Optional[str] = None

class CharacterInteraction(BaseModel):
    user_id: str
    character_id: str
    emotion: str
    interaction_type: str  # "chat" or "lesson"
    timestamp: datetime = datetime.utcnow()
    id: Optional[str] = None
