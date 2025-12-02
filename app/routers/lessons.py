import json
from fastapi import APIRouter, HTTPException
from pathlib import Path

router = APIRouter()

LESSONS_PATH = Path(__file__).resolve().parents[1] / "seed" / "lessons"

@router.get("/{character_key}")
async def get_character_lessons(character_key: str):
    """
    Get lesson data for a specific character.

    Args:
        character_key: The character identifier (e.g., 'bibi', 'chacha')

    Returns:
        JSON object containing all lessons for the character
    """
    try:
        lesson_file = LESSONS_PATH / f"{character_key}.json"

        if not lesson_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Lesson data not found for character: {character_key}"
            )

        with open(lesson_file, "r", encoding="utf-8") as f:
            lesson_data = json.load(f)

        return lesson_data

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON format in lesson file for character: {character_key}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading lessons for character {character_key}: {str(e)}"
        )
