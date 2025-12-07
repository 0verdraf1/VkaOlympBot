import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv


load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(id) for id in admin_ids_str.split()] if admin_ids_str else []
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# СЛОВАРИ И КЭШИ
active_alerts: dict[int, list[list[tuple[int, int]]]] = {}
active_dialogs: dict[int, int] = {}

# Кэш забаненных ID (заполняется при старте бота), чтобы не делать запрос к БД на каждое сообщение
banned_ids: set[int] = set()

SCHOOLS = [
    "Школа №1",
    "Лицей №5",
    "Гимназия №12",
    "МГУ",
    "МГТУ им. Баумана",
]

GRADES = [f"{i} класс" for i in range(1, 12)] + [f"{i} курс" for i in range(1, 5)]


# --- FSM ---

class Registration(StatesGroup):
    full_name = State()
    phone = State()
    school = State()
    grade = State()
    email = State()
    waiting_for_agreement = State()
    confirm = State()


class Report(StatesGroup):
    offender_username = State()
    description = State()
    proof = State()
    last_bot_msg_id = State()


class Support(StatesGroup):
    waiting_for_message = State()
    last_bot_msg_id = State()


class AdminPanel(StatesGroup):
    waiting_for_broadcast_content = State()
    waiting_for_user_search = State()
    waiting_for_user_id = State()
    in_dialog = State()


class AdminBanSystem(StatesGroup):
    """Состояния для системы бана/разбана."""

    waiting_for_ban_search_method = State()
    waiting_for_ban_user_id = State()
    waiting_for_ban_username = State()
    waiting_for_ban_reason = State()
    waiting_for_ban_proof = State()

    waiting_for_unban_search_method = State()
    waiting_for_unban_user_id = State()
    waiting_for_unban_username = State()


class AdminState(StatesGroup):
    waiting_for_reply = State()


class UserState(StatesGroup):
    in_dialog_with_admin = State()


async def try_delete(bot: Bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass
