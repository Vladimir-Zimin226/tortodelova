from __future__ import annotations

import hashlib
import hmac

from .config import get_settings

_settings = get_settings()


def hash_password(password: str) -> str:
    """
    Простейшее хеширование пароля через SHA256 + соль.
    """
    if not password:
        raise ValueError("Пароль не может быть пустым.")

    salted = (_settings.password_salt + password).encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Проверка пароля против хеша.
    """
    calculated = hash_password(password)
    return hmac.compare_digest(calculated, hashed_password)
