import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv


load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS").split()]
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# { user_id_автора: [ [(admin_id, message_id), ...], [...] ] }
active_alerts: dict[int, list[list[tuple[int, int]]]] = {}
# { user_id_участника: admin_id_организатора }
active_dialogs: dict[int, int] = {}

SCHOOLS = [
    "Школа №1",
    "Лицей №5",
    "Гимназия №12",
    "МГУ",
    "МГТУ им. Баумана",
]

GRADES = [
    f"{i} класс" for i in range(1, 12)
    ] + [
        f"{i} курс" for i in range(1, 5)
        ]


# FSM
class Registration(StatesGroup):
    """Регистрации нового пользователя в системе."""

    full_name = State()
    phone = State()
    school = State()
    grade = State()
    email = State()
    waiting_for_agreement = State()
    confirm = State()


class Report(StatesGroup):
    """Подача участником репорта (жалобы) о нарушении."""

    offender_username = State()
    description = State()
    proof = State()
    last_bot_msg_id = State()


class Support(StatesGroup):
    """Обращение участника к организаторам."""

    waiting_for_message = State()
    last_bot_msg_id = State()


class AdminPanel(StatesGroup):
    """Режимы работы организатора через панель управления бота."""

    waiting_for_broadcast_content = State()
    waiting_for_user_search = State()
    waiting_for_user_id = State()
    in_dialog = State()


class AdminState(StatesGroup):
    """Для единственного ответа на репорт/жалобу ."""

    waiting_for_reply = State()


class UserState(StatesGroup):
    """Режимы работы участника с организатором."""

    in_dialog_with_admin = State()


async def try_delete(bot: Bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass
