from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
import os
from contextlib import asynccontextmanager

from app.routers import characters, chat, lessons, admin, auth
from app.db import get_database
from app.database import engine, Base
from app.services.character_service import CharacterService
from app.models import Character, LessonData
import json
from pathlib import Path

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables and seed database if empty
    try:
        # Create PostgreSQL tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("PostgreSQL tables created!")

        # MongoDB seeding
        db = await get_database()
        char_service = CharacterService(db)

        # Check if characters exist
        existing_chars = await char_service.get_all_characters()
        if not existing_chars:
            print("MongoDB database empty, seeding data...")

            # Seed characters
            char_path = Path(__file__).parent / "seed" / "characters.json"
            if char_path.exists():
                with open(char_path, "r", encoding="utf-8") as f:
                    chars_data = json.load(f)

                for char_id, char_data in chars_data.items():
                    character = Character(**char_data)
                    try:
                        await char_service.create_character(character)
                        print(f"Seeded character: {char_id}")
                    except Exception as e:
                        print(f"Error seeding character {char_id}: {e}")

            # Seed lessons from static folder
            lessons_path = Path(__file__).parent.parent / "static"
            if lessons_path.exists():
                from app.services.lesson_service import LessonService
                lesson_service = LessonService(db)

                for lesson_file in lessons_path.glob("*.json"):
                    if lesson_file.name == "admin.html" or lesson_file.name == "mongo_admin.html":
                        continue

                    try:
                        with open(lesson_file, "r", encoding="utf-8") as f:
                            lesson_data = json.load(f)

                        lesson_doc = LessonData(**lesson_data)
                        existing = await lesson_service.get_character_lessons(lesson_doc.characterId)
                        if not existing:
                            await db.lessons.insert_one(lesson_doc.model_dump())
                            print(f"Seeded lessons for character: {lesson_doc.characterId}")
                    except Exception as e:
                        print(f"Error seeding lessons from {lesson_file.name}: {e}")

            print("Database seeding completed!")
    except Exception as e:
        print(f"Error during startup seeding: {e}")

    yield

    # Shutdown
    pass

app = FastAPI(title="PunjabiTutor Backend – Phase 1", lifespan=lifespan)

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-in-production")

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
static_dir = os.path.abspath(static_dir)
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(characters.router, prefix="/characters", tags=["characters"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(lessons.router, prefix="/lessons", tags=["lessons"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin.router, tags=["admin"])

@app.get("/admin")
async def admin_panel():
    """Serve the admin panel HTML page"""
    admin_file = os.path.join(static_dir, "admin.html")
    if os.path.exists(admin_file):
        return FileResponse(admin_file, media_type='text/html')
    return {"error": "Admin panel not found"}

@app.get("/mongo-admin")
async def mongo_admin_panel():
    """Serve the advanced MongoDB admin panel HTML page"""
    mongo_admin_file = os.path.join(static_dir, "mongo_admin.html")
    if os.path.exists(mongo_admin_file):
        return FileResponse(mongo_admin_file, media_type='text/html')
    return {"error": "MongoDB admin panel not found"}

@app.post("/seed-database")
async def seed_database():
    """Manually trigger database seeding"""
    try:
        db = await get_database()
        char_service = CharacterService(db)

        # Check if characters exist
        existing_chars = await char_service.get_all_characters()
        if existing_chars:
            return {"message": "Database already seeded", "characters_count": len(existing_chars)}

        # Seed characters
        char_path = Path(__file__).parent / "seed" / "characters.json"
        seeded_chars = 0
        seeded_lessons = 0

        if char_path.exists():
            with open(char_path, "r", encoding="utf-8") as f:
                chars_data = json.load(f)

            for char_id, char_data in chars_data.items():
                character = Character(**char_data)
                try:
                    await char_service.create_character(character)
                    seeded_chars += 1
                except Exception as e:
                    print(f"Error seeding character {char_id}: {e}")

        # Seed lessons from static folder (same as lifespan seeding)
        lessons_path = Path(__file__).parent.parent / "static"
        if lessons_path.exists():
            from app.services.lesson_service import LessonService
            lesson_service = LessonService(db)

            for lesson_file in lessons_path.glob("*.json"):
                if lesson_file.name == "admin.html" or lesson_file.name == "mongo_admin.html":
                    continue

                try:
                    with open(lesson_file, "r", encoding="utf-8") as f:
                        lesson_data = json.load(f)

                    lesson_doc = LessonData(**lesson_data)
                    existing = await lesson_service.get_character_lessons(lesson_doc.characterId)
                    if not existing:
                        await db.lessons.insert_one(lesson_doc.model_dump())
                        seeded_lessons += 1
                        print(f"Seeded lessons for character: {lesson_doc.characterId}")
                except Exception as e:
                    print(f"Error seeding lessons from {lesson_file.name}: {e}")

        return {
            "message": "Database seeded successfully",
            "characters_seeded": seeded_chars,
            "lesson_sets_seeded": seeded_lessons
        }
    except Exception as e:
        return {"error": f"Seeding failed: {str(e)}"}

@app.get("/health")
async def health():
    return {"status": "ok"}
