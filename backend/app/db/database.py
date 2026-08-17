from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


# SQLite needs this option when used with FastAPI
connect_args = {}

if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False
    }


# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args
)


# Create database session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# Base class for all SQLAlchemy models
Base = declarative_base()


# Dependency used by FastAPI routes
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()