import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db, utc, utcnow
from app.models import LoginSession, User

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000).hex()
    return f"pbkdf2_sha256$310000${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt, digest = encoded.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(db: Session, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=token_hash(token), user_id=user_id, expires_at=utcnow() + timedelta(hours=12)))
    return token


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(401, "请先登录")
    login = db.get(LoginSession, token_hash(credentials.credentials))
    if login is None or utc(login.expires_at) <= utcnow():
        raise HTTPException(401, "登录已过期，请重新登录")
    user = db.get(User, login.user_id)
    if user is None:
        raise HTTPException(401, "账号不存在")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "需要管理员权限")
    return user
