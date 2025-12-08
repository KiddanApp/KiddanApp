from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from app.database import get_db
from app.services.user_service import UserService
from app.models import User
from typing import Optional

async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db)
) -> User:
    """Get the current authenticated user from session cookie"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    service = UserService(session)
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

async def get_optional_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get the current user if authenticated, None otherwise"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None

    service = UserService(session)
    user = await service.get_user_by_id(user_id)
    return user
