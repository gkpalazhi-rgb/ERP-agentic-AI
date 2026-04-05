"""
Authentication service for the ERP Agent.

Provides:
  - Password hashing (bcrypt)
  - JWT token creation & verification
  - User registration & login helpers
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Iterable

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.feature_access import (
    effective_feature_access,
    serialize_feature_access,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "erp-agent-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------
def register_user(
    db: Session,
    username: str,
    password: str,
    email: str | None = None,
    role: str = "employee",
    feature_access: Iterable[str] | None = None,
) -> dict:
    """Register a new user. Returns user info + JWT token."""

    # Check for existing username
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return {"error": f"Username '{username}' is already taken."}

    # Check for existing email
    if email:
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            return {"error": f"Email '{email}' is already registered."}

    stored_feature_access = serialize_feature_access(feature_access)

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=role,
        accessible_features=stored_feature_access,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id, user.username, user.role)

    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "feature_access": effective_feature_access(user.role, user.accessible_features),
        "token": token,
    }


def login_user(db: Session, username: str, password: str) -> dict:
    """Authenticate a user. Returns user info + JWT token."""

    user = db.query(User).filter(User.username == username).first()
    if not user:
        return {"error": "Invalid username or password."}

    if not user.password_hash:
        return {"error": "This account has no password set. Please contact admin."}

    if not verify_password(password, user.password_hash):
        return {"error": "Invalid username or password."}

    token = create_token(user.id, user.username, user.role)

    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "feature_access": effective_feature_access(user.role, user.accessible_features),
        "token": token,
    }


def get_current_user(db: Session, token: str) -> User | None:
    """Decode a JWT and return the corresponding User, or None."""
    payload = decode_token(token)
    if not payload:
        return None

    user_id = payload.get("user_id")
    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()
