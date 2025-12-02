from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import get_database
from app.services.lesson_service import LessonService

router = APIRouter()

def get_lesson_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> LessonService:
    return LessonService(db)

@router.get("/{character_key}")
async def get_character_lessons(character_key: str, service: LessonService = Depends(get_lesson_service)):
    """
    Get lesson data for a specific character.

    Args:
        character_key: The character identifier (e.g., 'bibi', 'chacha')

    Returns:
        JSON object containing all lessons for the character
    """
    try:
        lesson_data = await service.get_character_lessons(character_key)

        if not lesson_data:
            raise HTTPException(
                status_code=404,
                detail=f"Lesson data not found for character: {character_key}"
            )

        return lesson_data.model_dump()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading lessons for character {character_key}: {str(e)}"
        )
