from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.translation_service import translation_service

router = APIRouter()

class TranslationRequest(BaseModel):
    roman_punjabi_text: str

class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    translation_type: str = "roman_punjabi_to_english"

@router.post("/roman-to-english", response_model=TranslationResponse)
async def translate_roman_to_english(request: TranslationRequest):
    """
    Translate Romanized Punjabi text to English using Gemini AI

    This endpoint takes Romanized Punjabi text and returns its English translation.
    Useful for understanding Punjabi text or converting user input.
    """
    try:
        if not request.roman_punjabi_text.strip():
            raise HTTPException(status_code=400, detail="Roman Punjabi text cannot be empty")

        translated_text = await translation_service.translate_roman_to_english(request.roman_punjabi_text)

        return TranslationResponse(
            original_text=request.roman_punjabi_text,
            translated_text=translated_text,
            translation_type="roman_punjabi_to_english"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

@router.post("/test-translation")
async def test_translation():
    """
    Test endpoint to verify translation service is working
    """
    test_text = "Sat Sri Akal, ki haal hai?"
    try:
        result = await translation_service.translate_roman_to_english(test_text)
        return {
            "test_input": test_text,
            "translation_result": result,
            "status": "Translation service is working"
        }
    except Exception as e:
        return {
            "error": f"Translation service failed: {str(e)}",
            "status": "Translation service is not working"
        }
