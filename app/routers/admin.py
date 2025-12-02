from fastapi import APIRouter, HTTPException, Depends, Header, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.db import get_database
from app.services.character_service import CharacterService
from app.services.lesson_service import LessonService
from app.models import Character, Lesson
from app.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])

# Basic authentication dependency
def verify_admin_key(x_admin_key: Optional[str] = Header(None)):
    if not x_admin_key or x_admin_key != settings.GEMINI_API_KEY:  # Using API key as admin key for simplicity
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin key"
        )
    return x_admin_key

def get_character_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> CharacterService:
    return CharacterService(db)

def get_lesson_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> LessonService:
    return LessonService(db)

# Character CRUD
@router.post("/characters", response_model=Character)
async def create_character(
    character: Character,
    service: CharacterService = Depends(get_character_service),
    admin_key: str = Depends(verify_admin_key)
):
    try:
        return await service.create_character(character)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/characters", response_model=List[Character])
async def list_characters_admin(
    service: CharacterService = Depends(get_character_service),
    admin_key: str = Depends(verify_admin_key)
):
    return await service.get_all_characters()

@router.get("/characters/{char_id}", response_model=Character)
async def get_character_admin(
    char_id: str,
    service: CharacterService = Depends(get_character_service),
    admin_key: str = Depends(verify_admin_key)
):
    character = await service.get_character(char_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character

@router.put("/characters/{char_id}", response_model=Character)
async def update_character(
    char_id: str,
    character_data: Dict[str, Any],
    service: CharacterService = Depends(get_character_service),
    admin_key: str = Depends(verify_admin_key)
):
    updated = await service.update_character(char_id, character_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Character not found")
    return updated

@router.delete("/characters/{char_id}")
async def delete_character(
    char_id: str,
    service: CharacterService = Depends(get_character_service),
    admin_key: str = Depends(verify_admin_key)
):
    deleted = await service.delete_character(char_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"message": "Character deleted successfully"}

# Lesson CRUD
class InsertLessonRequest(BaseModel):
    position: int
    lesson: Lesson

@router.post("/lessons", response_model=Lesson)
async def create_lesson(
    lesson: Lesson,
    service: LessonService = Depends(get_lesson_service),
    admin_key: str = Depends(verify_admin_key)
):
    return await service.create_lesson(lesson)

@router.post("/lessons/{character_id}/insert", response_model=bool)
async def insert_lesson_at_position(
    character_id: str,
    request: InsertLessonRequest,
    service: LessonService = Depends(get_lesson_service),
    admin_key: str = Depends(verify_admin_key)
):
    success = await service.insert_lesson_at_position(character_id, request.position, request.lesson)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to insert lesson at position")
    return True

@router.put("/lessons/{character_id}/{lesson_id}", response_model=Lesson)
async def update_lesson(
    character_id: str,
    lesson_id: str,
    lesson_data: Dict[str, Any],
    service: LessonService = Depends(get_lesson_service),
    admin_key: str = Depends(verify_admin_key)
):
    updated = await service.update_lesson(character_id, lesson_id, lesson_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return updated

@router.delete("/lessons/{character_id}/{lesson_id}")
async def delete_lesson(
    character_id: str,
    lesson_id: str,
    service: LessonService = Depends(get_lesson_service),
    admin_key: str = Depends(verify_admin_key)
):
    deleted = await service.delete_lesson(character_id, lesson_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return {"message": "Lesson deleted successfully"}

class ReorderLessonsRequest(BaseModel):
    lesson_ids: List[str]

@router.post("/lessons/{character_id}/reorder")
async def reorder_lessons(
    character_id: str,
    request: ReorderLessonsRequest,
    service: LessonService = Depends(get_lesson_service),
    admin_key: str = Depends(verify_admin_key)
):
    success = await service.reorder_lessons(character_id, request.lesson_ids)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reorder lessons")
    return {"message": "Lessons reordered successfully"}

@router.get("/lessons/{character_id}")
async def get_character_lessons_admin(
    character_id: str,
    service: LessonService = Depends(get_lesson_service),
    admin_key: str = Depends(verify_admin_key)
):
    lessons = await service.get_character_lessons(character_id)
    if not lessons:
        raise HTTPException(status_code=404, detail="Lessons not found for character")
    return lessons.model_dump()
