from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from app.models import UserLessonProgress

class ProgressService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.user_lesson_progress

    async def get_progress(self, user_id: str, character_id: str) -> Optional[UserLessonProgress]:
        """Get progress for a user's character lessons"""
        doc = await self.collection.find_one({
            "user_id": user_id,
            "character_id": character_id
        })
        if doc:
            return UserLessonProgress(**doc)
        return None

    async def create_progress(self, user_id: str, character_id: str) -> UserLessonProgress:
        """Create new progress record for a character"""
        progress = UserLessonProgress(
            user_id=user_id,
            character_id=character_id,
            current_lesson_index=0,
            current_step_index=0,
            completed=False
        )
        result = await self.collection.insert_one(progress.model_dump())
        progress.id = str(result.inserted_id)
        return progress

    async def update_progress(self, user_id: str, character_id: str, lesson_index: int, step_index: int, completed: bool = False):
        """Update progress for a user's character"""
        await self.collection.update_one(
            {
                "user_id": user_id,
                "character_id": character_id
            },
            {"$set": {"current_lesson_index": lesson_index, "current_step_index": step_index, "completed": completed}}
        )
