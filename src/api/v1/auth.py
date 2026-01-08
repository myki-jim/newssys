"""
用户认证 API
处理用户登录、登出等
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import APIResponse
from src.core.auth import create_access_token, get_current_user, get_admin_user, ACCESS_TOKEN_EXPIRE_MINUTES
from src.core.database import get_async_session_generator
from src.core.models import UserLogin, UserCreate, UserResponse, LoginResponse
from src.repository.user_repository import UserRepository

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=APIResponse[LoginResponse])
async def login(
    user_data: UserLogin,
    db: AsyncSession = Depends(get_async_session_generator),
):
    """用户登录"""
    user_repo = UserRepository(db)
    user = await user_repo.authenticate(user_data.username, user_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 创建 token
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return APIResponse(
        success=True,
        data=LoginResponse(
            access_token=access_token,
            user=UserResponse(**user),
        ),
    )


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_me(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session_generator),
):
    """获取当前用户信息"""
    return APIResponse(success=True, data=current_user)
