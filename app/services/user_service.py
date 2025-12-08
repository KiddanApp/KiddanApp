import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import Optional
from passlib.context import CryptContext
from app.models import User
from app.models_sql import UserSQL

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    async def create_user(self, email: str, password: str) -> User:
        """Create a new user"""
        # Check if user already exists
        existing = await self.session.execute(
            select(UserSQL).where(UserSQL.email == email)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"User with email '{email}' already exists")

        # Hash password and create user
        hashed_password = self.hash_password(password)
        user_id = str(uuid.uuid4())

        user_sql = UserSQL(
            id=user_id,
            email=email,
            hashed_password=hashed_password
        )

        try:
            self.session.add(user_sql)
            await self.session.commit()
            await self.session.refresh(user_sql)

            # Return Pydantic model
            return User(
                id=user_sql.id,
                email=user_sql.email,
                hashed_password=user_sql.hashed_password,
                created_at=user_sql.created_at
            )
        except IntegrityError:
            await self.session.rollback()
            raise ValueError(f"User with email '{email}' already exists")

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email"""
        result = await self.session.execute(
            select(UserSQL).where(UserSQL.email == email)
        )
        user_sql = result.scalar_one_or_none()
        if user_sql:
            return User(
                id=user_sql.id,
                email=user_sql.email,
                hashed_password=user_sql.hashed_password,
                created_at=user_sql.created_at
            )
        return None

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        result = await self.session.execute(
            select(UserSQL).where(UserSQL.id == user_id)
        )
        user_sql = result.scalar_one_or_none()
        if user_sql:
            return User(
                id=user_sql.id,
                email=user_sql.email,
                hashed_password=user_sql.hashed_password,
                created_at=user_sql.created_at
            )
        return None

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user with email and password"""
        user = await self.get_user_by_email(email)
        if user and self.verify_password(password, user.hashed_password):
            return user
        return None
