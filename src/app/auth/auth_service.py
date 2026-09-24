# app/auth/service.py

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.models import UserSession
from app.models import User


SESSION_DURATION = timedelta(hours=24)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(
    db: Session,
    email: str,
    password: str,
    name: str,
    mobile: str,
) -> User:

    print("*"*100,"create_user method","*"*100)


    email = normalize_email(email)

    existing_user = db.scalar(
        select(User).where(User.user_email == email)
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create account.",
        )

    user = User(
        user_email=email,
        password=hash_password(password),
        user_name=name,
        mobile_number=mobile,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:

    email = normalize_email(email)

    user = db.scalar(
        select(User).where(User.user_email == email)
    )

    if not user:
        return None

    if not user.is_active:
        return None

    if not verify_password(
        password,
        user.password,
    ):
        return None

    return user


def create_session(
    db: Session,
    user: User,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:

    raw_token = generate_session_token()

    now = datetime.now(timezone.utc)

    session = UserSession(
        user_id=user.user_id,
        session_token_hash=hash_session_token(raw_token),
        created_at=now,
        last_used_at=now,
        expires_at=now + SESSION_DURATION,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(session)

    user.last_login_at = now

    db.commit()

    return raw_token


# app/auth/service.py

def get_user_from_session(
    db: Session,
    raw_token: str,
) -> User | None:

    token_hash = hash_session_token(raw_token)

    session = db.scalar(
        select(UserSession)
        .where(
            UserSession.session_token_hash == token_hash
        )
    )

    if not session:
        return None

    now = datetime.now(timezone.utc)

    if session.revoked_at is not None:
        return None

    if session.expires_at <= now:
        return None

    user = db.get(User, session.user_id)

    if not user:
        return None

    if not user.is_active:
        return None

    if (
        now - session.last_used_at
        > timedelta(minutes=5)
    ):
        session.last_used_at = now
        db.commit()
    #session.last_used_at = now
    #db.commit()

    return user