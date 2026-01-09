from datetime import datetime, timedelta, timezone
import hashlib
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
)
from database import get_db
from models.user import User

# OAuth2 scheme for Swagger UI integration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _bcrypt_input(password: str) -> bytes:
    """Return bytes safe to pass into bcrypt.

    bcrypt only considers the first 72 bytes of input; many implementations
    also error on longer inputs. To avoid surprising truncation and crashes,
    we pre-hash long passwords with SHA-256.
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        return hashlib.sha256(password_bytes).digest()
    return password_bytes


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(_bcrypt_input(password), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        plain_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
    except Exception:
        return False

    # Try the raw password first (works for existing users and for <=72 bytes).
    try:
        if bcrypt.checkpw(plain_bytes, hashed_bytes):
            return True
    except ValueError:
        # bcrypt raises on >72-byte passwords; we'll try the pre-hash path below.
        pass
    except Exception:
        return False

    # If it's long, try the SHA-256 pre-hash variant.
    if len(plain_bytes) > 72:
        try:
            return bcrypt.checkpw(hashlib.sha256(plain_bytes).digest(), hashed_bytes)
        except Exception:
            return False

    return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Get the current authenticated user from the JWT token."""
    payload = decode_token(token)

    # Ensure it's an access token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id_str)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate token version (session invalidation check)
    token_version = payload.get("token_ver")
    if token_version is None or token_version != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalidated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def create_tokens(user: User) -> dict:
    """Create both access and refresh tokens for a user."""
    # JWT 'sub' claim must be a string
    access_token = create_access_token(
        data={"sub": str(user.id), "token_ver": user.token_version}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "token_ver": user.token_version}
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

