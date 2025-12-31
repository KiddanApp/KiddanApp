from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, Dict, List, Any
import re
import asyncio
import difflib
from ..evaluation_pipeline import evaluation_pipeline

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
        self.conversation_history = {}  # Store conversation history per user-character pair

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

        # Extract additional notes from character message
        additional_notes = step.get("characterMessage", {}).get("additionalNotes", "")

        if lesson_type == "info":
            # Return info and indicate to advance
            return {
                "type": "info",
                "data": step,
                "advance": True,
            }
        elif lesson_type in ["mcq", "multiple-choice", "text", "text-input"]:
            # Return question, wait for answer
            return {
                "type": "question",
                "data": step,
                "advance": False,
            }
        else:
            # Unknown type, advance
            return {
                "type": "unknown",
                "advance": True,
            }

    async def validate_answer(self, current_lesson_index: int, current_step_index: int, character_id: str, user_answer: str, user_id: str) -> Dict[str, Any]:
        """Validate user answer using the three-stage evaluation pipeline with conversation context"""
        lesson = await self.get_lesson_by_index(current_lesson_index, character_id)
        if not lesson:
            return {"valid": False, "advance": False, "feedback": "Lesson not found", "emotion": "normal"}

        steps = lesson.get("steps", [])
        if current_step_index >= len(steps):
            return {"valid": False, "advance": False, "feedback": "Lesson completed", "emotion": "normal"}

        step = steps[current_step_index]
        lesson_type = step.get("lessonType")
        correct_answers = step.get("correctAnswers", [])

        # Handle empty answers
        if not user_answer.strip():
            return {"valid": False, "advance": False, "feedback": "", "retry": False, "emotion": "normal"}

        # Get conversation history for this user-character pair
        conversation_key = f"{user_id}_{character_id}"
        if conversation_key not in self.conversation_history:
            self.conversation_history[conversation_key] = []

        conversation_history = self.conversation_history[conversation_key][-3:]  # Last 3 exchanges

        # For text inputs without predefined correct answers, use AI feedback
        if lesson_type in ["text", "text-input"] and not correct_answers:
            # Extract expected answer from character message if possible
            character_message = step.get("characterMessage", {}).get("romanPunjabi", "")
            match = re.search(r'"([^"]+)"', character_message)
            if match:
                expected = match.group(1)
                correct_answers = [expected]

        # If still no correct answers, use AI evaluation
        if not correct_answers:
            ai_feedback = await self.generate_ai_feedback(user_answer, step, character_id, conversation_history)
            emotion = self._determine_feedback_emotion(ai_feedback)

            # Store this interaction in conversation history
            import time
            self.conversation_history[conversation_key].append({
                "user_answer": user_answer,
                "ai_feedback": ai_feedback,
                "timestamp": time.time()
            })

            return {
                "valid": True,  # Accept open-ended responses
                "advance": True,
                "feedback": ai_feedback,
                "retry": False,
                "emotion": emotion
            }

        # Use the three-stage evaluation pipeline with conversation context
        question_text = step.get("question", "")
        evaluation_result = await evaluation_pipeline.evaluate_answer_async(
            user_answer=user_answer,
            correct_answers_list=correct_answers,
            question_text=question_text,
            character_id=character_id,
            conversation_history=conversation_history,
            lesson_type=lesson_type
        )

        # Store this interaction in conversation history
        import time
        self.conversation_history[conversation_key].append({
            "user_answer": user_answer,
            "ai_feedback": evaluation_result.get("feedback", ""),
            "timestamp": time.time()
        })

        # Map pipeline results to service response format
        emotion = "happy" if evaluation_result["correctness"] >= 80 else "normal"
        if evaluation_result["correctness"] < 30:
            emotion = "sad"

        return {
            "valid": evaluation_result["correctness"] >= 40,  # More lenient validation for language learning
            "advance": evaluation_result["advance"],
            "feedback": evaluation_result["feedback"],
            "retry": False,  # Never force retry - allow progression
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

    async def generate_ai_feedback(self, user_answer: str, step: Dict[str, Any], character_id: str, conversation_history: List[Dict] = None) -> str:
        """Generate contextual AI feedback with character personality context - ENHANCED for better evaluation"""
        if not user_answer.strip():
            return "Jawab deo ji."

        # Load character context
        character = await self.load_character(character_id)
        if not character:
            character = {"name": "Teacher", "personality": "helpful", "role": "teacher"}

        # Extract comprehensive lesson context
        character_message = step.get("characterMessage", {}).get("romanPunjabi", "")
        question = step.get("question", "")
        correct_answers = step.get("correctAnswers", [])
        lesson_type = step.get("lessonType", "")

        # Build conversation context from previous interactions if available
        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            recent_messages = conversation_history[-3:]  # Last 3 exchanges
            conversation_context = "\nRecent conversation:\n" + "\n".join([
                f"Student: {msg.get('user_answer', '')}\n{character.get('name', 'Teacher')}: {msg.get('ai_feedback', '')}"
                for msg in recent_messages
            ])

        prompt = f"""
You are {character.get('name', 'Teacher')}, a {character.get('role', 'teacher')} with personality: {character.get('personality', 'helpful')}.

LESSON CONTEXT:
- Character's message: {character_message}
- Question asked: {question}
- Expected correct answers: {", ".join(correct_answers)}
- Question type: {lesson_type}
{conversation_context}

STUDENT ANSWER: "{user_answer}"

EVALUATION INSTRUCTIONS:
1. **PRIMARY GOAL**: Evaluate if the student's answer shows understanding of the concept, even if not perfectly worded
2. **ACCEPT** if answer demonstrates comprehension, even with:
   - Spelling variations in Roman Punjabi
   - Different word choices that convey the same meaning
   - Partial answers that address the core concept
   - Cultural/contextual understanding
3. **ACCEPT** alternative expressions that are conversationally appropriate
4. **GUIDE GENTLY** for minor mistakes - don't punish learning
5. **ONLY REJECT** if completely unrelated or shows no understanding

RESPONSE STYLE:
- Use character's personality: {character.get('speaking_style', 'friendly and encouraging')}
- Respond in Roman Punjabi only
- Be warm and supportive, like a family member teaching
- If correct: Celebrate and encourage more
- If needs help: Guide gently without frustration
- Focus on what they got right, then suggest improvements
- Keep responses conversational and natural

Your response should help the student learn while building confidence.
"""

        try:
            feedback = await self.call_gemini(prompt, max_tokens=120)
            return feedback.strip()
        except Exception as e:
            # Enhanced fallback with better contextual understanding
            if not user_answer.strip():
                return "Jawab deo ji."

            # Try to provide contextual fallback based on question type
            if lesson_type in ["mcq", "multiple-choice"]:
                # For MCQs, check if answer matches any option contextually
                normalized_user = self.normalize_text(user_answer)
                for correct in correct_answers:
                    if self.calculate_similarity(normalized_user, self.normalize_text(correct)) > 0.6:
                        return "Bahut accha! Sahi jawab."
                return f"Try karo ji. Sahi options mein se ik choose karo."

            # For text questions, provide general encouragement
            return "Bahut accha try hai. Thoda aur practice karo ji."
