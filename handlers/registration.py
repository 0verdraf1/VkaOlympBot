"""Регистрация участников в системе."""
import re
import string
import secrets
import sys
import os

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from aiogram.types import FSInputFile

from config import GRADES, bot, Registration, try_delete
from keyboards import (
    get_main_kb,
    get_selection_kb,
    get_cancel_kb,
    get_agreement_kb,
    get_confirm_kb,
)

from models import User, async_session

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

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
@registration.message(Registration.place_of_study, F.text == "🏠 На главную")
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
        reply_markup=get_main_kb(message.from_user.id),
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
        "Введите ваше Ф.И.О. (полностью):", reply_markup=get_cancel_kb()
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
        "Введите номер телефона:\n"
        "(Номер должен начинаться с <b>+7</b> или с <b>8</b>)",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.message(Registration.phone)
async def process_phone(message: types.Message, state: FSMContext):
    """Проверка телефона, форматирование и переход к вводу города."""

    data = await state.get_data()

    user_input = message.text.strip()
    if not (user_input.startswith("+7") or user_input.startswith("8")):
        await try_delete(bot, message.chat.id, message.message_id)
        if "last_bot_msg_id" in data:
            await try_delete(bot, message.chat.id, data["last_bot_msg_id"])

        msg = await message.answer(
            "⚠️ Ошибка формата!\nНомер должен начинаться с <b>+7</b> или <b>8</b>.\nПопробуйте еще раз:",
            reply_markup=get_cancel_kb(),
            parse_mode="HTML",
        )
        await state.update_data(last_bot_msg_id=msg.message_id)
        return

    raw_digits = re.sub(r"\D", "", user_input)
    clean_num = ""
    error_msg = None

    if len(raw_digits) == 11:
        if raw_digits[0] in ["7", "8"]:
            clean_num = "7" + raw_digits[1:]
        else:
            error_msg = "Некорректный код страны."
    else:
        error_msg = f"Неверное количество цифр (введено: {len(raw_digits)}, нужно: 11)."

    if error_msg:
        await try_delete(bot, message.chat.id, message.message_id)
        if "last_bot_msg_id" in data:
            await try_delete(bot, message.chat.id, data["last_bot_msg_id"])

        msg = await message.answer(
            f"⚠️ {error_msg}\nПопробуйте еще раз:", reply_markup=get_cancel_kb()
        )
        await state.update_data(last_bot_msg_id=msg.message_id)
        return

    formatted_phone = f"+{clean_num[0]} ({clean_num[1:4]}) {clean_num[4:7]}-{clean_num[7:9]}-{clean_num[9:]}"

    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])
    await try_delete(bot, message.chat.id, message.message_id)

    await state.update_data(phone=formatted_phone)

    await state.set_state(Registration.place_of_study)

    msg = await message.answer(
        "Введите населенный пункт, где находится ваше учебное заведение\n"
        "(Например: г. Москва ИЛИ г. Обнинск Калужской области):",
        reply_markup=get_cancel_kb(),
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.message(Registration.place_of_study)
async def process_place_of_study(message: types.Message, state: FSMContext):
    """Сохранение населенного пункта и переход к вводу школы (текстом)."""

    data = await state.get_data()

    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])
    await try_delete(bot, message.chat.id, message.message_id)

    await state.update_data(place_of_study=message.text)

    await state.set_state(Registration.school)

    msg = await message.answer(
        "Введите полное название вашего учебного заведения:",
        reply_markup=get_cancel_kb(),
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.message(Registration.school)
async def process_school(message: types.Message, state: FSMContext):
    """Сохранение школы (текст) и выбор класса/курса."""

    data = await state.get_data()

    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])
    await try_delete(bot, message.chat.id, message.message_id)

    await state.update_data(school=message.text)
    await state.set_state(Registration.grade)

    msg = await message.answer(
        "Выберите класс или курс:",
        reply_markup=get_selection_kb(GRADES, "grade"),
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.callback_query(Registration.grade, F.data.startswith("grade_"))
async def process_grade(callback: types.CallbackQuery, state: FSMContext):
    """Сохранение класса/курса и ввод эл.почты."""

    grade_name = callback.data.split("_")[1]
    await state.update_data(grade=grade_name)
    await state.set_state(Registration.email)

    await try_delete(bot, callback.message.chat.id, callback.message.message_id)

    msg = await callback.message.answer(
        f"Выбрано: {grade_name}\nВведите вашу электронную почту:",
        reply_markup=get_cancel_kb(),
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
        f"Нас. пункт, в котором обучаетесь: {data.get('place_of_study')}\n"
        f"Уч. заведение: {data.get('school')}\n"
        f"Класс/Курс: {data.get('grade')}\n"
        f"Email: {message.text}\n\n"
        "Для продолжения необходимо ознакомиться и принять согласие на обработку персональных данных."
    )

    msg = await message.answer(
        user_data_msg, reply_markup=get_agreement_kb(), parse_mode="HTML"
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.message(
    Registration.waiting_for_agreement,
    F.text == "📄 Согласие на обработку персональных данных",
)
async def send_agreement_file(message: types.Message):
    """Отправляет PDF файл с соглашением."""

    try:
        pdf_file = FSInputFile("Соглашение.pdf")
        await message.answer_document(
            pdf_file, caption="Пожалуйста, ознакомьтесь с соглашением."
        )
    except Exception as e:
        await message.answer("⚠️ Файл соглашения не найден. Обратитесь к организаторам.")
        print(f"Ошибка отправки файла: {e}")


@registration.message(
    Registration.waiting_for_agreement, F.text == "✅ Я принимаю условия"
)
async def accept_agreement(message: types.Message, state: FSMContext):
    """Переход к финальному подтверждению."""

    data = await state.get_data()

    await try_delete(bot, message.chat.id, message.message_id)
    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])

    await state.set_state(Registration.confirm)

    msg = await message.answer(
        "Условия приняты. Нажмите кнопку ниже для завершения регистрации.",
        reply_markup=get_confirm_kb(),
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
                place_of_study=data["place_of_study"],  # Сохраняем город
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
