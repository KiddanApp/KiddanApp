# MongoDB Motor client setup
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client = AsyncIOMotorClient(settings.MONGODB_URL)
db = client.punjabi_tutor

async def get_database():
    return db
