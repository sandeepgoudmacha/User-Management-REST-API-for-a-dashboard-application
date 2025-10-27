"""Database configuration and connection management."""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, DECIMAL, ARRAY
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgresUUID
from sqlalchemy.types import TypeDecorator, String as SQLString
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import uuid

from app.config import get_settings

# Database engine and session
engine = None
async_session = None

Base = declarative_base()


# Cross-database compatible types
class UUID(TypeDecorator):
    """UUID type that works with both PostgreSQL and SQLite."""
    impl = SQLString
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresUUID(as_uuid=True))
        else:
            return dialect.type_descriptor(SQLString(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            return uuid.UUID(value)


class JSON(TypeDecorator):
    """JSON type that works with both PostgreSQL and SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            return json.loads(value)


class NameCheck(Base):
    """Name availability check record."""
    __tablename__ = "name_checks"
    
    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)
    provider_count = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    extra_data = Column(JSON())


class ProviderResult(Base):
    """Individual provider check result."""
    __tablename__ = "provider_results"
    
    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    check_id = Column(UUID(), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_type = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    available = Column(Boolean)
    confidence = Column(DECIMAL(3, 2))
    extra_data = Column(JSON())
    error_message = Column(Text)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())


class Suggestion(Base):
    """Name suggestion record."""
    __tablename__ = "suggestions"
    
    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    base_keywords = Column(JSON())
    suggestion = Column(String(100), nullable=False)
    score = Column(DECIMAL(3, 2), nullable=False)
    generated_by = Column(String(20), nullable=False)
    brandability_metrics = Column(JSON())
    availability_data = Column(JSON())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SimilarName(Base):
    """Similar name discovery record."""
    __tablename__ = "similar_names"
    
    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    base_name = Column(String(100), nullable=False)
    similar_name = Column(String(100), nullable=False)
    similarity_score = Column(DECIMAL(3, 2), nullable=False)
    found_in = Column(JSON())
    sources = Column(JSON(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class APIKey(Base):
    """API key management."""
    __tablename__ = "api_keys"
    
    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    key_hash = Column(String(64), unique=True, nullable=False)
    name = Column(String(100))
    plan = Column(String(20), default="free")
    active = Column(Boolean, default=True)
    requests_used = Column(Integer, default=0)
    last_used = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))


async def init_db():
    """Initialize database connection."""
    global engine, async_session
    
    settings = get_settings()
    
    # SQLite doesn't support pool_size and max_overflow
    if 'sqlite' in settings.database_url:
        engine = create_async_engine(
            settings.database_url,
            echo=settings.debug
        )
    else:
        engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=20,
            max_overflow=30
        )
    
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connection."""
    global engine
    if engine:
        await engine.dispose()


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_health() -> bool:
    """Check database connectivity."""
    try:
        async with async_session() as session:
            await session.execute("SELECT 1")
            return True
    except Exception:
        return False
