from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from app.models import Character
from app.schemas import CharacterOut
from app.services.progress_service import ProgressService
from app.services.simplified_lesson_service import SimplifiedLessonService
from pymongo.errors import DuplicateKeyError

class CharacterService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.characters
        self.progress_service = ProgressService(db)
        self.lesson_service = SimplifiedLessonService(db)

    async def create_character(self, character: Character) -> Character:
        """Create a new character"""
        try:
            result = await self.collection.insert_one(character.model_dump())
            character.id = str(result.inserted_id)
            return character
        except DuplicateKeyError:
            raise ValueError(f"Character with id '{character.id}' already exists")

    async def get_character(self, character_id: str) -> Optional[Character]:
        """Get a character by ID"""
        doc = await self.collection.find_one({"id": character_id})
        if doc:
            return Character(**doc)
        return None

    async def get_all_characters(self) -> List[Character]:
        """Get all characters"""
        characters = []
        async for doc in self.collection.find():
            characters.append(Character(**doc))
        return characters

    async def update_character(self, character_id: str, character_data: dict) -> Optional[Character]:
        """Update a character"""
        # Remove id from update data to avoid conflicts
        update_data = {k: v for k, v in character_data.items() if k != 'id'}

        result = await self.collection.update_one(
            {"id": character_id},
            {"$set": update_data}
        )

        if result.modified_count > 0:
            return await self.get_character(character_id)
        return None

    async def delete_character(self, character_id: str) -> bool:
        """Delete a character"""
        result = await self.collection.delete_one({"id": character_id})
        return result.deleted_count > 0

    async def character_exists(self, character_id: str) -> bool:
        """Check if character exists"""
        count = await self.collection.count_documents({"id": character_id})
        return count > 0

    async def _calculate_progress_percentage(self, user_id: str, character_id: str) -> int:
        """Calculate progress percentage for a user and character"""
        # Get user's progress for this character
        user_progress = await self.progress_service.get_progress(user_id, character_id)
        if not user_progress or user_progress.completed:
            return 100 if user_progress and user_progress.completed else 0

        # Get total lessons and steps for the character
        character_data = await self.lesson_service.get_character_data(character_id)
        if not character_data:
            return 0

        lessons = character_data.get("lessons", [])
        if not lessons:
            return 0

        total_lessons = len(lessons)
        total_steps = sum(len(lesson.get("steps", [])) for lesson in lessons)

        if total_steps == 0:
            return 0

        # Calculate completed steps
        completed_lessons = user_progress.current_lesson_index
        completed_steps_in_current = user_progress.current_step_index

        # Get steps in completed lessons
        completed_steps = 0
        for i in range(completed_lessons):
            if i < total_lessons:
                completed_steps += len(lessons[i].get("steps", []))

        completed_steps += completed_steps_in_current

        return int((completed_steps / total_steps) * 100)

    async def get_all_characters_with_progress(self, user_id: str = None) -> List[CharacterOut]:
        """Get all characters with progress percentage for the user"""
        characters = await self.get_all_characters()
        result = []

        for character in characters:
            progress = 0
            if user_id:
                progress = await self._calculate_progress_percentage(user_id, character.id)

            result.append(CharacterOut(
                id=character.id,
                name=character.name,
                role=character.role,
                personality=character.personality,
                progress=progress
            ))

        return result
