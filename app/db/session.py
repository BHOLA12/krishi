from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from app.core.config import settings

# Async engine & sessionmaker
engine_kwargs = {
    "pool_pre_ping": True,
    "echo": settings.DEBUG,
}
if settings.SQLALCHEMY_DATABASE_URI and settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    **engine_kwargs
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Sync engine & sessionmaker (for Celery, scripts, and Alembic migrations)
sync_engine_kwargs = {
    "pool_pre_ping": True,
}
if settings.SQLALCHEMY_DATABASE_URI_SYNC and settings.SQLALCHEMY_DATABASE_URI_SYNC.startswith("sqlite"):
    sync_engine_kwargs["connect_args"] = {"check_same_thread": False}

sync_engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI_SYNC,
    **sync_engine_kwargs
)

SessionLocalSync = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
)

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
