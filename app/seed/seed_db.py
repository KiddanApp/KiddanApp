import asyncio
import json
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.models import Character, LessonData
from app.services.character_service import CharacterService
from app.services.lesson_service import LessonService

async def seed_characters():
    """Load characters from JSON file into MongoDB"""
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client.punjabi_tutor
    char_service = CharacterService(db)

    char_path = Path(__file__).parent / "characters.json"

    with open(char_path, "r", encoding="utf-8") as f:
        chars_data = json.load(f)

    for char_id, char_data in chars_data.items():
        character = Character(**char_data)
        try:
            existing = await char_service.get_character(char_id)
            if not existing:
                await char_service.create_character(character)
                print(f"Created character: {char_id}")
            else:
                print(f"Character {char_id} already exists")
        except Exception as e:
            print(f"Error creating character {char_id}: {e}")

async def seed_lessons():
    """Load lessons from JSON files into MongoDB"""
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client.punjabi_tutor
    lesson_service = LessonService(db)

    lessons_path = Path(__file__).parent / "lessons"

    for lesson_file in lessons_path.glob("*.json"):
        try:
            with open(lesson_file, "r", encoding="utf-8") as f:
                lesson_data = json.load(f)

            lesson_doc = LessonData(**lesson_data)

            # Check if already exists
            existing = await lesson_service.get_character_lessons(lesson_doc.characterId)
            if not existing:
                # Insert the document
                await db.lessons.insert_one(lesson_doc.model_dump())
                print(f"Seeded lessons for character: {lesson_doc.characterId}")
            else:
                print(f"Lessons for {lesson_doc.characterId} already exist")
        except Exception as e:
            print(f"Error seeding lessons from {lesson_file.name}: {e}")

async def main():
    print("Starting database seeding...")

    # Seed characters first
    print("Seeding characters...")
    await seed_characters()

    # Then seed lessons
    print("Seeding lessons...")
    await seed_lessons()

    print("Database seeding completed!")

if __name__ == "__main__":
    asyncio.run(main())
