from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Tuple
from app.models import Character, UserLessonProgress
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

    async def _calculate_question_counts(self, user_id: str, character_id: str) -> tuple[int, int]:
        """Calculate total and completed questions for a user and character
        Returns: (total_questions, completed_questions)
        """
        # Get character lesson data
        character_data = await self.lesson_service.get_character_data(character_id)
        if not character_data:
            return 0, 0

        lessons = character_data.get("lessons", [])
        if not lessons:
            return 0, 0

        # Count total questions (non-info steps)
        total_questions = 0
        for lesson in lessons:
            steps = lesson.get("steps", [])
            for step in steps:
                if step.get("lessonType") != "info":
                    total_questions += 1

        if total_questions == 0:
            return 0, 0

        # Get user's progress
        user_progress = await self.progress_service.get_progress(user_id, character_id)
        if not user_progress or user_progress.completed:
            completed_questions = total_questions if user_progress and user_progress.completed else 0
            return total_questions, completed_questions

        # Count completed questions
        completed_questions = 0
        current_lesson_idx = user_progress.current_lesson_index
        current_step_idx = user_progress.current_step_index

        for lesson_idx, lesson in enumerate(lessons):
            if lesson_idx > current_lesson_idx:
                break

            steps = lesson.get("steps", [])
            for step_idx, step in enumerate(steps):
                if step.get("lessonType") == "info":
                    continue  # Skip info steps

                if lesson_idx < current_lesson_idx or (lesson_idx == current_lesson_idx and step_idx < current_step_idx):
                    completed_questions += 1
                else:
                    break

        return total_questions, completed_questions

    async def _get_all_user_progress(self, user_id: str, character_ids: List[str]) -> List[UserLessonProgress]:
        """Get all progress records for a user and specific characters in one query"""
        return await self.progress_service.get_all_user_progress(user_id, character_ids)

    async def _get_lesson_totals(self, character_id: str) -> int:
        """Get total number of questions for a character"""
        character_data = await self.lesson_service.get_character_data(character_id)
        if not character_data:
            return 0

        lessons = character_data.get("lessons", [])
        if not lessons:
            return 0

        total_questions = 0
        for lesson in lessons:
            steps = lesson.get("steps", [])
            for step in steps:
                if step.get("lessonType") != "info":
                    total_questions += 1

        return total_questions

    async def _calculate_progress_percentage_from_data(self, user_progress: UserLessonProgress, total_steps: int) -> int:
        """Calculate progress percentage using pre-fetched data"""
        if user_progress.completed:
            return 100

        if total_steps == 0:
            return 0

        # For simplicity, we'll need to get the character data to count steps
        # This could be further optimized by pre-calculating step counts
        character_data = await self.lesson_service.get_character_data(user_progress.character_id)
        if not character_data:
            return 0

        lessons = character_data.get("lessons", [])
        if not lessons:
            return 0

        total_steps_actual = sum(len(lesson.get("steps", [])) for lesson in lessons)
        if total_steps_actual == 0:
            return 0

        # Calculate completed steps
        completed_lessons = user_progress.current_lesson_index
        completed_steps_in_current = user_progress.current_step_index

        completed_steps = 0
        for i in range(completed_lessons):
            if i < len(lessons):
                completed_steps += len(lessons[i].get("steps", []))

        completed_steps += completed_steps_in_current

        return int((completed_steps / total_steps_actual) * 100)

    async def _calculate_completed_questions_from_data(self, user_progress: UserLessonProgress, character_id: str) -> int:
        """Calculate completed questions using pre-fetched user progress"""
        if user_progress.completed:
            # Return total questions if completed
            return await self._get_lesson_totals(character_id)

        # Get character lesson data to count completed questions
        character_data = await self.lesson_service.get_character_data(character_id)
        if not character_data:
            return 0

        lessons = character_data.get("lessons", [])
        if not lessons:
            return 0

        completed_questions = 0
        current_lesson_idx = user_progress.current_lesson_index
        current_step_idx = user_progress.current_step_index

        for lesson_idx, lesson in enumerate(lessons):
            if lesson_idx > current_lesson_idx:
                break

            steps = lesson.get("steps", [])
            for step_idx, step in enumerate(steps):
                if step.get("lessonType") == "info":
                    continue  # Skip info steps

                if lesson_idx < current_lesson_idx or (lesson_idx == current_lesson_idx and step_idx < current_step_idx):
                    completed_questions += 1
                else:
                    break

        return completed_questions

    async def get_all_characters_with_progress(self, user_id: str = None) -> List[CharacterOut]:
        """Get all characters with progress data for the user"""
        characters = await self.get_all_characters()
        result = []

        # Batch load all user progress for characters to avoid N individual queries
        user_progress_cache = {}
        lesson_totals_cache = {}  # Cache total questions per character

        if user_id:
            # Get all user progress in one query
            all_progress = await self._get_all_user_progress(user_id, [char.id for char in characters])
            user_progress_cache = {p.character_id: p for p in all_progress}

            # Pre-load lesson data for all characters to avoid N individual queries
            for character in characters:
                if character.id not in lesson_totals_cache:
                    lesson_totals_cache[character.id] = await self._get_lesson_totals(character.id)

        for character in characters:
            progress = 0
            total_questions = lesson_totals_cache.get(character.id, 0)
            completed_questions = 0

            if user_id:
                user_progress = user_progress_cache.get(character.id)
                if user_progress:
                    # Calculate progress percentage
                    progress = await self._calculate_progress_percentage_from_data(user_progress, total_questions)
                    # Calculate completed questions from progress data and lesson totals
                    completed_questions = await self._calculate_completed_questions_from_data(user_progress, character.id)

            result.append(CharacterOut(
                id=character.id,
                name=character.name,
                role=character.role,
                personality=character.personality,
                progress=progress,
                total_questions=total_questions,
                completed_questions=completed_questions
            ))

        return result
