"""
用户认证 API
处理用户登录、登出、访问密码门禁等
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import APIResponse
from src.core.auth import (
    create_access_token,
    create_gate_token,
    decode_gate_token,
    get_current_user,
    get_admin_user,
    get_daily_password,
    get_gate_token_from_cookie,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    GATE_TOKEN_EXPIRE_DAYS,
)
from src.core.config import settings
from src.core.database import get_async_session_generator
from src.core.models import UserLogin, UserCreate, UserResponse, LoginResponse
from src.repository.user_repository import UserRepository

router = APIRouter(tags=["auth"])
gate_router = APIRouter(tags=["auth-gate"])

LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>访问验证 - 智能情报分析平台</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.card { background: #fff; border-radius: 12px; box-shadow: 0 2px 16px rgba(0,0,0,0.08); padding: 40px; width: 100%; max-width: 400px; }
h1 { font-size: 20px; color: #1a1a2e; margin-bottom: 8px; text-align: center; }
.subtitle { font-size: 13px; color: #888; margin-bottom: 24px; text-align: center; }
.input-group { margin-bottom: 16px; }
input[type="password"] { width: 100%; padding: 10px 14px; border: 1px solid #d9d9d9; border-radius: 8px; font-size: 15px; outline: none; transition: border-color 0.2s; }
input[type="password"]:focus { border-color: #4f46e5; }
button { width: 100%; padding: 10px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; transition: background 0.2s; }
button:hover { background: #4338ca; }
.error { color: #dc2626; font-size: 13px; margin-top: 8px; display: none; text-align: center; }
.hint { font-size: 12px; color: #aaa; margin-top: 16px; text-align: center; }
</style>
</head>
<body>
<div class="card">
<h1>智能情报分析平台</h1>
<p class="subtitle">请输入今日访问密码</p>
<form id="loginForm">
<div class="input-group">
<input type="password" id="password" placeholder="访问密码" autofocus autocomplete="off">
</div>
<button type="submit">验证访问</button>
<p class="error" id="error"></p>
</form>
<p class="hint">密码每日更新，验证通过后 7 天内无需重复输入</p>
</div>
<script>
const params = new URLSearchParams(window.location.search);
const redirect = params.get('redirect') || '/';
document.getElementById('loginForm').addEventListener('submit', async (e) => {
e.preventDefault();
const password = document.getElementById('password').value;
const errorEl = document.getElementById('error');
errorEl.style.display = 'none';
try {
const resp = await fetch('/auth/login', {
method: 'POST',
headers: { 'Content-Type': 'application/json' },
body: JSON.stringify({ password, redirect }),
});
if (resp.ok) {
const data = await resp.json();
window.location.href = data.redirect || redirect;
} else {
const data = await resp.json();
errorEl.textContent = data.detail || '密码错误，请重试';
errorEl.style.display = 'block';
}
} catch (err) {
errorEl.textContent = '网络错误，请重试';
errorEl.style.display = 'block';
}
});
</script>
</body>
</html>"""


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


# ============================================================================
# 访问密码门禁 (nginx auth_request)
# ============================================================================


@router.get("/check")
async def gate_check(request: Request):
    """nginx auth_request 回调 — 验证访问门禁 cookie"""
    token = await get_gate_token_from_cookie(request)
    if token and decode_gate_token(token, settings.runtime.access_gate_secret):
        return JSONResponse({"status": "ok"})
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要访问密码")


@gate_router.get("/auth/login", response_class=HTMLResponse)
async def gate_login_page():
    """访问密码登录页面"""
    return HTMLResponse(LOGIN_HTML)


@gate_router.post("/auth/login")
async def gate_login_submit(request: Request):
    """验证访问密码并设置 7 天有效 Cookie"""
    import json
    body = await request.json()
    password = body.get("password", "").strip()
    redirect_url = body.get("redirect", "/")

    daily_pw = get_daily_password(settings.runtime.access_gate_secret)
    if password != daily_pw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="密码错误，请重试")

    token = create_gate_token(settings.runtime.access_gate_secret)
    resp = JSONResponse({"status": "ok", "redirect": redirect_url})
    resp.set_cookie(
        key="newsys_gate_token",
        value=token,
        max_age=GATE_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp
