from fastapi import Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette.requests import Request
from app.db import get_database
from app.services.user_service import UserService, get_user_service
from app.models import User
from typing import Optional

async def get_current_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> User:
    """Get the current authenticated user from session cookie"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    service = UserService(db)
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

async def get_optional_current_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> Optional[User]:
    """Get the current user if authenticated, None otherwise"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None

    service = UserService(db)
    user = await service.get_user_by_id(user_id)
    return user
