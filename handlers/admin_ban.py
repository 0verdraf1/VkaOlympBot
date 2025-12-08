"""Логика бана и разбана участников."""
import os
import sys
from typing import List

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from config import ADMIN_IDS, AdminBanSystem, banned_ids, bot
from keyboards import get_admin_panel_kb, get_search_method_kb
from models import BannedUser, User, async_session

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


admin_ban_router = Router()


@admin_ban_router.message(F.text == "⛔ Бан участника")
async def start_ban_process(message: types.Message, state: FSMContext):
    """Бан участника."""

    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "Выберите метод поиска участника для БАНА:",
        reply_markup=get_search_method_kb()
    )
    await state.set_state(AdminBanSystem.waiting_for_ban_search_method)


@admin_ban_router.callback_query(AdminBanSystem.waiting_for_ban_search_method)
async def ban_method_chosen(callback: types.CallbackQuery, state: FSMContext):
    """Выбор метода бана (по username/id)."""

    if callback.data == "search_by_id":
        await state.set_state(AdminBanSystem.waiting_for_ban_user_id)
        await callback.message.edit_text("Введите ID участника для бана:")
    else:
        await state.set_state(AdminBanSystem.waiting_for_ban_username)
        await callback.message.edit_text("Введите @username участника для бана:")
    await callback.answer()


@admin_ban_router.message(AdminBanSystem.waiting_for_ban_user_id)
async def process_ban_id(message: types.Message, state: FSMContext):
    """Поиск по id."""

    if not message.text.isdigit():
        await message.answer("ID должен быть числом.")
        return

    user_id = int(message.text)
    await check_and_proceed_ban(message, state, user_id=user_id)


@admin_ban_router.message(AdminBanSystem.waiting_for_ban_username)
async def process_ban_username(message: types.Message, state: FSMContext):
    """Поиск по username."""

    username = message.text.strip().replace("@", "")
    await check_and_proceed_ban(message, state, username=username)


async def check_and_proceed_ban(message: types.Message, state: FSMContext, user_id=None, username=None):
    """Проверка на налчиие в базе и переход к причине бана."""

    async with async_session() as session:
        query = select(User)
        if user_id:
            query = query.where(User.telegram_id == user_id)
        else:
            query = query.where(User.username == username)

        result = await session.execute(query)
        user = result.scalar()

    if not user:
        await message.answer("❌ Пользователь не найден в базе.", reply_markup=get_admin_panel_kb())
        await state.clear()
        return

    await state.update_data(target_user=user)
    await state.set_state(AdminBanSystem.waiting_for_ban_reason)

    user_sign = f"@{user.username}" if user.username else "(Без username)"
    await message.answer(
        f"Пользователь найден: <b>{user.full_name}</b>\n"
        f"ID: <code>{user.telegram_id}</code> {user_sign}\n\n"
        "Введите <b>Причину бана</b>:",
        parse_mode="HTML"
    )


@admin_ban_router.message(AdminBanSystem.waiting_for_ban_reason)
async def process_ban_reason(message: types.Message, state: FSMContext):
    """Выбор причины бана."""

    await state.update_data(ban_reason=message.text)
    await state.set_state(AdminBanSystem.waiting_for_ban_proof)
    await message.answer("Прикрепите <b>доказательства</b> (текст, фото или скриншот):", parse_mode="HTML")


@admin_ban_router.message(AdminBanSystem.waiting_for_ban_proof, F.text | F.photo)
async def process_ban_finish(
    message: types.Message,
    state: FSMContext,
    album: List[types.Message] = None
):
    """
    1. Формирование алерта бана;
    2. Запись в БД;
    3. Рассылка алерта всем админам.
    """

    data = await state.get_data()
    target_user: User = data['target_user']
    reason = data['ban_reason']

    proof_db = ""
    proof_text_for_alert = ""

    if album:
        file_ids = [m.photo[-1].file_id for m in album if m.photo]
        proof_db = f"Album ({len(file_ids)} photos): {', '.join(file_ids)}"

        for msg in album:
            if msg.caption:
                proof_text_for_alert = msg.caption
                proof_db += f" | Caption: {msg.caption}"
                break
    elif message.photo:
        proof_db = f"Photo ID: {message.photo[-1].file_id}"
        if message.caption:
            proof_text_for_alert = message.caption
            proof_db += f" | Caption: {message.caption}"
    elif message.text:
        proof_text_for_alert = message.text
        proof_db = f"Text: {message.text}"

    if not proof_text_for_alert:
        proof_text_for_alert = "(Без текстового описания, только медиа)"

    admin_username = f"@{message.from_user.username}" if message.from_user.username else "(Без username)"
    admin_info = f"{admin_username}, ID <code>{message.from_user.id}</code>"
    admin_info_db = f"@{message.from_user.username}, ID {message.from_user.id}"

    async with async_session() as session:
        stmt = update(User).where(User.id == target_user.id).values(is_banned=True)
        await session.execute(stmt)

        banned_user_data = {
            "user_id": target_user.telegram_id,
            "username": target_user.username,
            "reason": reason,
            "admin_who_banned": admin_info_db,
            "proof": proof_db,
            "admin_who_unbanned": None
        }

        insert_stmt = insert(BannedUser).values(**banned_user_data)
        do_update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=['user_id'],
            set_=banned_user_data
        )
        await session.execute(do_update_stmt)
        await session.commit()

    banned_ids.add(target_user.telegram_id)

    target_user_sign = f"@{target_user.username}" if target_user.username else "(Без username)"

    ban_alert = (
        f"⛔ <b>ЗАБАНЕН УЧАСТНИК</b>\n\n"
        f"👤 <b>ФИО:</b> {target_user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{target_user.telegram_id}</code>\n"
        f"📧 <b>Username:</b> {target_user_sign}\n\n"
        f"📝 <b>Причина:</b> {reason}\n"
        f"👮‍♂️ <b>Кто забанил:</b> {admin_info}\n"
        f"📂 <b>Доказательства:</b> {proof_text_for_alert}"
    )

    for admin_id in ADMIN_IDS:
        try:
            if album:
                media_group = MediaGroupBuilder()
                first = True
                for msg in album:
                    caption = ban_alert if first else None
                    if msg.photo:
                        media_group.add_photo(media=msg.photo[-1].file_id, caption=caption, parse_mode="HTML")
                    elif msg.document:
                        media_group.add_document(media=msg.document.file_id, caption=caption, parse_mode="HTML")
                    first = False
                await bot.send_media_group(chat_id=admin_id, media=media_group.build())
            elif message.photo:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=message.photo[-1].file_id,
                    caption=ban_alert,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(chat_id=admin_id, text=ban_alert, parse_mode="HTML")
        except Exception:
            pass

    await message.answer(
        f"✅ Пользователь <b>{target_user.full_name}</b> успешно забанен.\nУведомление отправлено всем администраторам.",
        reply_markup=get_admin_panel_kb(),
        parse_mode="HTML"
    )

    try:
        await bot.send_message(target_user.telegram_id, "⛔ <b>Вы были забанены администратором.</b>", parse_mode="HTML")
    except Exception:
        pass

    await state.clear()


@admin_ban_router.message(F.text == "✅ Разбан участника")
async def start_unban_process(message: types.Message, state: FSMContext):
    """Разбан участника."""

    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "Выберите метод поиска участника для РАЗБАНА:",
        reply_markup=get_search_method_kb()
    )
    await state.set_state(AdminBanSystem.waiting_for_unban_search_method)


@admin_ban_router.callback_query(AdminBanSystem.waiting_for_unban_search_method)
async def unban_method_chosen(callback: types.CallbackQuery, state: FSMContext):
    """Выбор метода разбана (по username/id)."""

    if callback.data == "search_by_id":
        await state.set_state(AdminBanSystem.waiting_for_unban_user_id)
        await callback.message.edit_text("Введите ID участника для разбана:")
    else:
        await state.set_state(AdminBanSystem.waiting_for_unban_username)
        await callback.message.edit_text("Введите @username участника для разбана:")
    await callback.answer()


@admin_ban_router.message(AdminBanSystem.waiting_for_unban_user_id)
async def process_unban_id(message: types.Message, state: FSMContext):
    """Поиск по id."""

    if not message.text.isdigit():
        await message.answer("ID должен быть числом.")
        return
    await process_unban_final(message, state, user_id=int(message.text))


@admin_ban_router.message(AdminBanSystem.waiting_for_unban_username)
async def process_unban_username(message: types.Message, state: FSMContext):
    """Поиск по username."""

    username = message.text.strip().replace("@", "")
    await process_unban_final(message, state, username=username)


async def process_unban_final(message: types.Message, state: FSMContext, user_id=None, username=None):
    """
    1. Формирование алерта разбана;
    2. Запись в БД;
    3. Рассылка алерта всем админам.
    """

    admin_username = f"@{message.from_user.username}" if message.from_user.username else "(Без username)"
    admin_info = f"{admin_username}, ID <code>{message.from_user.id}</code>"
    admin_info_db = f"@{message.from_user.username}, ID {message.from_user.id}"

    async with async_session() as session:
        query = select(User)
        if user_id:
            query = query.where(User.telegram_id == user_id)
        else:
            query = query.where(User.username == username)

        result = await session.execute(query)
        user = result.scalar()

        if not user:
            await message.answer("❌ Пользователь не найден.", reply_markup=get_admin_panel_kb())
            await state.clear()
            return

        user.is_banned = False
        stmt = update(BannedUser).where(BannedUser.user_id == user.telegram_id).values(
            admin_who_unbanned=admin_info_db
        )
        await session.execute(stmt)
        await session.commit()

        if user.telegram_id in banned_ids:
            banned_ids.remove(user.telegram_id)

    user_sign = f"@{user.username}" if user.username else "(Без username)"
    unban_alert = (
        f"✅ <b>РАЗБАНЕН УЧАСТНИК</b>\n\n"
        f"👤 <b>ФИО:</b> {user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{user.telegram_id}</code>\n"
        f"📧 <b>Username:</b> {user_sign}\n\n"
        f"👮‍♂️ <b>Кто разбанил:</b> {admin_info}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=unban_alert, parse_mode="HTML")
        except Exception:
            pass

    await message.answer(
        f"✅ Пользователь <b>{user.full_name}</b> успешно разбанен.",
        parse_mode="HTML",
        reply_markup=get_admin_panel_kb()
    )
    try:
        await bot.send_message(user.telegram_id, "✅ <b>Вы были разбанены!</b> Доступ восстановлен.", parse_mode="HTML")
    except Exception:
        pass

    await state.clear()
