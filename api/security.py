"""Compatible bcrypt hashes, hashed session tokens and input validation."""
import hashlib
import re
import secrets

import bcrypt
from starlette.concurrency import run_in_threadpool


class AppError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def identity():
    return secrets.token_hex(16)


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def email(value):
    text = str(value or '').strip().lower()
    if len(text) > 254 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', text):
        raise AppError('Nhập email hợp lệ.')
    return text


def password(value):
    if not isinstance(value, str) or len(value) < 8 or len(value.encode()) > 72 or not value.strip():
        raise AppError('Mật khẩu cần ít nhất 8 ký tự, tối đa 72 byte UTF-8.')
    return value


def label(value, maximum=120):
    text = str(value or '').strip()
    if not text or len(text) > maximum:
        raise AppError(f'Nội dung phải có 1–{maximum} ký tự.')
    return text


async def hash_password(value):
    encoded = password(value).encode()
    return (await run_in_threadpool(bcrypt.hashpw, encoded, bcrypt.gensalt(rounds=12))).decode()


async def verify_password(value, hashed):
    if not isinstance(value, str) or len(value.encode()) > 72:
        return False
    try:
        return await run_in_threadpool(bcrypt.checkpw, value.encode(), hashed.encode())
    except ValueError:
        return False


def safe_user(user):
    return {key: user[key] for key in ('id', 'name', 'email')} | {'legacy_workspace': bool(user['legacy_workspace'])}
