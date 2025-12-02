from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict, Any
from app.models import Lesson, LessonData
import json

class LessonService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.lessons

    async def get_character_lessons(self, character_id: str) -> Optional[LessonData]:
        """Get all lessons for a character"""
        doc = await self.collection.find_one({"characterId": character_id})
        if doc:
            return LessonData(**doc)
        return None

    async def create_lesson(self, lesson: Lesson) -> Lesson:
        """Create a new lesson for a character"""
        # Check if character lessons document exists
        existing = await self.collection.find_one({"characterId": lesson.characterId})

        if existing:
            # Add lesson to existing document
            lesson_data = LessonData(**existing)
            lesson_data.lessons.append(lesson)

            # Sort lessons by some order (you might want to add an order field)
            # For now, just append

            await self.collection.update_one(
                {"characterId": lesson.characterId},
                {"$set": {"lessons": [l.model_dump() for l in lesson_data.lessons]}}
            )
        else:
            # Create new document for character
            lesson_data = LessonData(
                characterId=lesson.characterId,
                characterName="",  # Will be set when needed
                lessons=[lesson]
            )
            await self.collection.insert_one(lesson_data.model_dump())

        return lesson

    async def insert_lesson_at_position(self, character_id: str, position: int, lesson: Lesson) -> bool:
        """Insert a lesson at a specific position, shifting others right"""
        existing = await self.collection.find_one({"characterId": character_id})
        if not existing:
            return False

        lesson_data = LessonData(**existing)
        lessons = lesson_data.lessons

        if position < 0 or position > len(lessons):
            return False

        # Insert at position
        lessons.insert(position, lesson)

        # Update in database
        await self.collection.update_one(
            {"characterId": character_id},
            {"$set": {"lessons": [l.model_dump() for l in lessons]}}
        )
        return True

    async def update_lesson(self, character_id: str, lesson_id: str, lesson_data: Dict[str, Any]) -> Optional[Lesson]:
        """Update a specific lesson"""
        existing = await self.collection.find_one({"characterId": character_id})
        if not existing:
            return None

        lesson_doc = LessonData(**existing)
        lessons = lesson_doc.lessons

        # Find and update the lesson
        for i, lesson in enumerate(lessons):
            if lesson.id == lesson_id:
                # Update lesson fields
                for key, value in lesson_data.items():
                    if hasattr(lesson, key):
                        setattr(lesson, key, value)
                break
        else:
            return None

        # Save back to database
        await self.collection.update_one(
            {"characterId": character_id},
            {"$set": {"lessons": [l.model_dump() for l in lessons]}}
        )

        return lesson

    async def delete_lesson(self, character_id: str, lesson_id: str) -> bool:
        """Delete a specific lesson"""
        existing = await self.collection.find_one({"characterId": character_id})
        if not existing:
            return False

        lesson_doc = LessonData(**existing)
        lessons = lesson_doc.lessons

        # Remove the lesson
        original_length = len(lessons)
        lessons = [l for l in lessons if l.id != lesson_id]

        if len(lessons) == original_length:
            return False  # Lesson not found

        # Save back to database
        await self.collection.update_one(
            {"characterId": character_id},
            {"$set": {"lessons": [l.model_dump() for l in lessons]}}
        )
        return True

    async def reorder_lessons(self, character_id: str, lesson_ids: List[str]) -> bool:
        """Reorder lessons by providing new order of lesson IDs"""
        existing = await self.collection.find_one({"characterId": character_id})
        if not existing:
            return False

        lesson_doc = LessonData(**existing)
        lessons = lesson_doc.lessons

        # Create mapping of id to lesson
        lesson_map = {lesson.id: lesson for lesson in lessons}

        # Reorder based on provided IDs
        reordered_lessons = []
        for lesson_id in lesson_ids:
            if lesson_id in lesson_map:
                reordered_lessons.append(lesson_map[lesson_id])

        if len(reordered_lessons) != len(lessons):
            return False  # Some lessons missing from reorder list

        # Save back to database
        await self.collection.update_one(
            {"characterId": character_id},
            {"$set": {"lessons": [l.model_dump() for l in reordered_lessons]}}
        )
        return True
