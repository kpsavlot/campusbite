from app.core.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args = {"check_same_thread": False} if is_sqlite else {}
)

SessionLocal = sessionmaker(
    bind= engine,
    autoflush= False,
    autocommit= False,
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        if is_sqlite:
            db.execute(text("PRAGMA foreign_keys=ON"))
        yield db
    finally:
        db.close()