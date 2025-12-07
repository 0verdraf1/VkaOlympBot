"""Логика бана и разбана участников."""
import sys
import os
from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import (
    AdminBanSystem, 
    bot, 
    ADMIN_IDS, 
    banned_ids, # Импортируем глобальный кэш
)
from keyboards import get_admin_panel_kb, get_search_method_kb
from models import User, BannedUser, async_session

admin_ban_router = Router()

# ==================== БАН УЧАСТНИКА ====================

@admin_ban_router.message(F.text == "⛔ Бан участника")
async def start_ban_process(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    
    await message.answer(
        "Выберите метод поиска участника для БАНА:",
        reply_markup=get_search_method_kb()
    )
    await state.set_state(AdminBanSystem.waiting_for_ban_search_method)

# --- Выбор метода (ID или Username) ---
@admin_ban_router.callback_query(AdminBanSystem.waiting_for_ban_search_method)
async def ban_method_chosen(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "search_by_id":
        await state.set_state(AdminBanSystem.waiting_for_ban_user_id)
        await callback.message.edit_text("Введите ID участника для бана:")
    else:
        await state.set_state(AdminBanSystem.waiting_for_ban_username)
        await callback.message.edit_text("Введите @username участника для бана:")
    await callback.answer()

# --- Поиск по ID ---
@admin_ban_router.message(AdminBanSystem.waiting_for_ban_user_id)
async def process_ban_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен быть числом.")
        return
    
    user_id = int(message.text)
    await check_and_proceed_ban(message, state, user_id=user_id)

# --- Поиск по Username ---
@admin_ban_router.message(AdminBanSystem.waiting_for_ban_username)
async def process_ban_username(message: types.Message, state: FSMContext):
    username = message.text.strip().replace("@", "")
    await check_and_proceed_ban(message, state, username=username)

# --- Общая проверка и переход к причине ---
async def check_and_proceed_ban(message: types.Message, state: FSMContext, user_id=None, username=None):
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

    # Сохраняем найденного юзера
    await state.update_data(target_user=user)
    await state.set_state(AdminBanSystem.waiting_for_ban_reason)
    await message.answer(f"Пользователь найден: {user.full_name} (ID: {user.telegram_id})\n\nВведите <b>Причину бана</b>:", parse_mode="HTML")

# --- Причина бана ---
@admin_ban_router.message(AdminBanSystem.waiting_for_ban_reason)
async def process_ban_reason(message: types.Message, state: FSMContext):
    await state.update_data(ban_reason=message.text)
    await state.set_state(AdminBanSystem.waiting_for_ban_proof)
    await message.answer("Прикрепите <b>доказательства</b> (текст, фото или скриншот):", parse_mode="HTML")

# --- Доказательства и ФИНАЛ ---
@admin_ban_router.message(AdminBanSystem.waiting_for_ban_proof, F.text | F.photo)
async def process_ban_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_user: User = data['target_user']
    reason = data['ban_reason']
    
    # Обработка доказательств
    proof = "Текст: " + message.text if message.text else f"Photo ID: {message.photo[-1].file_id}"
    if message.caption: proof += f" | Caption: {message.caption}"

    admin_info = f"@{message.from_user.username}, ID_{message.from_user.id}"

    async with async_session() as session:
        # 1. Обновляем статус в таблице users
        stmt = update(User).where(User.id == target_user.id).values(is_banned=True)
        await session.execute(stmt)

        # 2. Upsert в таблицу users_banned (Создаем или Обновляем)
        # Если юзер уже был забанен ранее, мы обновим причину и админа
        banned_user_data = {
            "user_id": target_user.telegram_id,
            "username": target_user.username,
            "reason": reason,
            "admin_who_banned": admin_info,
            "proof": proof,
            "admin_who_unbanned": None # Сбрасываем разбан, так как баним снова
        }
        
        # PostgreSQL UPSERT
        insert_stmt = insert(BannedUser).values(**banned_user_data)
        do_update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=['user_id'], # Поле, по которому ищем дубликаты
            set_=banned_user_data # Обновляем все поля новыми данными
        )
        await session.execute(do_update_stmt)
        await session.commit()

    # 3. Обновляем кэш в памяти
    banned_ids.add(target_user.telegram_id)

    await message.answer(
        f"✅ Пользователь <b>{target_user.full_name}</b> (ID {target_user.telegram_id}) успешно <b>ЗАБАНЕН</b>.",
        parse_mode="HTML",
        reply_markup=get_admin_panel_kb()
    )
    
    # Пытаемся уведомить пользователя (если он не заблочил бота)
    try:
        await bot.send_message(target_user.telegram_id, "⛔ <b>Вы были забанены администратором.</b>", parse_mode="HTML")
    except: pass
    
    await state.clear()


# ==================== РАЗБАН УЧАСТНИКА ====================

@admin_ban_router.message(F.text == "✅ Разбан участника")
async def start_unban_process(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    
    await message.answer(
        "Выберите метод поиска участника для РАЗБАНА:",
        reply_markup=get_search_method_kb()
    )
    await state.set_state(AdminBanSystem.waiting_for_unban_search_method)

@admin_ban_router.callback_query(AdminBanSystem.waiting_for_unban_search_method)
async def unban_method_chosen(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "search_by_id":
        await state.set_state(AdminBanSystem.waiting_for_unban_user_id)
        await callback.message.edit_text("Введите ID участника для разбана:")
    else:
        await state.set_state(AdminBanSystem.waiting_for_unban_username)
        await callback.message.edit_text("Введите @username участника для разбана:")
    await callback.answer()

@admin_ban_router.message(AdminBanSystem.waiting_for_unban_user_id)
async def process_unban_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен быть числом.")
        return
    await process_unban_final(message, state, user_id=int(message.text))

@admin_ban_router.message(AdminBanSystem.waiting_for_unban_username)
async def process_unban_username(message: types.Message, state: FSMContext):
    username = message.text.strip().replace("@", "")
    await process_unban_final(message, state, username=username)

async def process_unban_final(message: types.Message, state: FSMContext, user_id=None, username=None):
    admin_info = f"@{message.from_user.username}, ID_{message.from_user.id}"

    async with async_session() as session:
        # Ищем юзера
        query = select(User)
        if user_id: query = query.where(User.telegram_id == user_id)
        else: query = query.where(User.username == username)
        
        result = await session.execute(query)
        user = result.scalar()

        if not user:
            await message.answer("❌ Пользователь не найден.", reply_markup=get_admin_panel_kb())
            await state.clear()
            return

        # 1. Снимаем бан в users
        user.is_banned = False
        
        # 2. Обновляем инфу в users_banned (кто разбанил)
        stmt = update(BannedUser).where(BannedUser.user_id == user.telegram_id).values(
            admin_who_unbanned=admin_info
        )
        await session.execute(stmt)
        await session.commit()

        # 3. Убираем из кэша
        if user.telegram_id in banned_ids:
            banned_ids.remove(user.telegram_id)

    await message.answer(
        f"✅ Пользователь <b>{user.full_name}</b> успешно <b>РАЗБАНЕН</b>.",
        parse_mode="HTML",
        reply_markup=get_admin_panel_kb()
    )
    try:
        await bot.send_message(user.telegram_id, "✅ <b>Вы были разбанены!</b> Доступ восстановлен.", parse_mode="HTML")
    except: pass

    await state.clear()