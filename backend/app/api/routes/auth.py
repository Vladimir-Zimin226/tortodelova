from __future__ import annotations

import time

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, constr, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from jwt import PyJWTError

from app.core.db import get_db
from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.services.repositories.user_service import user_service

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)

_settings = get_settings()
_JWT_SECRET_KEY = _settings.jwt_secret_key
_JWT_ALGORITHM = _settings.jwt_algorithm
_ACCESS_TOKEN_EXPIRE_MINUTES = _settings.access_token_expire_minutes


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


def _create_access_token(user_id: int) -> str:
    """
    Создаёт JWT access-токен.

    В payload кладём:
    - sub: str(user_id)
    - exp: время истечения (UTC + ACCESS_TOKEN_EXPIRE_MINUTES)
    """
    now = int(time.time())
    expire = now + _ACCESS_TOKEN_EXPIRE_MINUTES * 60

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, _JWT_SECRET_KEY, algorithm=_JWT_ALGORITHM)


def _get_user_id_from_token(token: str) -> int:
    """
    Парсит JWT и возвращает user_id или кидает HTTP 401.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            _JWT_SECRET_KEY,
            algorithms=[_JWT_ALGORITHM],
        )
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id = int(sub)
    except (PyJWTError, ValueError):
        raise credentials_exception

    return user_id


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Зависимость FastAPI для получения текущего пользователя по JWT-токену.

    Ищем токен:
    1) в заголовке Authorization: Bearer <token>
    2) если нет — в HttpOnly-куке access_token
    """
    token: str | None = None

    # 1) Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    # 2) HttpOnly-кука access_token
    if not token:
        cookie_val = request.cookies.get("access_token")
        if cookie_val:
            token = cookie_val.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = _get_user_id_from_token(token)
    user = await user_service.get(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
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


@router.post("/login", response_model=TokenResponse)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Авторизация по email + password через OAuth2 password flow.

    username в форме = email в нашей модели.

    Возвращаем токен в JSON И одновременно кладём его в HttpOnly-куку
    access_token, чтобы <img src="/api/..."> тоже проходил авторизацию.
    """
    email = form_data.username
    password = form_data.password

    user = await user_service.get_by_email(session, email)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = _create_access_token(user.id)

    # HttpOnly-кука для браузера
    response.set_cookie(
        key="access_token",
        value=token,                    # храним чистый JWT
        httponly=True,
        secure=False,                   # в проде под HTTPS поставить True
        samesite="lax",
        path="/",
        max_age=_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return TokenResponse(access_token=token)