"""Система доставки ответа на репорт/просьбу."""
import os
import sys

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from config import (
    AdminPanel,
    AdminState,
    UserState,
    active_alerts,
    active_dialogs,
    admin_ids_set,
    bot,
    dp,
)
from keyboards import get_admin_dialog_kb

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


router_reply = Router()


@router_reply.callback_query(F.data.startswith("reply_"))
async def admin_start_reply(callback: types.CallbackQuery, state: FSMContext):
    """Инициализация связи с участником и уведомление др. организаторам"""

    if callback.from_user.id not in admin_ids_set:
        await callback.answer("У вас нет прав.", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])
    current_admin_id = callback.from_user.id
    admin_username = callback.from_user.username

    active_dialogs[user_id] = current_admin_id

    try:
        user_storage_key = StorageKey(
            bot_id=callback.bot.id, chat_id=user_id, user_id=user_id
        )

        user_ctx = FSMContext(storage=dp.storage, key=user_storage_key)

        await user_ctx.set_state(UserState.in_dialog_with_admin)

        await user_ctx.update_data(dialog_admin_id=current_admin_id)

        await bot.send_message(
            user_id,
            "🔔 <b>С вами связывается организатор.</b>\n"
            "Диалог с организатором:",
            parse_mode="HTML",
        )

    except Exception as e:
        print(f"CRITICAL ERROR связывания: {e}")
        await callback.message.answer("❌ Ошибка связи с пользователем.")
        if user_id in active_dialogs:
            del active_dialogs[user_id]
        return

    await state.update_data(dialog_user_id=user_id)
    await state.set_state(AdminPanel.in_dialog)

    clicked_msg_id = callback.message.message_id
    user_alert_groups = active_alerts.get(user_id, [])
    target_group = []

    for group in user_alert_groups:
        if (current_admin_id, clicked_msg_id) in group:
            target_group = group
            break

    if not target_group:
        target_group = [(current_admin_id, clicked_msg_id)]

    current_text = callback.message.caption or callback.message.text or ""

    signature = (
        f"\n\n✅ <b>Организатор @{admin_username} "
        f"отреагировал на алерт.</b>"
    )

    final_text = current_text
    if final_text and "отреагировал на алерт" not in final_text:
        final_text += signature

    for admin_chat_id, msg_id in target_group:
        try:
            await bot.edit_message_text(
                chat_id=admin_chat_id,
                message_id=msg_id,
                text=final_text,
                parse_mode="HTML",
                reply_markup=None,
            )
        except Exception:
            try:
                await bot.edit_message_caption(
                    chat_id=admin_chat_id,
                    message_id=msg_id,
                    caption=final_text,
                    parse_mode="HTML",
                    reply_markup=None,
                )
            except Exception as e:
                print(
                    f"Не удалось обновить сообщение"
                    f"у админа {admin_chat_id}: {e}"
                    )

    try:
        if user_id in active_alerts and target_group in active_alerts[user_id]:
            active_alerts[user_id].remove(target_group)
            if not active_alerts[user_id]:
                del active_alerts[user_id]
    except Exception:
        pass

    await callback.message.answer(
        f"Диалог с участником (ID {user_id}) начат.",
        reply_markup=get_admin_dialog_kb()
    )
    await callback.answer()


@router_reply.message(AdminState.waiting_for_reply)
async def admin_send_reply(message: types.Message, state: FSMContext):
    """Ответ организатора на репорт/просьбу."""

    if message.from_user.id not in admin_ids_set:
        return

    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if not target_user_id:
        await message.answer("Ошибка: Не найден ID пользователя.")
        await state.clear()
        return

    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=f"🔔 <b>Ответ от организаторов:</b>\n\n{message.text}",
            parse_mode="HTML",
        )
        await message.answer("✅ Ответ успешно доставлен.")
    except Exception as e:
        await message.answer(
            f"❌ Не удалось отправить (возможно, пользователь"
            f"заблокировал бота): {e}"
        )

    await state.clear()
