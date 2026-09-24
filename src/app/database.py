import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


# Set DATABASE_URL in your environment, for example:

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required.")


class Base(DeclarativeBase):
	"""Base class for all SQLAlchemy ORM models."""


engine = create_engine(
	DATABASE_URL,
	pool_pre_ping=True,
)

SessionLocal = sessionmaker(
	bind=engine,
	autocommit=False,
	autoflush=False,
	expire_on_commit=False,
)


def initialize_database() -> None:
	"""Create missing tables for the mapped SQLAlchemy models."""
	# Import app.models here so Base.metadata includes all ORM tables.
	from app import models  # noqa: F401
	Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
	"""FastAPI dependency that provides and closes a database session."""
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()


