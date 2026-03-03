from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from pathlib import Path
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PRIVATE_KEY = Path("app/keys/private.pem").read_text()
PUBLIC_KEY = Path("app/keys/public.pem").read_text()


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict):
    expire = datetime.utcnow() + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, PRIVATE_KEY, algorithm="RS256")


def verify_token(token: str):
    return jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])