from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, Dict, List, Any
import re

class SimplifiedLessonService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        from app.services.lesson_service import LessonService
        self.lesson_service = LessonService(db)
        self.lessons_by_character = {}  # Cache for loaded lessons

    async def _get_character_data(self, character_id: str) -> Optional[Dict[str, Any]]:
        """Get character lesson data from MongoDB or cache"""
        if character_id in self.lessons_by_character:
            return self.lessons_by_character[character_id]

        lesson_data = await self.lesson_service.get_character_lessons(character_id)
        if lesson_data:
            self.lessons_by_character[character_id] = lesson_data.model_dump()
            return self.lessons_by_character[character_id]

        return None

    async def get_lesson_by_index(self, lesson_index: int, character_id: str) -> Optional[Dict[str, Any]]:
        """Get lesson by index for a character"""
        character_data = await self._get_character_data(character_id)
        if not character_data:
            return None
        lessons = character_data.get("lessons", [])
        if lesson_index >= len(lessons):
            return None
        return lessons[lesson_index]

    async def get_next_interaction(self, current_lesson_index: int, current_step_index: int, character_id: str) -> Optional[Dict[str, Any]]:
        """Get the next interaction (question or info) by indices for a character"""
        lesson = await self.get_lesson_by_index(current_lesson_index, character_id)
        if not lesson:
            return {"type": "completed"}

        steps = lesson.get("steps", [])
        if current_step_index >= len(steps):
            # Lesson completed
            return {"type": "lesson_completed", "lesson_id": lesson["id"], "lesson_title": lesson["title"]}

        step = steps[current_step_index]
        lesson_type = step.get("lessonType")

        if lesson_type == "info":
            # Return info and indicate to advance
            return {
                "type": "info",
                "data": step,
                "advance": True
            }
        elif lesson_type in ["mcq", "multiple-choice", "text", "text-input"]:
            # Return question, wait for answer
            return {
                "type": "question",
                "data": step,
                "advance": False
            }
        else:
            # Unknown type, advance
            return {
                "type": "unknown",
                "advance": True
            }

    async def validate_answer(self, current_lesson_index: int, current_step_index: int, character_id: str, user_answer: str) -> Dict[str, Any]:
        """Validate user answer and return result for a character"""
        lesson = await self.get_lesson_by_index(current_lesson_index, character_id)
        if not lesson:
            return {"valid": False, "error": "Lesson not found"}

        steps = lesson.get("steps", [])
        if current_step_index >= len(steps):
            return {"valid": False, "error": "Lesson completed"}

        step = steps[current_step_index]
        lesson_type = step.get("lessonType")

        correct_answers = step.get("correctAnswers", [])

        # For text inputs, if no correctAnswers, try to extract expected answer from message
        if lesson_type in ["text", "text-input"] and not correct_answers:
            character_message = step.get("characterMessage", {}).get("romanPunjabi", "")
            # Extract text in quotes after "Likho:" or "Type in Roman Punjabi:" phrases
            # Match text in quotes
            match = re.search(r'"([^"]+)"', character_message)
            if match:
                expected = match.group(1).strip('""').lower().strip()
                if expected and user_answer.strip().lower() == expected:
                    return {"valid": True, "advance": True, "feedback": "Correct!"}
                else:
                    return {
                        "valid": False,
                        "advance": False,
                        "feedback": f"Incorrect. Expected: {character_message}",
                        "retry": True
                    }
            else:
                # No quotes found, accept any non-empty answer
                if user_answer.strip():
                    return {"valid": True, "advance": True, "feedback": "Accepted"}
                else:
                    return {
                        "valid": False,
                        "advance": False,
                        "feedback": "Please provide an answer",
                        "retry": True
                    }

        if not correct_answers:
            # No correct answers defined
            return {"valid": True, "advance": True, "feedback": "Accepted"}

        # Normalize user_answer
        normalized_answer = user_answer.strip().lower()

        # Check if any correct answer matches
        for correct in correct_answers:
            if isinstance(correct, str) and correct.strip().lower() == normalized_answer:
                return {"valid": True, "advance": True, "feedback": "Correct!"}

        return {
            "valid": False,
            "advance": False,
            "feedback": step.get("characterMessage", {}).get("romanEnglish", "Incorrect"),
            "retry": True
        }

    async def get_character_data(self, character_id: str) -> Optional[Dict[str, Any]]:
        """Get the full character lesson data"""
        return await self._get_character_data(character_id)
