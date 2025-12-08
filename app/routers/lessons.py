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
    character_id: str = "bibi"  # Default to bibi

class AnswerRequest(BaseModel):
    user_id: str
    character_id: str = "bibi"
    answer: str

@router.post("/start")
async def start_lesson(
    request: StartLessonRequest,
    progress_service: ProgressService = Depends(get_progress_service)
):
    """Start lessons for a character's user"""
    try:
        # Create or get progress
        progress = await progress_service.get_progress(
            request.user_id, request.character_id
        )
        if not progress:
            progress = await progress_service.create_progress(
                request.user_id, request.character_id
            )

        return {"message": "Character lessons started", "progress": progress.model_dump()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting lessons: {str(e)}")

@router.get("/next")
async def get_next(
    user_id: str,
    character_id: str = "bibi",
    progress_service: ProgressService = Depends(get_progress_service),
    lesson_service: SimplifiedLessonService = Depends(get_simplified_lesson_service)
):
    """Get next interaction sequentially through all lessons"""
    try:
        # Get current progress
        progress = await progress_service.get_progress(user_id, character_id)
        if not progress:
            raise HTTPException(status_code=404, detail="Lessons not started. Call /lessons/start first.")

        # Get next interaction
        interaction = lesson_service.get_next_interaction(progress.current_lesson_index, progress.current_step_index, character_id)

        if interaction["type"] == "completed":
            # All lessons completed
            await progress_service.update_progress(user_id, character_id, progress.current_lesson_index, progress.current_step_index, True)
            return {"status": "all_completed"}

        if interaction["type"] == "lesson_completed":
            # Lesson completed, advance to next lesson
            new_lesson_index = progress.current_lesson_index + 1
            new_step_index = 0
            await progress_service.update_progress(user_id, character_id, new_lesson_index, new_step_index)
            return {
                "type": "lesson_completed",
                "lesson_id": interaction["lesson_id"],
                "lesson_title": interaction["lesson_title"],
                "next_lesson_starting": True
            }

        # If advance, update step
        if interaction["advance"]:
            new_step_index = progress.current_step_index + 1
            await progress_service.update_progress(user_id, character_id, progress.current_lesson_index, new_step_index)

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
            request.user_id, request.character_id
        )
        if not progress:
            raise HTTPException(status_code=404, detail="Lessons not started")

        # Validate answer
        result = lesson_service.validate_answer(
            progress.current_lesson_index, progress.current_step_index, request.character_id, request.answer
        )

        if result["valid"] and result["advance"]:
            # Advance to next step
            new_step_index = progress.current_step_index + 1
            # Check if this completes the lesson
            lesson = lesson_service.get_lesson_by_index(progress.current_lesson_index, request.character_id)
            if lesson and new_step_index >= len(lesson["steps"]):
                # Lesson completed, advance to next lesson
                new_lesson_index = progress.current_lesson_index + 1
                new_step_index = 0
                await progress_service.update_progress(
                    request.user_id, request.character_id, new_lesson_index, new_step_index
                )
            else:
                # Just advance step
                await progress_service.update_progress(
                    request.user_id, request.character_id, progress.current_lesson_index, new_step_index
                )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting answer: {str(e)}")

@router.get("/{character_key}")
async def get_character_lessons(character_key: str, service: SimplifiedLessonService = Depends(get_simplified_lesson_service)):
    """
    Get lesson data for a specific character.

    Args:
        character_key: The character identifier (e.g., 'bibi', 'chacha')

    Returns:
        JSON object containing all lessons for the character
    """
    try:
        lesson_data = service.get_character_data(character_key)

        if not lesson_data:
            raise HTTPException(
                status_code=404,
                detail=f"Lesson data not found for character: {character_key}"
            )

        return lesson_data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading lessons for character {character_key}: {str(e)}"
        )
