# app/auth/router.py

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    SESSION_COOKIE_NAME,
)
from app.schemas import (
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.auth.auth_service import (
    authenticate_user,
    create_session,
    create_user,
)
from app.database import get_db


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


COOKIE_SECURE = True


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):

    print("*"*100,"Register endpoint","*"*100)

    user = create_user(
        db=db,
        email=request.email,
        password=request.password,
        name=request.name,
        mobile=request.mobile,
    )

    #return RedirectResponse(url=f"./../static/job_prof.html?user_id={user.user_id}", status_code=303)
    return JSONResponse({
        "user_id": user.user_id,
        "message": "Account created. Please complete your profile.",
        "next_url": f"/static/job_prof.html?user_id={user.user_id}"
    })
    #return user