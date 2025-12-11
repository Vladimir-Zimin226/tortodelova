from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    """
    Хеширование пароля через bcrypt.

    - Генерируется случайная соль (bcrypt.gensalt());
    - Возвращается строка, которую можно хранить в БД как есть.
    """
    if not password:
        raise ValueError("Пароль не может быть пустым.")

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Проверка пароля против bcrypt-хеша.
    """
    if not password or not hashed_password:
        return False

    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        # Если хеш в неожиданном формате
        return False