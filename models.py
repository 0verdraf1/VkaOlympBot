"""Модели для базы данных"""
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, Text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

from config import DATABASE_URL

Base = declarative_base()


class User(Base):
    """Задание необходимых столбцов в БД."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    school = Column(String, nullable=False)
    grade = Column(String, nullable=False)
    email = Column(String, nullable=False)

    login_id = Column(String, unique=True)
    plain_password = Column(String)

    is_banned = Column(Boolean, default=False)


class BannedUser(Base):
    """Таблица забаненных участников."""
    
    __tablename__ = "users_banned"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, nullable=False) # Telegram ID
    username = Column(String, nullable=True)
    reason = Column(Text, nullable=False)
    
    # Кто забанил: "@username, ID_11111"
    admin_who_banned = Column(String, nullable=False) 
    
    # Доказательства (file_id или текст)
    proof = Column(Text, nullable=True) 
    
    # Кто разбанил: "@username, ID_11111" (заполняется при разбане)
    admin_who_unbanned = Column(String, nullable=True)


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
    )


async def init_db():
    """Инициализируем БД."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)