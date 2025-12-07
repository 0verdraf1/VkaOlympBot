"""Участник пишет организатору."""
import sys
import os
from typing import List
from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import UserState, active_dialogs, bot
from keyboards import get_admin_dialog_kb


user_to_admin = Router()


@user_to_admin.message(UserState.in_dialog_with_admin)
async def user_message_proxy(
    message: types.Message,
    state: FSMContext,
    album: List[types.Message] = None
):
    """Проксирование сообщений участника админу."""

    user_id = message.from_user.id
    if message.text == "🏠 На главную": return

    target_admin_id = active_dialogs.get(user_id)
    if not target_admin_id:
        await message.answer(
            "Связь прервана. Ожидайте сообщения от организатора."
            )
        await state.clear()
        return

    # --- ФОРМИРОВАНИЕ ПОДПИСИ ---
    if message.from_user.username:
        user_sign = f"@{message.from_user.username}"
    else:
        # ID в теге code для копирования по клику
        user_sign = f"ID <code>{user_id}</code>"

    prefix = f"<b>Участник ({user_sign}):</b>\n"

    try:
        # 1. АЛЬБОМ
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
                    media_group.add_photo(media=msg.photo[-1].file_id, caption=caption_to_send, parse_mode="HTML")
                elif msg.document:
                    media_group.add_document(media=msg.document.file_id, caption=caption_to_send, parse_mode="HTML")
                elif msg.video:
                    media_group.add_video(media=msg.video.file_id, caption=caption_to_send, parse_mode="HTML")
                first = False
            
            await bot.send_media_group(target_admin_id, media=media_group.build())
            return

        # 2. ОБЫЧНОЕ
        if message.text:
            await bot.send_message(
                target_admin_id,
                f"{prefix}{message.text}",
                parse_mode="HTML",
                reply_markup=get_admin_dialog_kb(),
            )
        elif message.photo:
            text = message.caption or ""
            await bot.send_photo(
                target_admin_id,
                message.photo[-1].file_id,
                caption=f"{prefix}{text}",
                parse_mode="HTML",
                reply_markup=get_admin_dialog_kb(),
            )
        elif message.document:
            text = message.caption or ""
            await bot.send_document(
                target_admin_id,
                message.document.file_id,
                caption=f"{prefix}{text}",
                parse_mode="HTML",
                reply_markup=get_admin_dialog_kb(),
            )
        else:
            await message.answer("Тип сообщения не поддерживается.")
 
    except Exception as e:
        print(f"DEBUG: Ошибка пересылки админу: {e}")
