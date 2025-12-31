"""
Three-Stage Evaluation Pipeline for KiddanApp Language Learning
Implements the exact evaluation logic specified in requirements.
"""
import re
import difflib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from app.services.ai_service import call_gemini, load_character
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    call_gemini = None
    load_character = None


class EvaluationState(Enum):
    PERFECT = "perfect"
    ACCEPTABLE = "acceptable"
    PARTIAL = "partial"
    WRONG = "wrong"


@dataclass
class EvaluationResult:
    state: EvaluationState
    advance: bool
    feedback: str
    confidence: Optional[float] = None


@dataclass
class Thresholds:
    auto_pass: float
    ai_zone_low: float
    accept_states: List[EvaluationState]


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

    def sequence_similarity(self, str1: str, str2: str) -> float:
        """Calculate sequence similarity between two strings."""
        return difflib.SequenceMatcher(None, str1, str2).ratio()

    def token_overlap(self, str1: str, str2: str) -> float:
        """Calculate token overlap similarity."""
        tokens1 = set(str1.split())
        tokens2 = set(str2.split())
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        return len(intersection) / len(union)

    def get_thresholds(self, lesson_type: str) -> Thresholds:
        """Get thresholds based on lesson type."""
        if lesson_type == "mcq":
            return Thresholds(
                auto_pass=0.95,
                ai_zone_low=0.50,
                accept_states=[EvaluationState.PERFECT]
            )
        elif lesson_type == "text":
            return Thresholds(
                auto_pass=0.90,
                ai_zone_low=0.40,
                accept_states=[EvaluationState.PERFECT, EvaluationState.ACCEPTABLE]
            )
        elif lesson_type == "translation":
            return Thresholds(
                auto_pass=0.88,
                ai_zone_low=0.35,
                accept_states=[EvaluationState.PERFECT, EvaluationState.ACCEPTABLE]
            )
        else:
            # Conservative defaults
            return Thresholds(
                auto_pass=0.85,
                ai_zone_low=0.45,
                accept_states=[EvaluationState.PERFECT, EvaluationState.ACCEPTABLE]
            )

    def heuristic_score(self, user_answer: str, correct_answers: List[str]) -> float:
        """Calculate heuristic similarity score."""
        normalized_user = self.normalize_text(user_answer)
        best_score = 0.0

        for correct in correct_answers:
            normalized_correct = self.normalize_text(correct)

            seq_score = self.sequence_similarity(normalized_user, normalized_correct)
            token_score = self.token_overlap(normalized_user, normalized_correct)

            combined = (0.6 * seq_score) + (0.4 * token_score)
            best_score = max(best_score, combined)

        return best_score

    async def ai_evaluate(self, context: Dict) -> Tuple[EvaluationState, str]:
        """
        AI evaluation using Gemini with explicit rubric.
        Returns: (state, feedback)
        """
        try:
            # Check if AI is available
            if not AI_AVAILABLE or not self.ai_call_gemini:
                # Fallback to heuristic-based evaluation
                char_name = "Teacher"
                if context.get('character'):
                    char_name = context['character'].get('name', 'Teacher')
                return EvaluationState.ACCEPTABLE, f"{char_name} kehta hai: Sahi jawab check kar ke dubara try karo ji."

            character = context.get('character')
            if not character:
                character = {
                    'name': 'Teacher',
                    'personality': 'helpful',
                    'role': 'teacher',
                    'speaking_style': 'friendly and encouraging'
                }

            # Build conversation context
            conversation_context = ""
            if context.get('chat_history'):
                recent_exchanges = context['chat_history'][-3:]
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

QUESTION: "{context.get('question_text', '')}"
STUDENT ANSWER: "{context.get('user_answer', '')}"
CORRECT ANSWER(S): {', '.join(context.get('correct_answers', []))}
{conversation_context}

EVALUATION TASK:
Classify the answer as ONE of these categories:
- PERFECT: Answer is completely correct, matches meaning exactly
- ACCEPTABLE: Answer has minor issues but meaning is correct
- PARTIAL: Answer has some correct meaning but is incomplete or has errors
- WRONG: Answer is incorrect or irrelevant

Then give SHORT feedback in Roman Punjabi, matching {character.get('name', 'Teacher')}'s personality.

RESPONSE FORMAT:
First line: One word classification (PERFECT/ACCEPTABLE/PARTIAL/WRONG)
Then: Feedback in Roman Punjabi (max 2 sentences)"""

            ai_response = await self.ai_call_gemini(prompt, max_tokens=100)

            # Parse response
            lines = ai_response.strip().split('\n', 1)
            if len(lines) >= 2:
                classification = lines[0].strip().upper()
                feedback = lines[1].strip()
            else:
                classification = "ACCEPTABLE"
                feedback = ai_response.strip()

            # Map to enum
            state_map = {
                "PERFECT": EvaluationState.PERFECT,
                "ACCEPTABLE": EvaluationState.ACCEPTABLE,
                "PARTIAL": EvaluationState.PARTIAL,
                "WRONG": EvaluationState.WRONG
            }
            state = state_map.get(classification, EvaluationState.ACCEPTABLE)

            return state, feedback

        except Exception as e:
            # Fallback - AI failed, use heuristic-based response
            char_name = "Teacher"
            if context.get('character'):
                char_name = context['character'].get('name', 'Teacher')

            return EvaluationState.ACCEPTABLE, f"{char_name} kehta hai: Sahi jawab check kar ke dubara try karo ji."

    def polish_feedback(self, state: EvaluationState, advance: bool, ai_feedback: str, character: Dict) -> str:
        """Polish feedback based on state and advancement decision."""
        if not character:
            character = {'name': 'Teacher'}

        char_name = character.get('name', 'Teacher')

        if advance and state == EvaluationState.ACCEPTABLE:
            if ai_feedback:
                return f"Vadia! {ai_feedback} Agge vadh, bas eh gall yaad rakh..."
            else:
                return f"{char_name}: Shabaash! Sahi jawab. Agge vadh."

        if advance and state == EvaluationState.PERFECT:
            return f"{char_name}: Bilkul sahi! Shabaash!"

        if not advance and state == EvaluationState.PARTIAL:
            if ai_feedback:
                return f"{char_name}: {ai_feedback} Thoda aur try kar."
            else:
                return f"{char_name}: Thoda aur sahi banake dubara try karo ji."

        if not advance:
            if ai_feedback:
                return f"{char_name}: {ai_feedback}"
            else:
                return f"{char_name}: Dubara try karo ji."

        # Default fallback
        return f"{char_name}: Sahi jawab check karo ji."

    async def evaluate_answer(
        self,
        user_answer: str,
        correct_answers_list: List[str],
        question_text: str,
        lesson_type: str,
        character_id: str = None,
        chat_history: List[Dict] = None
    ) -> EvaluationResult:
        """
        Main evaluation pipeline implementing the three-stage process.
        """
        # Handle empty answers
        if not user_answer.strip():
            return EvaluationResult(
                state=EvaluationState.WRONG,
                advance=False,
                feedback="Jawab likho ji."
            )

        thresholds = self.get_thresholds(lesson_type)
        heuristic = self.heuristic_score(user_answer, correct_answers_list)

        # FAST PASS (CLEARLY CORRECT)
        if heuristic >= thresholds.auto_pass:
            character = await self.ai_load_character(character_id) if character_id and self.ai_load_character else None
            feedback = self.polish_feedback(EvaluationState.PERFECT, True, "", character)
            return EvaluationResult(
                state=EvaluationState.PERFECT,
                advance=True,
                feedback=feedback,
                confidence=heuristic
            )

        # FAST FAIL (CLEARLY WRONG)
        if heuristic < thresholds.ai_zone_low:
            character = await self.ai_load_character(character_id) if character_id and self.ai_load_character else None
            feedback = self.polish_feedback(EvaluationState.WRONG, False, "", character)
            return EvaluationResult(
                state=EvaluationState.WRONG,
                advance=False,
                feedback=feedback,
                confidence=heuristic
            )

        # AI DECIDES (AMBIGUOUS ZONE)
        character = await self.ai_load_character(character_id) if character_id and self.ai_load_character else None
        context = {
            'user_answer': user_answer,
            'correct_answers': correct_answers_list,
            'question_text': question_text,
            'chat_history': chat_history or [],
            'character': character
        }

        state, ai_feedback = await self.ai_evaluate(context)

        # PROGRESSION DECISION
        advance = state in thresholds.accept_states

        # FEEDBACK RECONCILIATION
        feedback = self.polish_feedback(state, advance, ai_feedback, character)

        return EvaluationResult(
            state=state,
            advance=advance,
            feedback=feedback,
            confidence=heuristic
        )

    # BACKWARD COMPATIBILITY METHODS

    async def evaluate_answer_async(
        self,
        user_answer: str,
        correct_answers_list: List[str],
        question_text: str = "",
        character_id: str = None,
        conversation_history: List[Dict] = None,
        lesson_type: str = None
    ) -> Dict:
        """
        Async wrapper for backward compatibility.
        """
        try:
            print(f"DEBUG: evaluate_answer_async called with user_answer='{user_answer[:50]}...', lesson_type={lesson_type}")

            # Default lesson_type if not provided
            if lesson_type is None:
                lesson_type = "text"  # Most common
                print(f"DEBUG: Using default lesson_type='{lesson_type}'")

            print(f"DEBUG: Calling evaluate_answer with lesson_type='{lesson_type}'")
            result = await self.evaluate_answer(
                user_answer=user_answer,
                correct_answers_list=correct_answers_list,
                question_text=question_text,
                lesson_type=lesson_type,
                character_id=character_id,
                chat_history=conversation_history
            )

            print(f"DEBUG: evaluate_answer returned: state={result.state}, advance={result.advance}")

            # Convert to old format
            correctness = {
                EvaluationState.PERFECT: 100,
                EvaluationState.ACCEPTABLE: 75,
                EvaluationState.PARTIAL: 45,
                EvaluationState.WRONG: 25
            }.get(result.state, 60)

            response = {
                'correctness': correctness,
                'advance': result.advance,
                'feedback': result.feedback
            }
            print(f"DEBUG: Returning response: {response}")
            return response

        except Exception as e:
            print(f"DEBUG: Exception in evaluate_answer_async: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

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
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Skip AI evaluation in sync mode when in event loop
                return self._evaluate_answer_sync(user_answer, correct_answers_list, question_text, character_id)
            else:
                return loop.run_until_complete(self.evaluate_answer_async(user_answer, correct_answers_list, question_text, character_id))
        except RuntimeError:
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
        for correct in normalized_corrects:
            score = self.sequence_similarity(normalized_user, correct)
            if score > best_match_score:
                best_match_score = score

        correctness = round(best_match_score * 100)

        # STAGE 4: ADVANCE DECISION (More lenient for language learning)
        advance = correctness >= 50

        return {
            'correctness': correctness,
            'advance': advance,
            'feedback': ""
        }


# Global instance for use in services
evaluation_pipeline = EvaluationPipeline()


# Convenience function for integration
async def evaluate_answer_async(
    user_answer: str,
    correct_answers_list: List[str],
    question_text: str = "",
    character_id: str = None,
    lesson_type: str = None
) -> Dict:
    """Async wrapper for evaluation pipeline."""
    return await evaluation_pipeline.evaluate_answer_async(
        user_answer, correct_answers_list, question_text, character_id, lesson_type=lesson_type
    )


if __name__ == "__main__":
    # Test the pipeline
    pipeline = EvaluationPipeline()
