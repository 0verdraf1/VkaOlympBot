"""Система подачи репортов."""
import os
import sys
from typing import List

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.media_group import MediaGroupBuilder

from config import Report, active_alerts, admin_ids_set, bot, try_delete
from keyboards import get_main_kb

sys.path.append(os.path.join(os.path.dirname(__file__), '...'))


user_rep = Router()


@user_rep.callback_query(F.data == "report_violation")
async def start_report(callback: types.CallbackQuery, state: FSMContext):
    """Начало составления репорта."""

    await state.set_state(Report.offender_username)
    await callback.message.edit_text(
        "Введите имя пользователя нарушителя (начинается с @):",
        reply_markup=None,
    )
    await state.update_data(last_bot_msg_id=callback.message.message_id)
    await callback.answer()


@user_rep.message(Report.offender_username)
async def process_report_username(message: types.Message, state: FSMContext):
    """Ввод username."""

    data = await state.get_data()
    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])
    await try_delete(bot, message.chat.id, message.message_id)

    if not message.text.startswith("@"):
        msg = await message.answer("❌ Имя должно начинаться с @. Попробуйте снова:")
        await state.update_data(last_bot_msg_id=msg.message_id)
        return

    await state.update_data(offender_username=message.text)
    await state.set_state(Report.description)
    msg = await message.answer("Опишите нарушение:")
    await state.update_data(last_bot_msg_id=msg.message_id)


@user_rep.message(Report.description)
async def process_report_desc(message: types.Message, state: FSMContext):
    """Ввод описания."""

    data = await state.get_data()
    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])
    await try_delete(bot, message.chat.id, message.message_id)

    await state.update_data(description=message.text)
    await state.set_state(Report.proof)
    msg = await message.answer(
        "Отправьте доказательства (фото, скриншот) или напишите 'нет'."
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@user_rep.message(Report.proof, F.photo | F.text)
async def process_report_proof(
    message: types.Message, state: FSMContext,
    album: List[types.Message] = None
):
    """
    1. Формирования алерта репорта;
    2. Рассылка репортов организаторам.
    """

    data = await state.get_data()

    user_proof_text = ""
    if album:
        for msg in album:
            if msg.caption:
                user_proof_text = msg.caption
                break
    else:
        user_proof_text = message.text or message.caption or ""

    user_link = f"(@{message.from_user.username})" if message.from_user.username else "(Без username)"

    report_text = (
        f"🚨 <b>НОВЫЙ РЕПОРТ</b>\n"
        f"От кого: ID <code>{message.from_user.id}</code> {user_link}\n"
        f"Нарушитель: {data['offender_username']}\n"
        f"Описание: {data['description']}"
    )

    if user_proof_text and user_proof_text.lower() != "нет":
        report_text += f"\nДок-ва (текст): {user_proof_text}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="💬 Ответить автору жалобы", callback_data=f"reply_{message.from_user.id}")
        ]]
    )

    sent_messages_info = []

    for admin_id in admin_ids_set:
        try:
            if album:
                media_group = MediaGroupBuilder()
                for msg in album:
                    if msg.photo:
                        media_group.add_photo(media=msg.photo[-1].file_id)
                    elif msg.document:
                        media_group.add_document(media=msg.document.file_id)

                await bot.send_media_group(chat_id=admin_id, media=media_group.build())

                sent_msg = await bot.send_message(
                    chat_id=admin_id,
                    text=report_text,
                    parse_mode="HTML",
                    reply_markup=kb
                )
                sent_messages_info.append((admin_id, sent_msg.message_id))

            elif message.photo:
                sent_msg = await bot.send_photo(
                    chat_id=admin_id,
                    photo=message.photo[-1].file_id,
                    caption=report_text,
                    parse_mode="HTML",
                    reply_markup=kb
                )
                sent_messages_info.append((admin_id, sent_msg.message_id))

            else:
                sent_msg = await bot.send_message(
                    chat_id=admin_id,
                    text=report_text,
                    parse_mode="HTML",
                    reply_markup=kb
                )
                sent_messages_info.append((admin_id, sent_msg.message_id))

        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

    if sent_messages_info:
        if message.from_user.id not in active_alerts:
            active_alerts[message.from_user.id] = []
        active_alerts[message.from_user.id].append(sent_messages_info)

    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])

    if album:
        for msg in album:
            await try_delete(bot, message.chat.id, msg.message_id)
    else:
        await try_delete(bot, message.chat.id, message.message_id)

    await state.clear()
    await message.answer("Ваш репорт отправлен организаторам.", reply_markup=get_main_kb(message.from_user.id))
