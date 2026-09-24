# app/admin/auth_service.py

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.models import Admin
from app.auth.security import verify_password


def authenticate_admin(
    db: Session,
    admin_name: str,
    admin_password: str,
) -> Admin | None:

    admin = db.scalar(
        select(Admin).where(Admin.admin_name == admin_name)
    )

    if not admin or not admin.admin_password:
        return None

    if admin_password != admin.admin_password:  
        return None

    # if not verify_password(admin_password, admin.admin_password):
    #     return None

    return admin
