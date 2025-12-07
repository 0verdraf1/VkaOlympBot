"""Система отправки сообщений о помощи."""
import sys
import os
from typing import List
from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.media_group import MediaGroupBuilder

sys.path.append(os.path.join(os.path.dirname(__file__), '...'))
from config import Support, bot, active_alerts, try_delete, ADMIN_IDS
from keyboards import get_main_kb


user_help = Router()


@user_help.callback_query(F.data == "contact_support")
async def start_support(callback: types.CallbackQuery, state: FSMContext):
    """Ввод описания проблемы."""
    await state.set_state(Support.waiting_for_message)
    await callback.message.edit_text(
        "Опишите вашу проблему одним сообщением (можно прикрепить фото), "
        "и организатор ответит вам здесь.",
        reply_markup=None,
    )
    await state.update_data(last_bot_msg_id=callback.message.message_id)
    await callback.answer()


@user_help.message(Support.waiting_for_message)
async def forward_to_admin(
    message: types.Message, 
    state: FSMContext,
    album: List[types.Message] = None
):
    """Рассылка проблем организаторам."""
    data = await state.get_data()

    # --- ИЩЕМ ТЕКСТ ПОЛЬЗОВАТЕЛЯ ---
    user_text = ""
    if album:
        for msg in album:
            if msg.caption:
                user_text = msg.caption
                break
    else:
        user_text = message.text or message.caption or ""

    if not user_text and not album and not message.photo and not message.document:
        user_text = "Без текста"

    # Шапка сообщения для админа
    header_text = (
        f"🆘 <b>ВОПРОС В ПОДДЕРЖКУ</b>\n"
        f"От: ID {message.from_user.id} (@{message.from_user.username})\n\n"
    )
    
    # Полный текст сообщения (Шапка + Текст юзера)
    full_text_msg = f"{header_text}Текст:\n{user_text}" if user_text else header_text + "Текст: (только медиа)"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="💬 Ответить пользователю", callback_data=f"reply_{message.from_user.id}")
        ]]
    )

    sent_messages_info = []

    for admin_id in ADMIN_IDS:
        try:
            # 1. АЛЬБОМ
            if album:
                # Сначала шлем альбом (без текста, чтобы не дублировать, или с текстом)
                media_group = MediaGroupBuilder()
                for msg in album:
                    if msg.photo: media_group.add_photo(media=msg.photo[-1].file_id)
                    elif msg.document: media_group.add_document(media=msg.document.file_id)
                    elif msg.video: media_group.add_video(media=msg.video.file_id)
                
                await bot.send_media_group(chat_id=admin_id, media=media_group.build())
                
                # Затем шлем текст вопроса с кнопкой (чтобы кнопка была видна и работала)
                sent_msg = await bot.send_message(
                    chat_id=admin_id,
                    text=full_text_msg, # Текст вопроса здесь
                    parse_mode="HTML",
                    reply_markup=kb
                )
                sent_messages_info.append((admin_id, sent_msg.message_id))

            # 2. ФОТО/ДОКУМЕНТ (Одиночные)
            elif message.photo or message.document:
                # Если одно фото - шлем фото с подписью и кнопкой
                file_id = message.photo[-1].file_id if message.photo else message.document.file_id
                method = bot.send_photo if message.photo else bot.send_document
                
                sent_msg = await method(
                    chat_id=admin_id,
                    photo=file_id if message.photo else None,
                    document=file_id if message.document else None,
                    caption=full_text_msg,
                    parse_mode="HTML",
                    reply_markup=kb
                )
                sent_messages_info.append((admin_id, sent_msg.message_id))

            # 3. ПРОСТО ТЕКСТ
            else:
                sent_msg = await bot.send_message(
                    chat_id=admin_id,
                    text=full_text_msg, 
                    parse_mode="HTML",
                    reply_markup=kb
                )
                sent_messages_info.append((admin_id, sent_msg.message_id))

        except Exception as e:
            print(f"Ошибка при отправке админу {admin_id}: {e}")

    # Сохранение и чистка
    if sent_messages_info:
        if message.from_user.id not in active_alerts:
            active_alerts[message.from_user.id] = []
        active_alerts[message.from_user.id].append(sent_messages_info)

    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])
        
    if album:
        for msg in album: await try_delete(bot, message.chat.id, msg.message_id)
    else:
        await try_delete(bot, message.chat.id, message.message_id)

    await state.clear()
    await message.answer("Сообщение отправлено. Ожидайте ответа.", reply_markup=get_main_kb(message.from_user.id))
