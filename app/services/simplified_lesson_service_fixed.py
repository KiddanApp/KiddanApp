from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, Dict, List, Any
import re
import asyncio
import difflib

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

    def calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity ratio between two strings using SequenceMatcher."""
        return difflib.SequenceMatcher(None, str1, str2).ratio()

    def generate_mistake_feedback(self, user_answer: str, correct_answer: str) -> str:
        """Generate feedback highlighting mistakes in Roman Punjabi."""
        # Use difflib.ndiff to find differences at word level
        diff = list(difflib.ndiff(correct_answer.split(), user_answer.split()))

        # Collect mistakes
        mistakes = []
        for item in diff:
            if item.startswith('- '):
                # Missing from user answer
                mistakes.append(f"missing: {item[2:]}")
            elif item.startswith('+ '):
                # Extra in user answer
                mistakes.append(f"extra: {{{item[2:]}}}")

        if mistakes:
            wrong_text = ', '.join(mistakes)
            feedback = f"Ye galat hai Roman Punjabi mein. Tumne likha: \"{user_answer}\". Galat hissa: {wrong_text}"
        else:
            feedback = f"Ye galat hai Roman Punjabi mein. Tumne likha: \"{user_answer}\". Sahi jawab: \"{correct_answer}\""

        return feedback
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
        """Validate user answer and return result for a character - FIXED to allow progression"""
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
                    # Generate AI feedback for text input answers - FIXED to allow progression
                    ai_feedback = await self.generate_ai_feedback(user_answer, step, character_id)
                    emotion = self._determine_feedback_emotion(ai_feedback)
                    return {
                        "valid": False,
                        "advance": True,  # FIXED: Allow progression
                        "feedback": ai_feedback,
                        "retry": False,   # FIXED: Don't force retry
                        "emotion": emotion
                    }
            else:
                # No quotes found, accept any non-empty answer
                if user_answer.strip():
                    return {"valid": True, "advance": True, "feedback": "Accepted", "retry": False, "emotion": "normal"}
                else:
                    return {
                        "valid": False,
                        "advance": True,  # FIXED: Allow progression even for empty answers
                        "feedback": "Please provide an answer",
                        "retry": False,   # FIXED: Don't force retry
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

        # Find the best matching correct answer
        best_similarity = 0.0
        best_correct = ""
        for correct in correct_answers:
            if isinstance(correct, str):
                sim = self.calculate_similarity(normalized_answer, self.normalize_text(correct))
                if sim > best_similarity:
                    best_similarity = sim
                    best_correct = correct

        # If similarity > 60%, generate mistake feedback
        if best_similarity > 0.6:
            feedback = self.generate_mistake_feedback(user_answer, best_correct)
            emotion = "normal"  # Since it's showing mistakes, neutral emotion
            # Allow AI to override if contextually correct
            ai_feedback = await self.generate_ai_feedback(user_answer, step, character_id)
            ai_emotion = self._determine_feedback_emotion(ai_feedback)
            if ai_emotion == "happy":
                # AI says correct, so accept
                return {"valid": True, "advance": True, "feedback": "Correct!", "retry": False, "emotion": "happy"}
            else:
                # FIXED: Allow progression with educational feedback
                return {
                    "valid": False,
                    "advance": True,  # FIXED: Allow progression
                    "feedback": feedback,
                    "retry": False,   # FIXED: Don't force retry
                    "emotion": emotion
                }
        else:
            # Low similarity, use AI feedback - FIXED to allow progression
            ai_feedback = await self.generate_ai_feedback(user_answer, step, character_id)
            emotion = self._determine_feedback_emotion(ai_feedback)
            if emotion == "happy":
                # AI accepts contextually
                return {"valid": True, "advance": True, "feedback": ai_feedback, "retry": False, "emotion": emotion}
            else:
                # FIXED: Allow progression with feedback for learning
                return {
                    "valid": False,
                    "advance": True,  # FIXED: Allow progression
                    "feedback": ai_feedback,
                    "retry": False,   # FIXED: Don't force retry
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
4. REJECT answers that are completely unrelated or show no understanding

Feedback Instructions:
- Use character's personality and speaking style: {character.get('speaking_style', 'friendly')}
- If answer is acceptable: Accept it warmly and encourage
- If needs small corrections: Suggest improvements helpfully
- If completely wrong/unrelated: Clearly indicate it's incorrect and guide towards the right answer
- Respond ONLY in Roman Punjabi using character's speaking pattern
- For wrong answers, be educational and point to the correct answer

Character's typical responses would be: {character.get('conversation_topics', 'warm, encouraging')}

Generate feedback in character's voice:
"""

        try:
            feedback = await self.call_gemini(prompt, max_tokens=100)
            return feedback.strip()
        except Exception as e:
            # Fallback feedback based on context - provide educational correction
            if not user_answer.strip():
                return "Jawab deo ji."
            else:
                # For wrong answers, provide correction guidance
                correct_text = ", ".join(correct_answers) if correct_answers else "sahi jawab"
                return f"Ye galat hai. Sahi jawab '{correct_text}' hai. Try karo ji."
