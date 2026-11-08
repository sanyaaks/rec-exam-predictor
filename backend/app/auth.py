"""Authentication.

Local accounts (PBKDF2 password hashes + HS256 JWT) work out of the box.
If SUPABASE_JWT_SECRET is set, access tokens issued by Supabase Auth are also
accepted and mapped to a local user row by email.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models
from .config import JWT_SECRET, JWT_TTL_HOURS, SUPABASE_JWT_SECRET
from .db import get_db

_bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 240_000)
    return f"pbkdf2${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 240_000)
    return hmac.compare_digest(dk.hex(), digest)


def create_token(user: models.User) -> str:
    payload = {"sub": str(user.id), "email": user.email,
               "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_TTL_HOURS)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                 db: Session = Depends(get_db)) -> models.User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    token = creds.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user = db.get(models.User, int(payload["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        user = None
        if SUPABASE_JWT_SECRET:
            try:
                payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")
                email = payload.get("email")
                user = db.query(models.User).filter(models.User.email == email).first()
                if user is None and email:
                    user = models.User(email=email, name=email.split("@")[0], external_id=payload.get("sub"))
                    db.add(user)
                    db.commit()
            except jwt.PyJWTError:
                user = None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired - please sign in again")
    return user
