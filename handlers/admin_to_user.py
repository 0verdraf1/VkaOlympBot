"""Организатор пишет участнику."""
import sys
import os
from typing import List
from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.utils.media_group import MediaGroupBuilder

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import AdminPanel, active_dialogs, bot, dp
from keyboards import get_admin_panel_kb


admin_to_user = Router()


@admin_to_user.message(AdminPanel.in_dialog)
async def admin_message_proxy(
    message: types.Message, 
    state: FSMContext,
    album: List[types.Message] = None
):
    """Проксирование сообщений админа участнику (текст, фото, альбомы)."""

    data = await state.get_data()
    user_id = data.get("dialog_user_id")

    # --- 1. ВЫХОД ИЗ ДИАЛОГА ---
    if message.text == "❌ Закончить диалог":
        if user_id in active_dialogs:
            del active_dialogs[user_id]

        await state.clear()
        await message.answer(
            "Диалог завершен.",
            reply_markup=get_admin_panel_kb()
        )

        if user_id:
            try:
                user_key = StorageKey(
                    bot_id=bot.id,
                    chat_id=user_id, user_id=user_id
                )
                user_ctx = FSMContext(storage=dp.storage, key=user_key)
                await user_ctx.clear()

                await bot.send_message(
                    user_id,
                    "🔕 <b>Диалог с организатором завершен.</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        return

    # Защита от кнопки "На главную" (если она вдруг есть)
    if message.text == "🏠 На главную":
        return

    # --- 2. ПЕРЕСЫЛКА СООБЩЕНИЙ ---
    if user_id:
        try:
            prefix = "<b>Организатор:</b> "
            
            # А) ЕЛСИ ЭТО АЛЬБОМ (ГРУППА ФОТО)
            if album:
                media_group = MediaGroupBuilder()
                # Мы хотим добавить префикс только к первому сообщению в альбоме
                # или к тому, где есть текст.
                first = True 
                
                for msg in album:
                    # Ищем подпись (если она есть)
                    text = msg.caption or ""
                    
                    # Если это первое фото в альбоме, добавляем префикс
                    if first:
                        caption = f"{prefix}{text}"
                        first = False
                    else:
                        caption = text  # К остальным фото префикс не лепим, чтобы не спамить

                    if msg.photo:
                        media_group.add_photo(
                            media=msg.photo[-1].file_id, 
                            caption=caption, 
                            parse_mode="HTML"
                        )
                    elif msg.document:
                        media_group.add_document(
                            media=msg.document.file_id, 
                            caption=caption, 
                            parse_mode="HTML"
                        )
                
                await bot.send_media_group(user_id, media=media_group.build())
                return

            # Б) ЕСЛИ ЭТО ОБЫЧНОЕ СООБЩЕНИЕ
            if message.text:
                await bot.send_message(
                    user_id, f"{prefix}{message.text}", parse_mode="HTML"
                )
            elif message.photo:
                # [ИСПРАВЛЕНИЕ] Правильная логика для caption
                if message.caption:
                    caption = f"{prefix}{message.caption}"
                else:
                    caption = prefix # Теперь переменная точно создается

                await bot.send_photo(
                    user_id,
                    message.photo[-1].file_id,
                    caption=caption,
                    parse_mode="HTML",
                )
            elif message.document:
                if message.caption:
                    caption = f"{prefix}{message.caption}"
                else:
                    caption = prefix # [ИСПРАВЛЕНИЕ]

                await bot.send_document(
                    user_id,
                    message.document.file_id,
                    caption=caption,
                    parse_mode="HTML",
                )
            else:
                await message.answer("Тип сообщения не поддерживается.")
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            await message.answer(
                "Ошибка доставки (возможно пользователь заблокировал бота)."
            )
