import json
import re
from typing import Optional, Dict, List, Any
from pathlib import Path

class SimplifiedLessonService:
    def __init__(self):
        self.lesson_data = self._load_lesson_data()

    def _load_lesson_data(self) -> Dict[str, Any]:
        """Load lesson data from static/bibi.json"""
        file_path = Path(__file__).parent.parent / ".." / "static" / "bibi.json"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise Exception(f"Error loading lesson data: {str(e)}")

    def get_next_interaction(self, lesson_id: str, current_step_index: int) -> Optional[Dict[str, Any]]:
        """Get the next interaction (question or info)"""
        lessons = self.lesson_data.get("lessons", [])
        lesson = next((l for l in lessons if l["id"] == lesson_id), None)
        if not lesson:
            return None

        steps = lesson.get("steps", [])
        if current_step_index >= len(steps):
            return {"type": "completed"}

        step = steps[current_step_index]
        lesson_type = step.get("lessonType")

        if lesson_type == "info":
            # Return info and indicate to advance
            return {
                "type": "info",
                "data": step,
                "advance": True
            }
        elif lesson_type in ["mcq", "text"]:
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

    def validate_answer(self, lesson_id: str, current_step_index: int, user_answer: str) -> Dict[str, Any]:
        """Validate user answer and return result"""
        lessons = self.lesson_data.get("lessons", [])
        lesson = next((l for l in lessons if l["id"] == lesson_id), None)
        if not lesson:
            return {"valid": False, "error": "Lesson not found"}

        steps = lesson.get("steps", [])
        if current_step_index >= len(steps):
            return {"valid": False, "error": "Lesson completed"}

        step = steps[current_step_index]
        lesson_type = step.get("lessonType")

        correct_answers = step.get("correctAnswers", [])

        # For text inputs, if no correctAnswers, try to extract expected answer from message
        if lesson_type == "text" and not correct_answers:
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
