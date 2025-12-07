"""Общие хендлеры навигации."""
import sys
import os
from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from keyboards import get_main_kb
from config import active_dialogs, bot, dp

common_router = Router()

@common_router.message(F.text == "🏠 На главную")
async def go_to_main(message: types.Message, state: FSMContext):
    """Сброс состояния и выход в главное меню."""

    data = await state.get_data()
    user_id = message.from_user.id

    dialog_user_id = data.get("dialog_user_id")
    if dialog_user_id:
        if dialog_user_id in active_dialogs:
            del active_dialogs[dialog_user_id]
        try:
            user_key = StorageKey(bot_id=bot.id, chat_id=dialog_user_id, user_id=dialog_user_id)
            user_ctx = FSMContext(storage=dp.storage, key=user_key)
            await user_ctx.clear()
            await bot.send_message(dialog_user_id, "🔕 <b>Диалог завершен (собеседник вышел).</b>", parse_mode="HTML")
        except: pass

    if user_id in active_dialogs:
        admin_id = active_dialogs[user_id]
        del active_dialogs[user_id]
        try:
            await bot.send_message(admin_id, "🔕 <b>Участник покинул диалог.</b>", parse_mode="HTML")
        except: pass

    await state.clear()

    await message.answer(
        "🏠 Вы вернулись в главное меню. Все действия отменены.",
        reply_markup=get_main_kb(message.from_user.id)
    )