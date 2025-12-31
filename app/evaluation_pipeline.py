"""
Three-Stage Evaluation Pipeline for KiddanApp Language Learning
Implements the exact evaluation logic specified in requirements.
"""
import re
import difflib
from typing import Dict, List, Optional

try:
    from app.services.ai_service import call_gemini, load_character
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    call_gemini = None
    load_character = None


class EvaluationPipeline:
    def __init__(self):
        self.ai_call_gemini = call_gemini
        self.ai_load_character = load_character

    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison: lowercase, remove punctuation, normalize spaces."""
        if not text:
            return ""

        # Remove punctuation (keep alphanumeric and Punjabi script)
        clean = re.sub(r'[^\w\s\u0A80-\u0AFF]', '', text)
        # Normalize multiple whitespaces to single space
        clean = ' '.join(clean.split())
        # Case normalization
        clean = clean.lower()
        return clean.strip()

    def string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity ratio between two strings."""
        return difflib.SequenceMatcher(None, str1, str2).ratio()

    async def ai_evaluate(self, question_text: str, user_answer: str, correct_answer: str, character_id: str = None, conversation_history: List[Dict] = None) -> Dict:
        """
        AI evaluation for ambiguous cases with character personality and conversation context.
        Returns: {'ai_correctness': float, 'ai_feedback': str}
        """
        try:
            # Load character for contextual feedback
            character = await self.ai_load_character(character_id) if character_id else None
            if not character:
                character = {
                    'name': 'Teacher',
                    'personality': 'helpful',
                    'role': 'teacher',
                    'speaking_style': 'friendly and encouraging'
                }

            # Build conversation context (last 3 exchanges)
            conversation_context = ""
            if conversation_history and len(conversation_history) > 0:
                recent_exchanges = conversation_history[-3:]  # Last 3 exchanges
                conversation_lines = []
                for exchange in recent_exchanges:
                    user_msg = exchange.get('user_answer', exchange.get('user_message', ''))
                    ai_msg = exchange.get('ai_feedback', exchange.get('ai_message_roman', ''))
                    if user_msg and ai_msg:
                        conversation_lines.append(f"Student: {user_msg}")
                        conversation_lines.append(f"{character.get('name', 'Teacher')}: {ai_msg}")
                if conversation_lines:
                    conversation_context = "\nRecent conversation:\n" + "\n".join(conversation_lines) + "\n"

            prompt = f"""You are {character.get('name', 'Teacher')}, a {character.get('role', 'teacher')} with {character.get('personality', 'helpful')} personality.

QUESTION: "{question_text}"
STUDENT ANSWER: "{user_answer}"
CORRECT ANSWER: "{correct_answer}"
{conversation_context}

EVALUATION TASK:
Compare the student's answer with the correct answer. Consider spelling variations, similar meanings, and cultural context in Punjabi learning.

RESPONSE GUIDELINES:
- Respond as {character.get('name', 'Teacher')} in a {character.get('speaking_style', 'friendly and encouraging')} way
- Use Roman Punjabi only (no English)
- Keep it conversational, like talking to a family member
- If mostly correct: Encourage and gently suggest improvements
- If wrong: Guide helpfully without being harsh, maintain the learning spirit
- Reference previous conversation if relevant
- Be concise but warm (max 3 sentences)
- Show {character.get('personality', 'helpful')} personality traits

Your response:"""

            ai_response = await self.ai_call_gemini(prompt, max_tokens=100)

            # Estimate correctness based on AI response content
            response_lower = ai_response.lower()
            if any(word in response_lower for word in ['sahi', 'accha', 'bahut', 'shabaash', 'correct']):
                ai_correctness = 75.0  # Positive feedback suggests higher correctness
            elif any(word in response_lower for word in ['try', 'kar', 'galat', 'wrong', 'check']):
                ai_correctness = 45.0  # Suggestive feedback suggests moderate correctness
            else:
                ai_correctness = 60.0  # Default for AI intervention

            return {
                'ai_correctness': ai_correctness,
                'ai_feedback': ai_response.strip()
            }

        except Exception as e:
            # Character-specific fallback
            char_name = "Teacher"
            if character_id and self.ai_load_character:
                try:
                    char = await self.ai_load_character(character_id)
                    char_name = char.get('name', 'Teacher') if char else 'Teacher'
                except:
                    pass

            return {
                'ai_correctness': 50.0,
                'ai_feedback': f"{char_name} kehta hai: Sahi jawab check kar ke dubara try karo ji."
            }

    async def evaluate_answer_async(
        self,
        user_answer: str,
        correct_answers_list: List[str],
        question_text: str = "",
        character_id: str = None,
        conversation_history: List[Dict] = None
    ) -> Dict:
        """
        Async version of evaluation pipeline implementing the three-stage process.
        Returns: {
            'correctness': float (0-100),
            'advance': bool,
            'feedback': str
        }
        """
        # Handle empty answers
        if not user_answer.strip():
            return {
                'correctness': 0,
                'advance': False,
                'feedback': "please provide an answer."
            }

        # Normalize inputs
        normalized_user = self.normalize_text(user_answer)
        normalized_corrects = [self.normalize_text(ans) for ans in correct_answers_list]

        # STAGE 1: EXACT MATCH (FAST PASS)
        for correct in normalized_corrects:
            if normalized_user == correct:
                return {
                    'correctness': 100,
                    'advance': True,
                    'feedback': "Bilkul sahi jawab."
                }

        # STAGE 2: PARTIAL STRING MATCH SCORING
        best_match_score = 0.0
        best_correct_answer = correct_answers_list[0] if correct_answers_list else ""

        for i, correct in enumerate(normalized_corrects):
            score = self.string_similarity(normalized_user, correct)
            if score > best_match_score:
                best_match_score = score
                best_correct_answer = correct_answers_list[i]

        correctness = round(best_match_score * 100)

        # STAGE 3: AI FALLBACK (IF NEEDED)
        feedback = ""
        if  0 <= correctness < 100:
            # Run AI evaluation asynchronously
            ai_result = await self.ai_evaluate(question_text, user_answer, best_correct_answer, character_id)

            # Blend scores (controlled adjustment)
            ai_correctness = ai_result['ai_correctness']
            correctness = min(100, max(0, round((correctness * 0.7) + (ai_correctness * 0.3))))
            feedback = ai_result['ai_feedback']

        # STAGE 4: ADVANCE DECISION (More lenient for language learning)
        advance = correctness >= 50

        # STAGE 5: FEEDBACK CONTROL
        # if correctness < 30:
        #     feedback = "please try again."

        return {
            'correctness': correctness,
            'advance': advance,
            'feedback': feedback
        }

    def evaluate_answer(
        self,
        user_answer: str,
        correct_answers_list: List[str],
        question_text: str = "",
        character_id: str = None
    ) -> Dict:
        """
        Synchronous wrapper for backward compatibility.
        """
        import asyncio
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in a running event loop, we need to handle this differently
                # For now, skip AI evaluation in sync mode when in event loop
                return self._evaluate_answer_sync(user_answer, correct_answers_list, question_text, character_id)
            else:
                # If no running loop, we can use asyncio.run
                return loop.run_until_complete(self.evaluate_answer_async(user_answer, correct_answers_list, question_text, character_id))
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(self.evaluate_answer_async(user_answer, correct_answers_list, question_text, character_id))

    def _evaluate_answer_sync(
        self,
        user_answer: str,
        correct_answers_list: List[str],
        question_text: str = "",
        character_id: str = None
    ) -> Dict:
        """
        Synchronous evaluation without AI (for when we're in an async context).
        """
        # Handle empty answers
        if not user_answer.strip():
            return {
                'correctness': 0,
                'advance': False,
                'feedback': "please provide an answer."
            }

        # Normalize inputs
        normalized_user = self.normalize_text(user_answer)
        normalized_corrects = [self.normalize_text(ans) for ans in correct_answers_list]

        # STAGE 1: EXACT MATCH (FAST PASS)
        for correct in normalized_corrects:
            if normalized_user == correct:
                return {
                    'correctness': 100,
                    'advance': True,
                    'feedback': "Bilkul sahi jawab."
                }

        # STAGE 2: PARTIAL STRING MATCH SCORING
        best_match_score = 0.0
        best_correct_answer = correct_answers_list[0] if correct_answers_list else ""

        for i, correct in enumerate(normalized_corrects):
            score = self.string_similarity(normalized_user, correct)
            if score > best_match_score:
                best_match_score = score
                best_correct_answer = correct_answers_list[i]

        correctness = round(best_match_score * 100)

        # STAGE 3: AI FALLBACK (SKIP IN SYNC MODE WHEN IN EVENT LOOP)
        feedback = ""
        # Skip AI evaluation in sync mode to avoid event loop issues

        # STAGE 4: ADVANCE DECISION (More lenient for language learning)
        advance = correctness >= 50

        # STAGE 5: FEEDBACK CONTROL

        return {
            'correctness': correctness,
            'advance': advance,
            'feedback': feedback
        }


# Global instance for use in services
evaluation_pipeline = EvaluationPipeline()


# Convenience function for integration
async def evaluate_answer_async(
    user_answer: str,
    correct_answers_list: List[str],
    question_text: str = "",
    character_id: str = None
) -> Dict:
    """Async wrapper for evaluation pipeline."""
    return evaluation_pipeline.evaluate_answer(
        user_answer, correct_answers_list, question_text, character_id
    )


if __name__ == "__main__":
    # Test the pipeline
    pipeline = EvaluationPipeline()
