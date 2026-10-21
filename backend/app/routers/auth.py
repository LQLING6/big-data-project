from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LoginSession, User
from app.schemas import LoginInput, UserOutput
from app.security import bearer, current_user, new_session, token_hash, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    token = new_session(db, user.id)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": UserOutput.model_validate(user)}


@router.post("/logout")
def logout(user: User = Depends(current_user), credentials=Depends(bearer), db: Session = Depends(get_db)):
    login_session = db.get(LoginSession, token_hash(credentials.credentials))
    if login_session:
        db.delete(login_session)
        db.commit()
    return {"ok": True}
