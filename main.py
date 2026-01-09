"""Запуск бота."""
import asyncio

from sqlalchemy import select

from config import admin_ids_set, banned_ids, bot, dp
from handlers.main_handler import router
from middlewares import BanMiddleware, MediaGroupMiddleware
from models import User, async_session, init_db


async def load_cache():
    """Загрузка кэшей (забаненные и админы) при старте."""

    async with async_session() as session:

        res_banned = await session.execute(select(User.telegram_id).where(User.is_banned is True))
        for uid in res_banned.scalars().all():
            banned_ids.add(uid)

        res_admins = await session.execute(select(User.telegram_id).where(User.is_admin is True))
        for uid in res_admins.scalars().all():
            admin_ids_set.add(uid)

    print(f"Кэш загружен: {len(banned_ids)} забаненных, {len(admin_ids_set)} админов.")


async def main():
    """Инициализация БД и точка входа."""

    await init_db()
    await load_cache()
    dp.message.outer_middleware(BanMiddleware())
    dp.callback_query.outer_middleware(BanMiddleware())

    dp.message.middleware(MediaGroupMiddleware(latency=0.5))

    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
