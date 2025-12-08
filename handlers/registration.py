"""Регистрация участников в системе."""
import os
import re
import secrets
import string
import sys

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from sqlalchemy import select

from config import GRADES, Registration, SCHOOLS, bot, try_delete
from keyboards import (
    get_agreement_kb,
    get_cancel_kb,
    get_confirm_kb,
    get_main_kb,
    get_selection_kb,
)
from models import User, async_session

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


registration = Router()


def generate_credentials(db_id):
    """Генерация логина и пароля."""

    login = f"user{db_id}"
    alphabet = string.ascii_letters + string.digits
    password = "".join(secrets.choice(alphabet) for i in range(20))
    return login, password


@registration.message(Command("start"))
async def cmd_start(message: types.Message):
    """Нажатие на кнопку старт или /start."""

    await message.answer(
        "Добро пожаловать...", reply_markup=get_main_kb(message.from_user.id)
    )


@registration.message(Registration.full_name, F.text == "🏠 На главную")
@registration.message(Registration.phone, F.text == "🏠 На главную")
@registration.message(Registration.school, F.text == "🏠 На главную")
@registration.message(Registration.grade, F.text == "🏠 На главную")
@registration.message(Registration.email, F.text == "🏠 На главную")
@registration.message(Registration.waiting_for_agreement, F.text == "🏠 На главную")
@registration.message(Registration.confirm, F.text == "🏠 На главную")
async def cancel_registration(message: types.Message, state: FSMContext):
    """Отмена регистрации и выход в меню."""

    await state.clear()
    await try_delete(bot, message.chat.id, message.message_id)
    await message.answer(
        "🏠 Регистрация прервана. Вы вернулись в главное меню.",
        reply_markup=get_main_kb(message.from_user.id)
    )


@registration.message(F.text == "📝 Зарегистрироваться")
async def start_register(message: types.Message, state: FSMContext):
    """Регистрация пользователя, ввод Ф.И.О."""

    await try_delete(bot, message.chat.id, message.message_id)

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        if result.scalar():
            msg = await message.answer(
                "Вы уже зарегистрированы! Получите логин и пароль."
            )
            return

    await state.set_state(Registration.full_name)

    msg = await message.answer(
        "Введите ваше Ф.И.О. (полностью):",
        reply_markup=get_cancel_kb()
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.message(Registration.full_name)
async def process_name(message: types.Message, state: FSMContext):
    """Сохранение Ф.И.О. и ввод номера телефона."""

    data = await state.get_data()

    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])
    await try_delete(bot, message.chat.id, message.message_id)

    await state.update_data(full_name=message.text)

    await state.set_state(Registration.phone)
    msg = await message.answer(
        "Введите номер телефона в формате +7 (999) 000-00-00:",
        reply_markup=get_cancel_kb()
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.message(Registration.phone)
async def process_phone(message: types.Message, state: FSMContext):
    """Проверка введенного телефона и сохранение, ввод уч.зав."""

    data = await state.get_data()
    pattern = r"^\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}$"

    if not re.match(pattern, message.text):
        await try_delete(bot, message.chat.id, message.message_id)
        if "last_bot_msg_id" in data:
            await try_delete(bot, message.chat.id, data["last_bot_msg_id"])

        msg = await message.answer(
            "Ошибка формата! Введите строго в указанном формате: "
            "+7 (999) 000-00-00",
            reply_markup=get_cancel_kb()
        )
        await state.update_data(last_bot_msg_id=msg.message_id)
        return

    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])
    await try_delete(bot, message.chat.id, message.message_id)

    await state.update_data(phone=message.text)
    await state.set_state(Registration.school)

    msg = await message.answer(
        "Выберите учебное заведение:",
        reply_markup=get_selection_kb(SCHOOLS[:10], "school"),
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.callback_query(Registration.school, F.data.startswith("school_"))
async def process_school(callback: types.CallbackQuery, state: FSMContext):
    """Сохранение уч.зав. и выбор класса/курса."""

    school_name = callback.data.split("_")[1]
    await state.update_data(school=school_name)
    await state.set_state(Registration.grade)

    await callback.message.edit_text(
        f"Выбрано: {school_name}\nТеперь выберите класс/курс:",
        reply_markup=get_selection_kb(GRADES, "grade"),
    )


@registration.callback_query(Registration.grade, F.data.startswith("grade_"))
async def process_grade(callback: types.CallbackQuery, state: FSMContext):
    """Сохранение класса/курса и ввод эл.почты."""

    grade_name = callback.data.split("_")[1]
    await state.update_data(grade=grade_name)
    await state.set_state(Registration.email)

    await try_delete(bot, callback.message.chat.id, callback.message.message_id)

    msg = await callback.message.answer(
        f"Выбрано: {grade_name}\nВведите вашу электронную почту:",
        reply_markup=get_cancel_kb()
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.message(Registration.email)
async def process_email(message: types.Message, state: FSMContext):
    """Проверка эл.почты и переход к СОГЛАШЕНИЮ."""

    data = await state.get_data()

    if "@" not in message.text or "." not in message.text:
        await try_delete(bot, message.chat.id, message.message_id)
        return

    await state.update_data(email=message.text)

    await state.set_state(Registration.waiting_for_agreement)

    await try_delete(bot, message.chat.id, message.message_id)
    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])

    user_data_msg = (
        "<b>Проверьте ваши данные:</b>\n"
        f"ФИО: {data.get('full_name')}\n"
        f"Телефон: {data.get('phone')}\n"
        f"Уч. заведение: {data.get('school')}\n"
        f"Класс/Курс: {data.get('grade')}\n"
        f"Email: {message.text}\n\n"
        "Для продолжения необходимо ознакомиться и принять согласие на обработку персональных данных."
    )

    msg = await message.answer(
        user_data_msg,
        reply_markup=get_agreement_kb(),
        parse_mode="HTML"
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.message(Registration.waiting_for_agreement, F.text == "📄 Согласие на обработку персональных данных")
async def send_agreement_file(message: types.Message):
    """Отправляет PDF файл с соглашением."""

    try:
        pdf_file = FSInputFile("Соглашение.pdf")
        await message.answer_document(pdf_file, caption="Пожалуйста, ознакомьтесь с соглашением.")
    except Exception as e:
        await message.answer("⚠️ Файл соглашения не найден. Обратитесь к организаторам.")
        print(f"Ошибка отправки файла: {e}")


@registration.message(Registration.waiting_for_agreement, F.text == "✅ Я принимаю условия")
async def accept_agreement(message: types.Message, state: FSMContext):
    """Переход к финальному подтверждению."""

    data = await state.get_data()

    await try_delete(bot, message.chat.id, message.message_id)
    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])

    await state.set_state(Registration.confirm)

    msg = await message.answer(
        "Условия приняты. Нажмите кнопку ниже для завершения регистрации.",
        reply_markup=get_confirm_kb()
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.message(Registration.confirm, F.text == "🚀 Подтвердить введенные данные")
async def finish_registration(message: types.Message, state: FSMContext):
    """Сохранение данных в БД."""

    data = await state.get_data()

    await try_delete(bot, message.chat.id, message.message_id)
    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])

    try:
        async with async_session() as session:
            new_user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                full_name=data["full_name"],
                phone=data["phone"],
                school=data["school"],
                grade=data["grade"],
                email=data["email"],
            )
            session.add(new_user)
            await session.flush()
            login, pwd = generate_credentials(new_user.id)
            new_user.login_id = login
            new_user.plain_password = pwd
            await session.commit()
    except Exception as e:
        await message.answer(f"Ошибка сохранения в БД: {e}")
        return

    await state.clear()

    await message.answer(
        f"✅ Регистрация успешна!\n\n"
        f"👤 Ваш User ID: `{login}`\n"
        f"🔑 Ваш Пароль: `{pwd}`\n\n"
        f"Сохраните эти данные!",
        parse_mode="Markdown",
        reply_markup=get_main_kb(message.from_user.id),
    )
