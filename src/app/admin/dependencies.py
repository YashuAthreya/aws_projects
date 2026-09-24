# app/admin/dependencies.py

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.admin.models import Admin
from app.admin.security import verify_admin_token
from app.database import get_db


ADMIN_SESSION_COOKIE_NAME = "admin_session"


def get_current_admin(
    request: Request,
    db: Session = Depends(get_db),
) -> Admin:

    token = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
        )

    admin_id = verify_admin_token(token)

    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
        )

    admin = db.get(Admin, admin_id)

    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
        )

    return admin
