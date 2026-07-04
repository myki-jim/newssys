"""
认证中间件和依赖项
处理用户登录、访问密码验证和 JWT token 验证
"""

import hashlib
import jwt
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_session_generator
from src.core.models import UserResponse
from src.repository.user_repository import UserRepository

# JWT 配置
SECRET_KEY = "newssys-secret-key-2024"  # 生产环境应该从环境变量读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 天
GATE_TOKEN_EXPIRE_DAYS = 7  # 访问密码有效期

security = HTTPBearer(auto_error=False)


# ============================================================================
# CPDK — 复合参数派生密钥 (Compound Parameter Derived Key)
# ============================================================================

SYSTEM_ID = "YLNU-OSINT-2.0"


def _cpdk_phase1(date_str: str, month_cycle: str, week_seed: str, secret: str) -> bytes:
    """Phase 1 — 复合种子: SHA256(date + system_id + month_cycle + week_seed + secret)"""
    material = date_str + SYSTEM_ID + month_cycle + week_seed + secret
    return hashlib.sha256(material.encode()).digest()


def _cpdk_phase2(seed: bytes, rounds: int) -> bytes:
    """Phase 2 — 拉伸: 对 seed 做 rounds 轮迭代 SHA256(key + seed)"""
    key = seed
    for _ in range(rounds):
        key = hashlib.sha256(key + seed).digest()
    return key


def _cpdk_phase3(key: bytes, date_str: str, secret: str) -> str:
    """Phase 3 — 终值导出: SHA256(key + date + secret) → hex 前 10 位"""
    final = hashlib.sha256(key + date_str.encode() + secret.encode()).hexdigest()[:10]
    return f"{final[:4]}-{final[4:8]}-{final[8:10]}"


def get_daily_password(secret: str) -> str:
    """CPDK 多参数复合派生每日密码 (3 阶段 6 参数)"""
    today = date.today()
    date_str = today.isoformat()                # "2026-05-26"
    month_cycle = today.strftime("%Y%m")         # "202605"
    week_seed = str(today.isocalendar()[1])      # "22" (ISO week)
    rounds = today.day + 10                      # 10~41

    seed = _cpdk_phase1(date_str, month_cycle, week_seed, secret)
    key = _cpdk_phase2(seed, rounds)
    return _cpdk_phase3(key, date_str, secret)


def create_gate_token(secret: str) -> str:
    """创建访问门禁 token (7天有效)"""
    expire = datetime.utcnow() + timedelta(days=GATE_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": "gate_access",
        "iat": datetime.utcnow(),
        "exp": expire,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_gate_token(token: str, secret: str) -> bool:
    """验证访问门禁 token，返回是否有效"""
    try:
        jwt.decode(token, secret, algorithms=[ALGORITHM])
        return True
    except jwt.ExpiredSignatureError:
        return False
    except jwt.JWTError:
        return False


async def get_gate_token_from_cookie(request: Request) -> str | None:
    """从 Cookie 中获取访问门禁 token"""
    return request.cookies.get("newsys_gate_token")

security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """解码 JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期",
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_session_generator),
) -> UserResponse:
    """获取当前登录用户"""
    token = credentials.credentials
    payload = decode_access_token(token)

    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Token",
        )

    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(username)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户已被禁用",
        )

    return UserResponse(**user)


async def get_admin_user(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """获取当前管理员用户"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
