from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.auth_service import authenticate_user, create_session
from app.auth.dependencies import SESSION_COOKIE_NAME, get_current_user, revoke_all_sessions
from app.auth.router import COOKIE_SECURE, router
from app.auth.security import hash_session_token
from app.database import get_db
from app.models import User, UserSession
from app.schemas import LoginRequest, UserResponse


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):

    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if token:

        token_hash = hash_session_token(token)

        session = db.scalar(
            select(UserSession)
            .where(
                UserSession.session_token_hash
                == token_hash
            )
        )

        if session and session.revoked_at is None:
            session.revoked_at = datetime.now(
                timezone.utc
            )

            db.commit()

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )

    return {
        "message": "Logged out",
    }


@router.post("/login")
def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):

    print(f"{'*'*100} \nAttempting login for email: {credentials.email}{'*'*100}")

    user = authenticate_user(
        db=db,
        email=credentials.email,
        password=credentials.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    print(f"{'*'*100} \nLogin successful for email: {credentials.email}{'*'*100}")
    session_token = create_session(
        db=db,
        user=user,
        ip_address=request.client.host
        if request.client
        else None,
        user_agent=request.headers.get(
            "user-agent"
        ),
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=60 * 60 * 24,
        path="/",
    )
    print(f"{'*'*100} \nSetting session cookie for email: {credentials.email}{'*'*100}")
    return {
        "message": "Login successful",
    }

@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user



@router.post("/logout-all")
def logout_all(
    response: Response,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):

    revoke_all_sessions(
        db,
        current_user.user_id,
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )

    return {
        "message": "All sessions revoked"
    }


def cleanup_sessions(db: Session):

    now = datetime.now(timezone.utc)

    db.execute(
        delete(UserSession)
        .where(
            UserSession.expires_at < now
        )
    )

    db.commit()    