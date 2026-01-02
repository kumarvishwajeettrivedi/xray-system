"""
Database configuration for X-Ray API

Uses PostgreSQL with SQLAlchemy async support.

Environment variable:
    DATABASE_URL - PostgreSQL connection string
    Default: postgresql+asyncpg://xray:xray_password@localhost/xray_db
"""
 
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Database URL - Must be set in environment
from dotenv import load_dotenv
load_dotenv()  # Load .env file if present

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL is not set. Please create a .env file with your connection string.\n"
        "Example: DATABASE_URL=postgresql+asyncpg://user:pass@localhost/xray_db"
    )

# Create async engine with connection pooling
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()


async def get_db():
    """Dependency for getting database sessions"""
    async with async_session_maker() as session:
        yield session


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
