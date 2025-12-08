"""Запуск бота."""
import asyncio

from sqlalchemy import select

from config import banned_ids, bot, dp
from handlers.main_handler import router
from middlewares import BanMiddleware, MediaGroupMiddleware
from models import User, async_session, init_db


async def load_banned_users():
    """Загрузка списка забаненных ID в кэш при старте."""

    async with async_session() as session:
        result = await session.execute(select(User.telegram_id).where(User.is_banned is True))
        ids = result.scalars().all()
        for banned_id in ids:
            banned_ids.add(banned_id)
    print(f"Загружено {len(banned_ids)} забаненных пользователей.")


async def main():
    """Инициализация БД и точка входа."""

    await init_db()
    await load_banned_users()
    dp.message.outer_middleware(BanMiddleware())
    dp.callback_query.outer_middleware(BanMiddleware())

    dp.message.middleware(MediaGroupMiddleware(latency=0.5))

    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
