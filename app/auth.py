import os
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, UserRole

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-this-secret-please-replace-32plus")
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "720"))
ph = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o vencida",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub", "0"))
    except (InvalidTokenError, ValueError, TypeError):
        raise credentials_error
    user = db.get(User, user_id)
    if not user or not user.active:
        raise credentials_error
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Se requiere perfil administrador")
    return user


def seed_users(db: Session) -> None:
    admin_user = os.getenv("INITIAL_ADMIN_USER", "admin")
    admin_password = os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")
    seller_user = os.getenv("INITIAL_SELLER_USER", "vendedor")
    seller_password = os.getenv("INITIAL_SELLER_PASSWORD", "vendedor123")

    if not db.scalar(select(User).where(User.username == admin_user)):
        db.add(User(username=admin_user, full_name="Administrador", password_hash=hash_password(admin_password), role=UserRole.ADMIN))
    if not db.scalar(select(User).where(User.username == seller_user)):
        db.add(User(username=seller_user, full_name="Vendedor", password_hash=hash_password(seller_password), role=UserRole.SELLER))
    db.commit()
