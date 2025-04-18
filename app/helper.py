import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel
from starlette.config import Config

from .crud import crud_users
from .database import get_session

current_file_dir = os.path.dirname(os.path.realpath(__file__))
env_path = os.path.join(current_file_dir, ".env")
config = Config(env_path)


# Security settings
SECRET_KEY = config("SECRET_KEY")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


# Token models
class Token(SQLModel):
    access_token: str
    token_type: str


class TokenData(SQLModel):
    username_or_email: str


def get_password_hash(password: str) -> bytes:
    return bcrypt.hashpw(password.encode(), salt=bcrypt.gensalt())


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


async def create_access_token(
    data: Dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc).replace(tzinfo=None) + expires_delta
    else:
        expire = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")


async def verify_token(token: str, db: AsyncSession) -> TokenData | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username_or_email: str | None = payload.get("sub")
        if username_or_email is None:
            return None
        else:
            return TokenData(username_or_email=username_or_email)
    except JWTError:
        return None


async def authenticate_user(username_or_email: str, password: str, db: AsyncSession):
    if "@" in username_or_email:
        # Assume email
        db_user: dict | None = await crud_users.get(
            db=db, email=username_or_email, is_deleted=False
        )
    else:
        db_user = await crud_users.get(
            db=db, username=username_or_email, is_deleted=False
        )
    if not db_user:
        return False
    elif not await verify_password(password, db_user["hashed_password"]):
        return False
    return db_user


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any] | None:
    """Get the current authenticated user."""
    token_data = await verify_token(token, db)
    if token_data is None:
        raise HTTPException(status_code=401, detail="User not authenticated.")

    if "@" in token_data.username_or_email:
        user = await crud_users.get(
            db=db, email=token_data.username_or_email, is_deleted=False
        )
    else:
        user = await crud_users.get(
            db=db, username=token_data.username_or_email, is_deleted=False
        )

    if user:
        return user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated."
    )
