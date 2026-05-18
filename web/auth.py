"""
认证路由 — 注册、登录、刷新、登出、当前用户
"""

import time

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ============================================================
# 请求/响应模型
# ============================================================

class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ============================================================
# 依赖：解析当前用户
# ============================================================

async def get_current_user(authorization: str = Header(None)):
    """从 Authorization 头解析当前用户"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="无效的 Authorization 格式")
    
    token = authorization[7:]
    if not token:
        raise HTTPException(status_code=401, detail="无效的 token")
    
    from db.schema import _jwt_verify, get_token_version
    payload = _jwt_verify(token)
    if not payload:
        raise HTTPException(status_code=401, detail="token 已过期或无效")
    
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="需要 access_token")
    
    user_id = payload.get("sub")
    token_ver = payload.get("ver", 0)
    
    # 检查 token_version（单点登录）
    current_ver = await get_token_version(user_id)
    if token_ver != current_ver:
        raise HTTPException(
            status_code=401,
            detail="该账号已在其他地方登录",
        )
    
    return {
        "id": user_id,
        "username": payload.get("username", ""),
    }


async def optional_user(authorization: str = Header(None)):
    """可选认证 — 有 token 就解析，没有也通过"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


# ============================================================
# 路由
# ============================================================

@router.post("/register")
async def register(req: RegisterRequest):
    """注册新用户"""
    username = req.username.strip()
    password = req.password
    
    if len(username) < 2 or len(username) > 32:
        raise HTTPException(status_code=400, detail="用户名长度需在 2-32 个字符之间")
    
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少 6 位")
    
    from db.schema import create_user, get_user_by_username
    existing = await get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")
    
    user = await create_user(username, password)
    from db.schema import create_tokens, increment_token_version
    
    ver = await increment_token_version(user["id"])
    tokens = create_tokens(user["id"], user["username"], ver)
    
    return {
        "status": "ok",
        **tokens,
        "user": {"id": user["id"], "username": user["username"]},
    }


@router.post("/login")
async def login(req: LoginRequest):
    """登录"""
    from db.schema import verify_user_password, create_tokens, increment_token_version
    
    user = await verify_user_password(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    ver = await increment_token_version(user["id"])
    tokens = create_tokens(user["id"], user["username"], ver)
    
    return {
        "status": "ok",
        **tokens,
        "user": {"id": user["id"], "username": user["username"]},
    }


@router.post("/refresh")
async def refresh(req: RefreshRequest):
    """刷新 access_token"""
    from db.schema import _jwt_verify, get_token_version, create_tokens, get_user_by_id
    
    payload = _jwt_verify(req.refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="refresh_token 已过期或无效")
    
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="需要 refresh_token")
    
    user_id = payload.get("sub")
    token_ver = payload.get("ver", 0)
    
    # 检查 token_version
    current_ver = await get_token_version(user_id)
    if token_ver != current_ver:
        raise HTTPException(
            status_code=401,
            detail="登录已失效，请重新登录",
        )
    
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    
    # 保留原有 version（不递增！只刷新 access）
    from db.schema import _jwt_sign
    now = time.time()
    access_payload = {
        "sub": user_id,
        "username": user["username"],
        "ver": current_ver,
        "exp": now + 900,
        "iat": now,
        "type": "access",
    }
    
    return {
        "status": "ok",
        "access_token": _jwt_sign(access_payload),
        "expires_in": 900,
    }


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """登出 — 递增 token_version 使所有 token 失效"""
    from db.schema import increment_token_version
    await increment_token_version(current_user["id"])
    return {"status": "ok", "message": "已退出登录"}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    from db.schema import get_user_by_id
    user = await get_user_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"status": "ok", "user": user}
