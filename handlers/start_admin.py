"""Реакции на кнопки Админ-панели и Назад в меню."""
import os
import sys

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from keyboards import get_admin_panel_kb, get_main_kb

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


start_admin = Router()


@start_admin.message(F.text == "🦾 Админ-панель")
async def open_admin_panel(message: types.Message, state: FSMContext):
    """Админ-панель."""

    if message.from_user.id not in ADMIN_IDS:
        return

    await state.clear()

    await message.answer("🦾 Админ-панель открыта.", reply_markup=get_admin_panel_kb())


@start_admin.message(F.text == "⬅️ Назад в меню")
async def exit_admin(message: types.Message, state: FSMContext):
    """Назад в меню."""

    await state.clear()
    await message.answer("Вышли в главное меню.", reply_markup=get_main_kb(message.from_user.id))
