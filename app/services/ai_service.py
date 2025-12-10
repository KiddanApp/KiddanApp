import json
import uuid
import asyncio
from datetime import datetime
import google.generativeai as genai
from app.config import settings
from app.services.translation_service import translation_service
from pathlib import Path
from typing import Optional, Dict, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models import Message

CHAR_PATH = Path(__file__).resolve().parents[1] / "seed" / "characters.json"

async def load_character(char_id: str) -> Optional[Dict]:
    with open(CHAR_PATH, "r", encoding="utf8") as f:
        chars = json.load(f)
    return chars.get(char_id)

async def call_gemini(prompt: str, max_tokens: int = 80) -> str:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Run blocking call in thread executor
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
            )
        )
    )

    try:
        return response.text
    except Exception:
        return "Demo response: Hello! I'm here to help you learn Punjabi."

async def get_conversation_history(db: AsyncIOMotorDatabase, conversation_id: str, limit: int = 10) -> List[Message]:
    """Get recent conversation history for context"""
    cursor = db.messages.find(
        {"conversation_id": conversation_id}
    ).sort("timestamp", -1).limit(limit)
    messages = []
    async for doc in cursor:
        messages.append(Message(**doc))
    return list(reversed(messages))  # Return in chronological order

async def generate_reply(
    character_id: str,
    user_message: str,
    language: str,
    conversation_id: str,
    db: AsyncIOMotorDatabase,
    user_id: Optional[str] = None
) -> Dict:
    character = await load_character(character_id)
    if not character:
        raise ValueError("Character not found")

    # Load conversation history for context
    history = await get_conversation_history(db, conversation_id, limit=5)

    # Build enhanced prompt with character details and conversation context
    system_prompt = f"""You are {character['name']} ({character.get('nameGurmukhi', character['name'])}), {character['role']}.

Personality: {character['personality']}
Background: {character.get('background', '')}
Speaking Style: {character.get('speaking_style', '')}
Status: {character.get('status', '')}

You are having a conversation in {language}. Respond naturally in character, using appropriate Punjabi phrases and cultural references.
Keep responses conversational and engaging. Remember previous messages in this conversation."""

    # Add conversation history to context
    context = ""
    if history:
        context = "\n\nConversation History:\n"
        for msg in history[-3:]:  # Include last 3 exchanges for context
            context += f"User: {msg.user_message}\n{character['name']}: {msg.ai_message_english}\n\n"

    full_prompt = f"{system_prompt}{context}Current User Message: {user_message}\n\nYour Response:"

    # Generate English response with context
    english = await call_gemini(full_prompt, max_tokens=100)

    print(full_prompt)

    # Translate to Roman and Gurmukhi
    roman, gurmukhi = await asyncio.gather(
        translation_service.translate_to_roman(english),
        translation_service.translate_to_gurmukhi(english)
    )

    # Determine expression based on content
    expression = "normal"
    lower_english = english.lower()
    if any(word in lower_english for word in ["happy", "great", "wonderful", "love", "excited"]):
        expression = "happy"
    elif any(word in lower_english for word in ["angry", "upset", "sorry", "wrong", "bad", "mad", "frustrated"]):
        expression = "angry"
    elif any(word in lower_english for word in ["sad", "unhappy", "disappointed", "heartbroken", "depressed", "unfortunate"]):
        expression = "sad"

    # Save to database
    message_data = {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "character_id": character_id,
        "user_message": user_message,
        "ai_message_english": english.strip(),
        "ai_message_roman": roman.strip(),
        "ai_message_gurmukhi": gurmukhi.strip(),
        "language": language,
        "timestamp": datetime.utcnow()
    }
    await db.messages.insert_one(message_data)

    return {
        "character_id": character_id,
        "conversation_id": conversation_id,
        "expression": expression,
        "reply": {
            "english": english.strip(),
            "roman": roman.strip(),
            "gurmukhi": gurmukhi.strip()
        }
    }
