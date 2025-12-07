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
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import GRADES, SCHOOLS, bot, Registration, try_delete
from keyboards import get_main_kb, get_selection_kb, get_cancel_kb
from models import User, async_session


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


# --- ВАЖНО: ЭТОТ ХЕНДЛЕР ДОЛЖЕН БЫТЬ ВЫШЕ ОСТАЛЬНЫХ ---
# Он перехватывает нажатие "На главную" в любом состоянии регистрации
@registration.message(Registration.full_name, F.text == "🏠 На главную")
@registration.message(Registration.phone, F.text == "🏠 На главную")
@registration.message(Registration.school, F.text == "🏠 На главную")
@registration.message(Registration.grade, F.text == "🏠 На главную")
@registration.message(Registration.email, F.text == "🏠 На главную")
@registration.message(Registration.confirm, F.text == "🏠 На главную")
async def cancel_registration(message: types.Message, state: FSMContext):
    """Отмена регистрации и выход в меню."""
    await state.clear()
    await try_delete(bot, message.chat.id, message.message_id)
    await message.answer(
        "🏠 Регистрация прервана. Вы вернулись в главное меню.",
        reply_markup=get_main_kb(message.from_user.id)
    )
# --------------------------------------------------------


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

    # Важно: здесь мы отправляем Selection KB, но у пользователя может остаться возможность ввода текста
    # "На главную" будет перехвачено верхним хендлером
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

    # При переходе к вводу текста снова показываем кнопку "На главную"
    # Т.к. предыдущее сообщение было edit_text с инлайн кнопками,
    # нам нужно отправить новое сообщение с Reply-клавиатурой (кнопкой снизу)
    
    # Удаляем старое инлайн сообщение, чтобы было чисто
    await try_delete(bot, callback.message.chat.id, callback.message.message_id)
    
    msg = await callback.message.answer(
        f"Выбрано: {grade_name}\nВведите вашу электронную почту:",
        reply_markup=get_cancel_kb()
    )
    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.message(Registration.email)
async def process_email(message: types.Message, state: FSMContext):
    """Проверка эл.почты и подтверждение введенных данных."""
    
    data = await state.get_data()

    if "@" not in message.text or "." not in message.text:
        await try_delete(bot, message.chat.id, message.message_id)
        # Можно отправить уведомление об ошибке
        return

    await state.update_data(email=message.text)
    await state.set_state(Registration.confirm)

    await try_delete(bot, message.chat.id, message.message_id)

    if "last_bot_msg_id" in data:
        await try_delete(bot, message.chat.id, data["last_bot_msg_id"])

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Подтвердить введенные данные")],
            [KeyboardButton(text="🏠 На главную")]
        ],
        resize_keyboard=True,
    )
    msg = await message.answer(
        "Все данные заполнены. Нажмите кнопку ниже.", reply_markup=kb
    )

    await state.update_data(last_bot_msg_id=msg.message_id)


@registration.message(
    Registration.confirm,
    F.text == "Подтвердить введенные данные"
)
async def finish_registration(message: types.Message, state: FSMContext):
    """Сохранение данных в БД, вывод финального сообщения."""
    
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
        await message.answer(f"Ошибка БД: {e}")
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