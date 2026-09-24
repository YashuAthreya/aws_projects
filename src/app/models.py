
from app.database import Base

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Index, String

 
class User(Base):
    __tablename__ = "user_table"

    user_id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_name: Mapped[str | None] = mapped_column(String, nullable=True)

    user_email: Mapped[str | None] = mapped_column(String, nullable=True)

    mobile_number: Mapped[str | None] = mapped_column(String, nullable=True)

    password: Mapped[str | None] = mapped_column(String, nullable=True)

    job_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    resume_loc: Mapped[str | None] = mapped_column(String, nullable=True)

    is_active: Mapped[bool | None] = mapped_column(
        Boolean,
        default=True,
        nullable=True,
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

class JobPosting(Base):
    __tablename__ = "job_posting"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool | None] = mapped_column(
        Boolean,
        default=True,
        nullable=True,
    )

    emb_generated: Mapped[bool | None] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int | None] = mapped_column(nullable=True)

    session_token_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)

    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)