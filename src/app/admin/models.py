# app/admin/models.py

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Admin(Base):
    __tablename__ = "admins"

    admin_id: Mapped[int] = mapped_column(primary_key=True, index=True)

    admin_name: Mapped[str | None] = mapped_column(String, nullable=True)

    admin_password: Mapped[str | None] = mapped_column(String, nullable=True)
