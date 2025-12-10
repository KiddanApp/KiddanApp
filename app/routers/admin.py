from fastapi import APIRouter, HTTPException, Depends, Header, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from bson import ObjectId
import json
from datetime import datetime
from app.db import get_database
from app.services.character_service import CharacterService
from app.services.lesson_service import LessonService
from app.models import Character, Lesson, LessonData
from app.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])

# Basic authentication dependency
def verify_admin_key(x_admin_key: Optional[str] = Header(None)):
    expected_key = settings.ADMIN_API_KEY or "temp"  # Allow setting via config
    if not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or missing admin key. Expected: {expected_key}"
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

@router.delete("/lessons/clear-all")
async def clear_all_lessons(
    db: AsyncIOMotorDatabase = Depends(get_database),
    admin_key: str = Depends(verify_admin_key)
):
    """Clear all lessons from MongoDB"""
    result = await db.lessons.delete_many({})
    return {
        "message": f"Cleared {result.deleted_count} lesson documents from database",
        "deleted_count": result.deleted_count
    }

@router.post("/lessons/sync-from-static")
async def sync_lessons_from_static(
    db: AsyncIOMotorDatabase = Depends(get_database),
    admin_key: str = Depends(verify_admin_key)
):
    """Sync lessons from static folder to MongoDB"""
    import json
    from pathlib import Path

    lesson_service = LessonService(db)
    synced_count = 0
    error_count = 0

    # Path to static folder
    static_path = Path(__file__).parent.parent.parent / "static"

    for lesson_file in static_path.glob("*.json"):
        if lesson_file.name == "admin.html":
            continue

        try:
            with open(lesson_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            # Transform the data to match our LessonData model expectations
            # Add missing fields to lessons and steps
            transformed_data = {
                "characterId": raw_data["characterId"],
                "characterName": raw_data.get("characterName", ""),
                "lessons": []
            }

            for lesson in raw_data["lessons"]:
                transformed_lesson = {
                    "id": lesson["id"],
                    "characterId": raw_data["characterId"],  # Add characterId to each lesson
                    "title": lesson["title"],
                    "steps": []
                }

                # Keep the steps exactly as they are in the original JSON
                transformed_lesson["steps"] = lesson["steps"]

                transformed_data["lessons"].append(transformed_lesson)

            lesson_doc = LessonData(**transformed_data)

            # Delete existing lessons for this character
            await db.lessons.delete_many({"characterId": lesson_doc.characterId})

            # Insert new lessons
            await db.lessons.insert_one(lesson_doc.model_dump())
            synced_count += 1
            print(f"Synced lessons for character: {lesson_doc.characterId}")

        except Exception as e:
            error_count += 1
            print(f"Error syncing {lesson_file.name}: {e}")

    return {
        "message": f"Synced {synced_count} lesson files, {error_count} errors",
        "synced_count": synced_count,
        "error_count": error_count
    }

# Step management endpoints
@router.put("/lessons/{character_id}/{lesson_id}/steps/{step_index}")
async def update_lesson_step(
    character_id: str,
    lesson_id: str,
    step_index: int,
    step_data: Dict[str, Any],
    service: LessonService = Depends(get_lesson_service),
    admin_key: str = Depends(verify_admin_key)
):
    """Update a specific step within a lesson"""
    success = await service.update_lesson_step(character_id, lesson_id, step_index, step_data)
    if not success:
        raise HTTPException(status_code=404, detail="Lesson or step not found")
    return {"message": "Step updated successfully"}

@router.post("/lessons/{character_id}/{lesson_id}/steps")
async def add_lesson_step(
    character_id: str,
    lesson_id: str,
    step_data: Dict[str, Any],
    service: LessonService = Depends(get_lesson_service),
    admin_key: str = Depends(verify_admin_key)
):
    """Add a new step to a lesson"""
    success = await service.add_lesson_step(character_id, lesson_id, step_data)
    if not success:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return {"message": "Step added successfully"}

@router.delete("/lessons/{character_id}/{lesson_id}/steps/{step_index}")
async def delete_lesson_step(
    character_id: str,
    lesson_id: str,
    step_index: int,
    service: LessonService = Depends(get_lesson_service),
    admin_key: str = Depends(verify_admin_key)
):
    """Delete a step from a lesson"""
    success = await service.delete_lesson_step(character_id, lesson_id, step_index)
    if not success:
        raise HTTPException(status_code=404, detail="Lesson or step not found")
    return {"message": "Step deleted successfully"}

class ReorderStepsRequest(BaseModel):
    step_indices: List[int]

@router.post("/lessons/{character_id}/{lesson_id}/steps/reorder")
async def reorder_lesson_steps(
    character_id: str,
    lesson_id: str,
    request: ReorderStepsRequest,
    service: LessonService = Depends(get_lesson_service),
    admin_key: str = Depends(verify_admin_key)
):
    """Reorder steps within a lesson"""
    success = await service.reorder_lesson_steps(character_id, lesson_id, request.step_indices)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reorder steps")
    return {"message": "Steps reordered successfully"}

# Advanced MongoDB Browser/Editor Endpoints
@router.get("/database/collections")
async def get_database_collections(
    db: AsyncIOMotorDatabase = Depends(get_database),
    admin_key: str = Depends(verify_admin_key)
):
    """Get list of all collections in the database"""
    try:
        collections = await db.list_collection_names()
        collections_info = []

        for collection_name in collections:
            collection = db[collection_name]
            count = await collection.count_documents({})
            collections_info.append({
                "name": collection_name,
                "document_count": count
            })

        return {"collections": collections_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting collections: {str(e)}")

@router.get("/database/{collection_name}/documents/{document_id}")
async def get_single_document(
    collection_name: str,
    document_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    admin_key: str = Depends(verify_admin_key)
):
    """Get a single document by ID"""
    try:
        collection = db[collection_name]
        object_id = ObjectId(document_id)
        document = await collection.find_one({"_id": object_id})

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        document["_id"] = str(document["_id"])
        return document
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting document: {str(e)}")

@router.get("/database/{collection_name}/documents")
async def get_collection_documents(
    collection_name: str,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    filter_field: Optional[str] = None,
    filter_value: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
    admin_key: str = Depends(verify_admin_key)
):
    """Get documents from a collection with optional filtering"""
    try:
        collection = db[collection_name]

        # Build query
        query = {}
        if search:
            # Simple text search across all fields
            query = {"$text": {"$search": search}}
        elif filter_field and filter_value:
            # Simple equality filter
            query[filter_field] = filter_value

        # Get documents
        cursor = collection.find(query).skip(skip).limit(limit)
        documents = []
        async for doc in cursor:
            # Add string representation of ObjectId for display
            doc["_id"] = str(doc["_id"])
            documents.append(doc)

        total_count = await collection.count_documents(query)

        return {
            "collection": collection_name,
            "documents": documents,
            "total_count": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + limit) < total_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting documents: {str(e)}")

@router.post("/database/{collection_name}/documents")
async def create_document(
    collection_name: str,
    document: Dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_database),
    admin_key: str = Depends(verify_admin_key)
):
    """Create a new document in a collection"""
    try:
        collection = db[collection_name]
        result = await collection.insert_one(document)
        document["_id"] = str(result.inserted_id)
        return {
            "message": "Document created successfully",
            "document": document,
            "inserted_id": str(result.inserted_id)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating document: {str(e)}")

@router.put("/database/{collection_name}/documents/{document_id}")
async def update_document(
    collection_name: str,
    document_id: str,
    document: Dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_database),
    admin_key: str = Depends(verify_admin_key)
):
    """Update a document in a collection"""
    try:
        collection = db[collection_name]
        object_id = ObjectId(document_id)

        # Remove _id from document if present to avoid updating it
        doc_to_update = {k: v for k, v in document.items() if k != "_id"}

        result = await collection.update_one(
            {"_id": object_id},
            {"$set": doc_to_update}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "message": "Document updated successfully",
            "modified_count": result.modified_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating document: {str(e)}")

@router.delete("/database/{collection_name}/documents/{document_id}")
async def delete_document(
    collection_name: str,
    document_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    admin_key: str = Depends(verify_admin_key)
):
    """Delete a document from a collection"""
    try:
        collection = db[collection_name]
        object_id = ObjectId(document_id)

        result = await collection.delete_one({"_id": object_id})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "message": "Document deleted successfully",
            "deleted_count": result.deleted_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")
