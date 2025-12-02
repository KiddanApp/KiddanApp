from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from app.models import Character
from pymongo.errors import DuplicateKeyError

class CharacterService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.characters

    async def create_character(self, character: Character) -> Character:
        """Create a new character"""
        try:
            result = await self.collection.insert_one(character.model_dump())
            character.id = str(result.inserted_id)
            return character
        except DuplicateKeyError:
            raise ValueError(f"Character with id '{character.id}' already exists")

    async def get_character(self, character_id: str) -> Optional[Character]:
        """Get a character by ID"""
        doc = await self.collection.find_one({"id": character_id})
        if doc:
            return Character(**doc)
        return None

    async def get_all_characters(self) -> List[Character]:
        """Get all characters"""
        characters = []
        async for doc in self.collection.find():
            characters.append(Character(**doc))
        return characters

    async def update_character(self, character_id: str, character_data: dict) -> Optional[Character]:
        """Update a character"""
        # Remove id from update data to avoid conflicts
        update_data = {k: v for k, v in character_data.items() if k != 'id'}

        result = await self.collection.update_one(
            {"id": character_id},
            {"$set": update_data}
        )

        if result.modified_count > 0:
            return await self.get_character(character_id)
        return None

    async def delete_character(self, character_id: str) -> bool:
        """Delete a character"""
        result = await self.collection.delete_one({"id": character_id})
        return result.deleted_count > 0

    async def character_exists(self, character_id: str) -> bool:
        """Check if character exists"""
        count = await self.collection.count_documents({"id": character_id})
        return count > 0
