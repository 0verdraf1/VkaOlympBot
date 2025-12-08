"""Посредники."""
import asyncio
from typing import Any, Awaitable, Callable, Dict, List

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import active_dialogs, banned_ids
from keyboards import get_banned_kb


BLOCKED_BUTTONS = [
    "📝 Зарегистрироваться",
    "🔐 Получить логин и пароль",
    "🔔 Связь с организаторами",
    "🦾 Админ-панель",
    "🏠 На главную",
    "👀 Сообщить о нарушении правил",
    "🆘 У меня проблема"
]


class BanMiddleware(BaseMiddleware):
    """Блокирует доступ забаненным пользователям."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:

        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        if user.id in banned_ids:

            if user.id in active_dialogs:

                if isinstance(event, CallbackQuery):
                    await event.answer(
                        "⛔ Вы забанены и находитесь в диалоге с организатором.",
                        show_alert=True
                    )
                    return

                if isinstance(event, Message) and event.text in BLOCKED_BUTTONS:
                    await event.answer(
                        "⛔ Вы забанены и находитесь в диалоге с организатором."
                    )
                    return

                return await handler(event, data)

            if isinstance(event, CallbackQuery):
                if event.data == "banned_appeal":
                    return await handler(event, data)
                else:
                    await event.answer("⛔ Вы забанены.", show_alert=True)
                    return

            if isinstance(event, Message):
                await event.answer(
                    "⛔ <b>Вы забанены.</b>\n"
                    "Вы не можете использовать бота.",
                    parse_mode="HTML",
                    reply_markup=get_banned_kb()
                )
                return

        return await handler(event, data)


class MediaGroupMiddleware(BaseMiddleware):
    """Собирает медиа в альбом для отправки группой."""

    def __init__(self, latency: float = 0.5):
        self.latency = latency
        self.album_data: Dict[str, List[Message]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:

        if not isinstance(event, Message):
            return await handler(event, data)

        if not event.media_group_id:
            return await handler(event, data)

        media_group_id = event.media_group_id

        if media_group_id not in self.album_data:
            self.album_data[media_group_id] = [event]
            await asyncio.sleep(self.latency)

            album = self.album_data.pop(media_group_id)
            data["album"] = album

            return await handler(event, data)

        self.album_data[media_group_id].append(event)
        return
