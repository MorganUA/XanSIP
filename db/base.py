from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from bot.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,          # True — если хочешь видеть SQL в консоли при отладке
    pool_size=10,
    max_overflow=20,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass
