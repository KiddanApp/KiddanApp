import google.generativeai as genai
from app.config import settings
from typing import Optional
import asyncio

class TranslationService:
    def __init__(self):
        pass

    async def translate_to_roman(self, text: str) -> str:
        """Translate English to Romanized Punjabi using Gemini"""
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash")

            prompt = f"""Translate this English text to Romanized Punjabi (using English letters to represent Punjabi sounds).
Keep the meaning and tone exactly the same. Use common Romanized Punjabi spellings.

English: {text}

Romanized Punjabi:"""

            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=100,
                    temperature=0.1  # Low temperature for consistent translations
                )
            )

            roman_text = response.text.strip()
            # Clean up any extra formatting
            if roman_text.startswith("Romanized Punjabi:"):
                roman_text = roman_text.replace("Romanized Punjabi:", "").strip()
            if roman_text.startswith("Roman:"):
                roman_text = roman_text.replace("Roman:", "").strip()

            return roman_text

        except Exception as e:
            print(f"Roman translation error: {e}")
            return text  # Return original text on error

    async def translate_to_gurmukhi(self, text: str) -> str:
        """Translate English to Gurmukhi Punjabi using Gemini"""
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash")

            prompt = f"""Translate this English text to Gurmukhi Punjabi script (ਪੰਜਾਬੀ ਗੁਰਮੁਖੀ ਲਿਪੀ).
Keep the meaning and tone exactly the same. Use proper Gurmukhi Unicode characters.

English: {text}

Gurmukhi Punjabi:"""

            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=100,
                    temperature=0.1  # Low temperature for consistent translations
                )
            )

            gurmukhi_text = response.text.strip()
            # Clean up any extra formatting
            if gurmukhi_text.startswith("Gurmukhi Punjabi:"):
                gurmukhi_text = gurmukhi_text.replace("Gurmukhi Punjabi:", "").strip()
            if gurmukhi_text.startswith("ਗੁਰਮੁਖੀ:"):
                gurmukhi_text = gurmukhi_text.replace("ਗੁਰਮੁਖੀ:", "").strip()

            return gurmukhi_text

        except Exception as e:
            print(f"Gurmukhi translation error: {e}")
            return text  # Return original text on error

# Global translation service instance
translation_service = TranslationService()
