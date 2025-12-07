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

    if message.text == "❌ Закончить диалог":
        if user_id in active_dialogs:
            del active_dialogs[user_id]

        await state.clear()
        await message.answer(
            "Диалог завершен.",
            reply_markup=get_admin_panel_kb() # Возвращаем меню админа
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

    if message.text == "🏠 На главную":
        return

    if user_id:
        try:
            prefix = "<b>Организатор:</b> "

            if album:
                media_group = MediaGroupBuilder()
                first = True
                for msg in album:
                    if msg.photo:
                        # Подпись добавляем только к первому фото
                        caption = f"{prefix}{msg.caption or ''}" if first else None
                        media_group.add_photo(
                            media=msg.photo[-1].file_id, 
                            caption=caption, 
                            parse_mode="HTML"
                        )
                        first = False
                    elif msg.document:
                        caption = f"{prefix}{msg.caption or ''}" if first else None
                        media_group.add_document(
                            media=msg.document.file_id, 
                            caption=caption, 
                            parse_mode="HTML"
                        )
                        first = False
                
                await bot.send_media_group(user_id, media=media_group.build())
                return

            if message.text:
                await bot.send_message(
                    user_id, f"{prefix}{message.text}", parse_mode="HTML"
                )
            elif message.photo:
                caption = f"{prefix}{message.caption or ''}"
                await bot.send_photo(
                    user_id,
                    message.photo[-1].file_id,
                    caption=caption,
                    parse_mode="HTML",
                )
            elif message.document:
                caption = f"{prefix}{message.caption or ''}"
                await bot.send_document(
                    user_id,
                    message.document.file_id,
                    caption=caption,
                    parse_mode="HTML",
                )
            else:
                await message.answer("Тип сообщения не поддерживается.")
                
        except Exception:
            await message.answer(
                "Ошибка доставки (возможно пользователь заблокировал бота)."
            )
