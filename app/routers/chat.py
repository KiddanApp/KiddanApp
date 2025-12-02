import uuid
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.schemas import ChatRequest, ChatReply
from app.services.ai_service import generate_reply
from app.db import get_database

router = APIRouter()

@router.post("/{character_id}", response_model=ChatReply)
async def chat_with(
    character_id: str,
    payload: ChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        # Generate conversation ID if not provided
        conversation_id = payload.conversation_id
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        resp = await generate_reply(
            character_id=character_id,
            user_message=payload.message,
            language=payload.language,
            conversation_id=conversation_id,
            db=db,
            user_id=payload.user_id
        )
        return resp
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
