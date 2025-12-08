"""Запрос участником кредов."""
import os
import sys

from aiogram import F, Router, types
from sqlalchemy import select

from models import User, async_session

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


get_creds = Router()


@get_creds.message(F.text == "🔐 Получить логин и пароль")
async def get_credentials(message: types.Message):
    """Получение логина и пароля."""

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar()

        if user:
            await message.answer(
                f"Ваши данные:\n"
                f"Login: `{user.login_id}`\n"
                f"Password: `{user.plain_password}`",
                parse_mode="Markdown",
            )
        else:
            await message.answer("Вы еще не зарегистрированы.")
