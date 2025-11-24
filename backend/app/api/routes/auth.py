from __future__ import annotations

import base64
import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, constr, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...core.config import get_settings
from ...core.security import hash_password, verify_password
from ...models.user import User, UserRole
from ...services.repositories.user_service import user_service

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)

# Настройки и "секрет" для токена берём из PASSWORD_SALT
_settings = get_settings()
_SECRET_KEY = _settings.password_salt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    balance_credits: int

    model_config = ConfigDict(from_attributes=True)


def _create_token(user_id: int) -> str:
    """
    Простейший HMAC-токен без внешних зависимостей.

    Формат:
        base64url("user_id:timestamp").hex_hmac_signature
    """
    payload = f"{user_id}:{int(time.time())}".encode("utf-8")
    b64 = base64.urlsafe_b64encode(payload).decode("ascii")
    signature = hmac.new(
        _SECRET_KEY.encode("utf-8"),
        b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{b64}.{signature}"


def _parse_token(token: str) -> int:
    """
    Распарсить токен и вернуть user_id или кинуть HTTP 401.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    try:
        b64, signature = token.split(".", 1)
    except ValueError:
        raise credentials_exception

    expected_sig = hmac.new(
        _SECRET_KEY.encode("utf-8"),
        b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, signature):
        raise credentials_exception

    try:
        payload = base64.urlsafe_b64decode(b64.encode("ascii")).decode("utf-8")
        user_id_str, _ts_str = payload.split(":", 1)
        user_id = int(user_id_str)
    except Exception:
        raise credentials_exception

    return user_id


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Зависимость FastAPI для получения текущего пользователя по токену.
    """
    user_id = _parse_token(token)
    user = await user_service.get(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Регистрация нового пользователя.

    - проверяем, что email свободен;
    - хешируем пароль;
    - создаём пользователя с ролью USER.
    """
    existing = await user_service.get_by_email(session, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    hashed = hash_password(payload.password)
    user = await user_service.create(
        session,
        email=payload.email,
        hashed_password=hashed,
        role=UserRole.USER,
    )
    await session.commit()
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Авторизация по email + password.

    При успехе возвращает HMAC-токен, который затем
    используется в Authorization: Bearer <token>.
    """
    user = await user_service.get_by_email(session, payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = _create_token(user.id)
    return TokenResponse(access_token=token)
