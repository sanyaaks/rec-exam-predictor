import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..auth import create_token, current_user, hash_password, verify_password
from ..db import get_db
from ..deps import user_out
from ..seed import seed_demo_subject

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=200)
    name: str = ""
    department: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Enter a valid email address")
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(400, "An account with this email already exists")
    u = models.User(email=email, name=body.name.strip() or email.split("@")[0], department=body.department,
                    password_hash=hash_password(body.password))
    db.add(u)
    db.commit()
    seed_demo_subject(db, u)
    return {"token": create_token(u), "user": user_out(u)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.email == body.email.strip().lower()).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"token": create_token(u), "user": user_out(u)}


@router.post("/guest")
def guest(db: Session = Depends(get_db)):
    """A throwaway account pre-loaded with the sample subject, for exploring without signing up."""
    u = models.User(email=f"guest-{secrets.token_hex(4)}@guest.local", name="Guest",
                    password_hash=hash_password(secrets.token_hex(16)))
    db.add(u)
    db.commit()
    seed_demo_subject(db, u)
    return {"token": create_token(u), "user": user_out(u)}


@router.get("/me")
def me(user: models.User = Depends(current_user)):
    return user_out(user)


class ProfileIn(BaseModel):
    name: str | None = None
    department: str | None = None


@router.patch("/me")
def update_me(body: ProfileIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name is not None:
        user.name = body.name
    if body.department is not None:
        user.department = body.department
    db.commit()
    return user_out(user)
