# app/admin/auth_router.py

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.admin.auth_service import authenticate_admin
from app.admin.dependencies import ADMIN_SESSION_COOKIE_NAME, get_current_admin
from app.admin.models import Admin
from app.admin.schemas import AdminLoginRequest, AdminResponse
from app.admin.security import create_admin_token
from app.database import get_db


router = APIRouter(
    prefix="/admin/auth",
    tags=["Admin Authentication"],
)


COOKIE_SECURE = True


@router.post("/login")
def admin_login(
    credentials: AdminLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):

    admin = authenticate_admin(
        db=db,
        admin_name=credentials.admin_name,
        admin_password=credentials.admin_password,
    )

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin name or password.",
        )

    token = create_admin_token(admin.admin_id)

    response.set_cookie(
        key=ADMIN_SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=8 * 60 * 60,
        path="/",
    )

    return {"message": "Admin login successful."}


@router.post("/logout")
def admin_logout(response: Response):
    response.delete_cookie(
        key=ADMIN_SESSION_COOKIE_NAME,
        path="/",
    )
    return {"message": "Admin logged out."}


@router.get(
    "/me",
    response_model=AdminResponse,
)
def admin_me(
    current_admin: Admin = Depends(get_current_admin),
):
    return current_admin
