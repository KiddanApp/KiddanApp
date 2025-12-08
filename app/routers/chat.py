import uuid
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.schemas import ChatRequest, ChatReply
from app.services.ai_service import generate_reply
from app.db import get_database
from app.dependencies import get_optional_current_user
from app.models import User
from typing import Optional

router = APIRouter()

@router.post("/{character_id}", response_model=ChatReply)
async def chat_with(
    character_id: str,
    payload: ChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    try:
        # Generate conversation ID if not provided
        conversation_id = payload.conversation_id
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        # Use authenticated user's ID if available, otherwise use the one from payload
        user_id = current_user.id if current_user else payload.user_id

        resp = await generate_reply(
            character_id=character_id,
            user_message=payload.message,
            language=payload.language,
            conversation_id=conversation_id,
            db=db,
            user_id=user_id
        )
        return resp
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
