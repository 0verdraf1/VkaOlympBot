"""Обработка апелляций от забаненных."""
import os
import sys

from aiogram import F, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import active_alerts, admin_ids_set, bot

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


ban_appeal_router = Router()


@ban_appeal_router.callback_query(F.data == "banned_appeal")
async def process_ban_appeal(callback: types.CallbackQuery):
    """Забаненный нажимает кнопку связи."""

    if callback.from_user.id in active_alerts:
        await callback.answer(
            "⏳ Ваш запрос уже отправлен.\nОжидайте, пока организатор свяжется с вами.",
            show_alert=True
        )
        return

    await callback.message.answer(
        "Ваше сообщение будет рассмотрено, организаторы свяжутся с вами в этом чате."
    )
    await callback.answer()

    user = callback.from_user
    user_sign = f"@{user.username}" if user.username else "(Без username)"

    alert_text = (
        f"⛔ <b>ЗАПРОС ПО БАНУ</b>\n"
        f"От забаненного: ID <code>{user.id}</code> {user_sign}\n"
        f"Пользователь хочет обжаловать блокировку."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="💬 Связаться", callback_data=f"reply_{user.id}")
        ]]
    )

    sent_messages_info = []

    for admin_id in admin_ids_set:
        try:
            sent_msg = await bot.send_message(
                chat_id=admin_id,
                text=alert_text,
                parse_mode="HTML",
                reply_markup=kb
            )
            sent_messages_info.append((admin_id, sent_msg.message_id))
        except Exception:
            pass

    if sent_messages_info:
        if user.id not in active_alerts:
            active_alerts[user.id] = []
        active_alerts[user.id].append(sent_messages_info)
