from datetime import datetime, timedelta
from jose import jwt
from config import settings

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"

if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not set. Define it in environment variables.")

def create_access_token(data: dict, expires_minutes=60*24):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
