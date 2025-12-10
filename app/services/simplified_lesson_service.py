from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, Dict, List, Any
import re
import asyncio

class SimplifiedLessonService:
    def normalize_text(self, text: str) -> str:
        """Comprehensive text normalization for better matching in language learning."""
        if not text:
            return ""

        # Remove punctuation (keep alphanumeric, whitespace, and Punjabi script)
        clean = re.sub(r'[^\w\s\u0A80-\u0AFF]', '', text)

        # Normalize multiple whitespaces to single space
        clean = ' '.join(clean.split())

        # Case normalization
        clean = clean.lower()

        return clean.strip()
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        from app.services.lesson_service import LessonService
        self.lesson_service = LessonService(db)
        self.lessons_by_character = {}  # Cache for loaded lessons
        self.characters_by_id = {}  # Cache for loaded characters
        from app.services.ai_service import call_gemini, load_character
        self.call_gemini = call_gemini
        self.load_character = load_character

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
            return {"valid": False, "advance": False, "feedback": "Lesson not found", "emotion": "normal"}

        steps = lesson.get("steps", [])
        if current_step_index >= len(steps):
            return {"valid": False, "advance": False, "feedback": "Lesson completed", "emotion": "normal"}

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
                expected = match.group(1)  # Keep the original text for feedback
                if expected and self.normalize_text(user_answer) == self.normalize_text(expected):
                    return {"valid": True, "advance": True, "feedback": "Correct!", "retry": False, "emotion": "happy"}
                else:
                    # Generate AI feedback for text input answers
                    ai_feedback = await self.generate_ai_feedback(user_answer, step, character_id)
                    emotion = self._determine_feedback_emotion(ai_feedback)
                    return {
                        "valid": False,
                        "advance": False,
                        "feedback": ai_feedback,
                        "retry": True,
                        "emotion": emotion
                    }
            else:
                # No quotes found, accept any non-empty answer
                if user_answer.strip():
                    return {"valid": True, "advance": True, "feedback": "Accepted", "retry": False, "emotion": "normal"}
                else:
                    return {
                        "valid": False,
                        "advance": False,
                        "feedback": "Please provide an answer",
                        "retry": True,
                        "emotion": "normal"
                    }

        if not correct_answers:
            # No correct answers defined
            return {"valid": True, "advance": True, "feedback": "Accepted", "retry": False, "emotion": "normal"}

        # Normalize user_answer using comprehensive normalization
        normalized_answer = self.normalize_text(user_answer)

        # Check if any correct answer matches (also normalize correct answers)
        for correct in correct_answers:
            if isinstance(correct, str) and self.normalize_text(correct) == normalized_answer:
                return {"valid": True, "advance": True, "feedback": "Correct!", "retry": False, "emotion": "happy"}

        # Generate contextual AI feedback for wrong answers
        ai_feedback = await self.generate_ai_feedback(user_answer, step, character_id)

        # Determine emotion from the generated feedback
        emotion = self._determine_feedback_emotion(ai_feedback)

        return {
            "valid": False,
            "advance": False,
            "feedback": ai_feedback,
            "retry": True,
            "emotion": emotion
        }

    async def get_character_data(self, character_id: str) -> Optional[Dict[str, Any]]:
        """Get the full character lesson data"""
        return await self._get_character_data(character_id)

    def _determine_feedback_emotion(self, feedback: str) -> str:
        """Determine emotion from feedback text (includes both English and Roman Punjabi keywords)"""
        feedback_lower = feedback.lower()

        # Check for emotion keywords in the feedback (English and Roman Punjabi)
        if any(word in feedback_lower for word in ["happy", "great", "wonderful", "love", "excited", "wah", "bahut vadiya", "shabaash", "bahut accha", "vaah", "great"]):
            return "happy"
        elif any(word in feedback_lower for word in ["angry", "upset", "sorry", "wrong", "bad", "mad", "frustrated", "galat", "kush nahi", "suit nahi karta", "galat nahi", "wrong nahi"]):
            return "angry"
        elif any(word in feedback_lower for word in ["sad", "unhappy", "disappointed", "heartbroken", "depressed", "unfortunate", "dukhi", "naraaz", "gam", "dard"]):
            return "sad"
        else:
            return "normal"

    async def generate_ai_feedback(self, user_answer: str, step: Dict[str, Any], character_id: str) -> str:
        """Generate contextual AI feedback with character personality context in Roman Punjabi only."""
        if not user_answer.strip():
            return "Jawab deo ji."

        # Load character context
        character = await self.load_character(character_id)
        if not character:
            character = {"name": "Teacher", "personality": "helpful", "role": "teacher"}

        # Extract lesson context
        character_message = step.get("characterMessage", {}).get("romanPunjabi", "")
        question = step.get("question", "")
        correct_answers = step.get("correctAnswers", [])

        prompt = f"""
You are {character.get('name', 'Teacher')}, a {character.get('role', 'teacher')} with personality: {character.get('personality', 'helpful')}.

Lesson Context:
Question: {question}
Expected Answers: {", ".join(correct_answers)}
Student Answer: {user_answer}

Validation Rules:
1. ACCEPT answers that are contextually appropriate, even if not exact matches
2. ACCEPT answers that show understanding of the concept in Punjabi
3. ACCEPT alternative valid ways to express the same idea
4. Only CORRECT if the answer is completely incorrect for context

Feedback Instructions:
- Use character's personality and speaking style: {character.get('speaking_style', 'friendly')}
- If answer is acceptable: Accept it warmly and encourage
- If needs small corrections: Suggest improvements helpfully
- If completely wrong: Guide towards correct understanding
- Respond ONLY in Roman Punjabi using character's speaking pattern

Character's typical responses would be: {character.get('conversation_topics', 'warm, encouraging')}

Generate feedback in character's voice:
"""

        try:
            feedback = await self.call_gemini(prompt, max_tokens=100)
            return feedback.strip()
        except Exception as e:
            # Fallback in Roman Punjabi
            return "Theek hai ji, continue karo."
