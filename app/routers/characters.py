from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.schemas import CharacterOut
from app.db import get_database
from app.services.character_service import CharacterService

router = APIRouter()

def get_character_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> CharacterService:
    return CharacterService(db)

@router.get("/", response_model=list[CharacterOut])
async def list_characters(service: CharacterService = Depends(get_character_service)):
    characters = await service.get_all_characters()
    return characters

@router.get("/{char_id}", response_model=CharacterOut)
async def get_character(char_id: str, service: CharacterService = Depends(get_character_service)):
    character = await service.get_character(char_id)
    if not character:
        raise HTTPException(status_code=404, detail="character not found")
    return character
