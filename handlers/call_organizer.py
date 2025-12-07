"""Взаимодействие участника с организаторами."""
import sys
import os
from aiogram import F, types, Router
from sqlalchemy import select

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from keyboards import get_organizer_kb, get_main_kb
from models import User, async_session


call = Router()


@call.message(F.text == "🔔 Связь с организаторами")
async def contact_menu(message: types.Message):
    """Выбор причины для связи с организаторами (с проверкой регистрации)."""

    # Проверка регистрации
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar()

    if not user:
        await message.answer(
            "⛔ <b>Доступ запрещен.</b>\n"
            "Этот раздел доступен только зарегистрированным участникам.\n"
            "Пожалуйста, нажмите кнопку <b>Зарегистрироваться</b> в главном меню.",
            parse_mode="HTML",
            reply_markup=get_main_kb(message.from_user.id)
        )
        return

    await message.answer(
        "Выберите категорию:",
        reply_markup=get_organizer_kb()
    )
