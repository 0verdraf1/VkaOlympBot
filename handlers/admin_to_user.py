"""Организатор пишет участнику."""
import os
import sys
from typing import List

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.utils.media_group import MediaGroupBuilder

from config import AdminPanel, active_dialogs, bot, dp
from keyboards import get_admin_panel_kb

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


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

    if message.text == "🏠 На главную":
        return

    if user_id:
        try:
            prefix = "<b>Организатор:</b>\n"

            if album:
                media_group = MediaGroupBuilder()

                found_caption = None
                for msg in album:
                    if msg.caption:
                        found_caption = msg.caption
                        break

                final_caption = f"{prefix}{found_caption}" if found_caption else prefix

                first = True
                for msg in album:
                    caption_to_send = final_caption if first else None

                    if msg.photo:
                        media_group.add_photo(
                            media=msg.photo[-1].file_id,
                            caption=caption_to_send,
                            parse_mode="HTML"
                        )
                    elif msg.document:
                        media_group.add_document(
                            media=msg.document.file_id,
                            caption=caption_to_send,
                            parse_mode="HTML"
                        )
                    elif msg.video:
                        media_group.add_video(
                            media=msg.video.file_id,
                            caption=caption_to_send,
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
                text = message.caption or ""
                await bot.send_photo(
                    user_id,
                    message.photo[-1].file_id,
                    caption=f"{prefix}{text}",
                    parse_mode="HTML",
                )
            elif message.document:
                text = message.caption or ""
                await bot.send_document(
                    user_id,
                    message.document.file_id,
                    caption=f"{prefix}{text}",
                    parse_mode="HTML",
                )
            else:
                await message.answer("Тип сообщения не поддерживается.")
        except Exception as e:
            print(f"Error admin_to_user: {e}")
            await message.answer(
                "Ошибка доставки (возможно пользователь заблокировал бота)."
            )
