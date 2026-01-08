"""
用户管理 API
仅管理员可访问
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import APIResponse
from src.core.auth import get_admin_user
from src.core.database import get_async_session_generator
from src.core.models import UserCreate, UserResponse, UserUpdate
from src.repository.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=APIResponse[list[UserResponse]])
async def list_users(
    role: str | None = None,
    is_active: bool | None = None,
    limit: int = 100,
    offset: int = 0,
    current_admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session_generator),
):
    """获取用户列表（管理员）"""
    user_repo = UserRepository(db)
    users = await user_repo.list(
        role=role,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return APIResponse(success=True, data=[UserResponse(**u) for u in users])


@router.get("/{user_id}", response_model=APIResponse[UserResponse])
async def get_user(
    user_id: int,
    current_admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session_generator),
):
    """获取用户详情（管理员）"""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    return APIResponse(success=True, data=UserResponse(**user))


@router.post("", response_model=APIResponse[dict])
async def create_user(
    user_data: UserCreate,
    current_admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session_generator),
):
    """创建用户（管理员）"""
    user_repo = UserRepository(db)

    # 检查用户名是否已存在
    existing = await user_repo.get_by_username(user_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )

    user_id = await user_repo.create(user_data.model_dump())
    user = await user_repo.get_by_id(user_id)

    return APIResponse(
        success=True,
        data={"message": "用户创建成功", "user": UserResponse(**user)},
    )


@router.put("/{user_id}", response_model=APIResponse[dict])
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session_generator),
):
    """更新用户（管理员）"""
    user_repo = UserRepository(db)

    # 检查用户是否存在
    existing = await user_repo.get_by_id(user_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 更新用户
    await user_repo.update(user_id, user_data.model_dump(exclude_unset=True))
    updated_user = await user_repo.get_by_id(user_id)

    return APIResponse(
        success=True,
        data={"message": "用户更新成功", "user": UserResponse(**updated_user)},
    )


@router.delete("/{user_id}", response_model=APIResponse[dict])
async def delete_user(
    user_id: int,
    current_admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session_generator),
):
    """删除用户（管理员）"""
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己",
        )

    user_repo = UserRepository(db)

    # 检查用户是否存在
    existing = await user_repo.get_by_id(user_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    await user_repo.delete(user_id)

    return APIResponse(
        success=True,
        data={"message": "用户删除成功"},
    )
