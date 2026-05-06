import json
import os
import hashlib
import time
import base64
from functools import wraps
from fastapi import Request, HTTPException
from config import DATA_DIR, logger

USERS_FILE = os.path.join(DATA_DIR, "users.json")

def _load_users():
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def verify_password(input_pw, stored_pw):
    """简单 SHA256 验证（生产环境应使用 bcrypt）"""
    return hashlib.sha256(input_pw.encode()).hexdigest() == stored_pw

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token(username):
    payload = f"{username}:{int(time.time())}"
    return base64.b64encode(payload.encode()).decode()

def decode_token(token):
    try:
        payload = base64.b64decode(token.encode()).decode()
        username = payload.split(":")[0]
        return username
    except Exception:
        return None

def login_user(username, password):
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    if not verify_password(password, user["password"]):
        return None
    token = generate_token(username)
    return {
        "token": token,
        "username": username,
        "name": user["name"],
        "role": user["role"],
    }

def get_current_user(request: Request):
    """从请求头提取并验证当前用户"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    username = decode_token(token)
    if not username:
        return None
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    return {"username": username, "name": user["name"], "role": user["role"]}

def require_role(role):
    """装饰器：限制指定角色才能访问"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # FastAPI 路由：第一个参数是 self/request，我们从 kwargs 中找 request
            request = kwargs.get("request", args[0] if args else None)
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            if request is None:
                raise HTTPException(500, "无法获取请求上下文")
            user = get_current_user(request)
            if not user:
                raise HTTPException(401, "未登录或登录已过期")
            if user["role"] != role and role != "any":
                raise HTTPException(403, f"权限不足，需要 {role} 角色")
            kwargs["_current_user"] = user
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 启动时初始化密码哈希
def init_users():
    if not os.path.exists(USERS_FILE):
        logger.warning(f"用户文件不存在: {USERS_FILE}")
        return
    users = _load_users()
    changed = False
    for username, info in users.items():
        pw = info["password"]
        if len(pw) != 64:  # 不是 SHA256 哈希，需要转换
            info["password"] = hash_password(pw)
            changed = True
    if changed:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        logger.info("用户密码已哈希处理")
