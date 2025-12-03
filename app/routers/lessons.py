from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import get_database
from app.services.lesson_service import LessonService
from app.services.progress_service import ProgressService
from app.services.simplified_lesson_service import SimplifiedLessonService
from pydantic import BaseModel

router = APIRouter()

def get_lesson_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> LessonService:
    return LessonService(db)

def get_progress_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> ProgressService:
    return ProgressService(db)

def get_simplified_lesson_service() -> SimplifiedLessonService:
    return SimplifiedLessonService()

class StartLessonRequest(BaseModel):
    user_id: str
    lesson_id: str
    character_id: str = "bibi"  # Default to bibi

class AnswerRequest(BaseModel):
    user_id: str
    lesson_id: str
    character_id: str = "bibi"
    answer: str

@router.post("/start")
async def start_lesson(
    request: StartLessonRequest,
    progress_service: ProgressService = Depends(get_progress_service)
):
    """Start a lesson for a user"""
    try:
        # Create or get progress
        progress = await progress_service.get_progress(
            request.user_id, request.character_id, request.lesson_id
        )
        if not progress:
            progress = await progress_service.create_progress(
                request.user_id, request.character_id, request.lesson_id
            )

        return {"message": "Lesson started", "progress": progress.model_dump()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting lesson: {str(e)}")

@router.get("/next")
async def get_next(
    user_id: str,
    lesson_id: str,
    character_id: str = "bibi",
    progress_service: ProgressService = Depends(get_progress_service),
    lesson_service: SimplifiedLessonService = Depends(get_simplified_lesson_service)
):
    """Get next interaction in lesson"""
    try:
        # Get current progress
        progress = await progress_service.get_progress(user_id, character_id, lesson_id)
        if not progress:
            raise HTTPException(status_code=404, detail="Lesson not started. Call /lessons/start first.")

        # Get next interaction
        interaction = lesson_service.get_next_interaction(lesson_id, progress.current_step_index)

        if not interaction:
            raise HTTPException(status_code=404, detail="Lesson not found")

        if interaction["type"] == "completed":
            # Mark as completed
            await progress_service.update_progress(user_id, character_id, lesson_id, progress.current_step_index, True)
            return {"status": "completed"}

        # If advance, update progress
        if interaction["advance"]:
            new_index = progress.current_step_index + 1
            await progress_service.update_progress(user_id, character_id, lesson_id, new_index)

        return interaction

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting next: {str(e)}")

@router.post("/answer")
async def submit_answer(
    request: AnswerRequest,
    progress_service: ProgressService = Depends(get_progress_service),
    lesson_service: SimplifiedLessonService = Depends(get_simplified_lesson_service)
):
    """Submit answer for current question"""
    try:
        # Get current progress
        progress = await progress_service.get_progress(
            request.user_id, request.character_id, request.lesson_id
        )
        if not progress:
            raise HTTPException(status_code=404, detail="Lesson not started")

        # Validate answer
        result = lesson_service.validate_answer(
            request.lesson_id, progress.current_step_index, request.answer
        )

        if result["valid"] and result["advance"]:
            # Advance to next step
            new_index = progress.current_step_index + 1
            await progress_service.update_progress(
                request.user_id, request.character_id, request.lesson_id, new_index
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting answer: {str(e)}")

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
