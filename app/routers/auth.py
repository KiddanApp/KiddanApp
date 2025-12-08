from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from app.schemas import UserSignup, UserLogin, UserOut
from app.database import get_db
from app.services.user_service import UserService

router = APIRouter()

def get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(session)

@router.post("/signup", response_model=UserOut)
async def signup(
    user_data: UserSignup,
    response: Response,
    service: UserService = Depends(get_user_service)
):
    try:
        user = await service.create_user(user_data.email, user_data.password)
        # Set session
        response.set_cookie(
            key="user_id",
            value=user.id,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )
        return UserOut(
            id=user.id,
            email=user.email,
            created_at=user.created_at.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=UserOut)
async def login(
    user_data: UserLogin,
    response: Response,
    service: UserService = Depends(get_user_service)
):
    user = await service.authenticate_user(user_data.email, user_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Set session
    response.set_cookie(
        key="user_id",
        value=user.id,
        httponly=True,
        secure=False,  
        samesite="lax"
    )
    return UserOut(
        id=user.id,
        email=user.email,
        created_at=user.created_at.isoformat()
    )

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="user_id")
    return {"message": "Logged out successfully"}

@router.get("/me/{user_id}", response_model=UserOut)
async def get_current_user(
    user_id: str,
    request: Request,
    service: UserService = Depends(get_user_service)
):
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return UserOut(
        id=user.id,
        email=user.email,
        created_at=user.created_at.isoformat()
    )
