from fastapi import APIRouter, HTTPException
from app.schemas import CharacterOut
import json
from pathlib import Path

router = APIRouter()
CHAR_PATH = Path(__file__).resolve().parents[1] / "seed" / "characters.json"

@router.get("/", response_model=list[CharacterOut])
async def list_characters():
    with open(CHAR_PATH, "r", encoding="utf8") as f:
        chars = json.load(f)
    return [chars[k] for k in chars]

@router.get("/{char_id}", response_model=CharacterOut)
async def get_character(char_id: str):
    with open(CHAR_PATH, "r", encoding="utf8") as f:
        chars = json.load(f)
    if char_id not in chars:
        raise HTTPException(status_code=404, detail="character not found")
    return chars[char_id]
