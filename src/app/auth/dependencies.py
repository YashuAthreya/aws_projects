# app/auth/dependencies.py

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import delete, delete, update
from sqlalchemy.orm import Session

from app.auth.auth_service import get_user_from_session
from app.auth.security import hash_password, verify_password
from app.database import get_db
from app.models import User, UserSession


SESSION_COOKIE_NAME = "session_id"


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:

    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    user = get_user_from_session(
        db,
        token,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return user


def require_admin(
    current_user: User = Depends(get_current_user),
):

    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required.",
        )

    return current_user

def revoke_all_sessions(
    db: Session,
    user_id: int,
):
    now = datetime.now(timezone.utc)

    db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    db.commit()


def change_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
):

    if not verify_password(
        current_password,
        user.password,
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect.",
        )

    user.password = hash_password(
        new_password
    )

    now = datetime.now(timezone.utc)

    db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user.user_id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    db.commit()    

