"""
Database engine and session management.

Uses SQLModel (SQLAlchemy 2.x under the hood) with the psycopg2 driver.
The engine is created once at import time; table creation is deferred to
init_db() which is called during the FastAPI lifespan startup.
"""

import logging
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

logger = logging.getLogger("finmate.database")

logger.info("Creating SQLAlchemy engine for %s", settings.database_url.split("@")[-1])
engine = create_engine(settings.database_url, echo=False)


def init_db() -> None:
    """Create all SQLModel tables if they don't already exist."""
    logger.info("Running SQLModel.metadata.create_all() …")
    SQLModel.metadata.create_all(engine)
    logger.info("All tables verified / created")


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a transactional DB session."""
    with Session(engine) as session:
        yield session
