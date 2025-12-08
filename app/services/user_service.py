import uuid
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from passlib.context import CryptContext
from app.models import User
from pymongo.errors import DuplicateKeyError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.users

    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    async def create_user(self, email: str, password: str) -> User:
        """Create a new user"""
        # Check if user already exists
        existing = await self.collection.find_one({"email": email})
        if existing:
            raise ValueError(f"User with email '{email}' already exists")

        # Hash password and create user
        hashed_password = self.hash_password(password)
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=hashed_password
        )

        try:
            await self.collection.insert_one(user.model_dump())
            return user
        except DuplicateKeyError:
            raise ValueError(f"User with email '{email}' already exists")

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email"""
        doc = await self.collection.find_one({"email": email})
        if doc:
            return User(**doc)
        return None

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        doc = await self.collection.find_one({"id": user_id})
        if doc:
            return User(**doc)
        return None

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user with email and password"""
        user = await self.get_user_by_email(email)
        if user and self.verify_password(password, user.hashed_password):
            return user
        return None
