"""Поиск организатором диалога с участником."""
import os
import sys

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import select

from config import ADMIN_IDS, AdminPanel, UserState, active_dialogs, bot, dp
from keyboards import get_admin_dialog_kb, get_admin_panel_kb, get_search_method_kb
from models import User, async_session

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


search = Router()


@search.message(F.text == "👤 Общение с участником")
async def start_dialog_search_menu(message: types.Message):
    """Запускает поиск."""

    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(
        "Выберите метод поиска участника:",
        reply_markup=get_search_method_kb()
    )


@search.callback_query(F.data == "search_by_username")
async def setup_username_search(callback: types.CallbackQuery, state: FSMContext):
    """Ввод username."""

    await state.set_state(AdminPanel.waiting_for_user_search)
    await callback.message.edit_text(
        "Введите @username пользователя:",
        reply_markup=None
    )
    await callback.answer()


@search.callback_query(F.data == "search_by_id")
async def setup_id_search(callback: types.CallbackQuery, state: FSMContext):
    """Ввод id."""

    await state.set_state(AdminPanel.waiting_for_user_id)
    await callback.message.edit_text(
        "Введите Telegram ID пользователя (число):",
        reply_markup=None
    )
    await callback.answer()


@search.message(AdminPanel.waiting_for_user_search)
async def process_username_search(message: types.Message, state: FSMContext):
    """Поиск по username."""

    username_input = message.text.strip().replace("@", "")

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.username == username_input)
        )
        user = result.scalar()

    if not user:
        await message.answer(
            f"❌ Пользователь @{username_input} не найден в базе.",
            reply_markup=get_admin_panel_kb(),
        )
        await state.clear()
        return

    await start_dialog_with_user(message, state, user)


@search.message(AdminPanel.waiting_for_user_id)
async def process_id_search(message: types.Message, state: FSMContext):
    """Поиск по id."""

    id_input = message.text.strip()

    if not id_input.isdigit():
        await message.answer("❌ ID должен быть числом. Попробуйте еще раз или нажмите '🏠 На главную'.")
        return

    user_id = int(id_input)

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar()

    if not user:
        await message.answer(
            f"❌ Пользователь с ID {user_id} не найден в базе.",
            reply_markup=get_admin_panel_kb(),
        )
        await state.clear()
        return

    await start_dialog_with_user(message, state, user)


async def start_dialog_with_user(message: types.Message, state: FSMContext, user):
    """Общая логика соединения для обоих методов поиска."""

    active_dialogs[user.telegram_id] = message.from_user.id

    await state.set_state(AdminPanel.in_dialog)
    await state.update_data(dialog_user_id=user.telegram_id)

    try:
        user_key = StorageKey(
            bot_id=bot.id, chat_id=user.telegram_id, user_id=user.telegram_id
        )
        user_state = FSMContext(storage=dp.storage, key=user_key)
        await user_state.set_state(UserState.in_dialog_with_admin)

        await bot.send_message(
            user.telegram_id,
            "🔔 <b>С вами связывается организатор.</b>\n"
            "Диалог с организатором:",
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"DEBUG: Не удалось переключить стейт юзера: {e}")

    user_label = f"@{user.username}" if user.username else f"ID {user.telegram_id}"
    await message.answer(
        f"Диалог с участником {user_label} начат.\n"
        "Все ваши сообщения будут пересылаться ему.",
        reply_markup=get_admin_dialog_kb(),
    )
