from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler
from aiogram.types import Message, CallbackQuery
from datetime import datetime, timedelta
from database import is_banned, get_user_role, get_admin_settings
import logging

logger = logging.getLogger(__name__)

class BanMiddleware(BaseMiddleware):
    async def on_process_message(self, message: Message, data: dict):
        if is_banned(message.from_user.id):
            await message.answer("🚫 Вы забанены и не можете использовать бота.")
            raise CancelHandler()

    async def on_process_callback_query(self, call: CallbackQuery, data: dict):
        if is_banned(call.from_user.id):
            await call.answer("🚫 Вы забанены.", show_alert=True)
            raise CancelHandler()

class MaintenanceMiddleware(BaseMiddleware):
    async def on_process_message(self, message: Message, data: dict):
        if get_admin_settings("maintenance_enabled") == "1":
            role = get_user_role(message.from_user.id)
            if role not in ["owner", "admin", "moderator"]:
                reason = get_admin_settings("maintenance_reason") or "ведутся техработы"
                await message.answer(f"🛠 Ведутся технические работы.\nПричина: {reason}")
                raise CancelHandler()

    async def on_process_callback_query(self, call: CallbackQuery, data: dict):
        if get_admin_settings("maintenance_enabled") == "1":
            role = get_user_role(call.from_user.id)
            if role not in ["owner", "admin", "moderator"]:
                reason = get_admin_settings("maintenance_reason") or "ведутся техработы"
                await call.answer(f"🛠 Техработы: {reason}", show_alert=True)
                raise CancelHandler()

class RoleMiddleware(BaseMiddleware):
    async def on_process_message(self, message: Message, data: dict):
        data["user_role"] = get_user_role(message.from_user.id)

    async def on_process_callback_query(self, call: CallbackQuery, data: dict):
        data["user_role"] = get_user_role(call.from_user.id)

class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self):
        self.user_actions = {}  # user_id -> list of timestamps
        super().__init__()

    async def on_process_message(self, message: Message, data: dict):
        if message.text and message.text.startswith("/start"):
            args = message.get_args()
            if args and (args.startswith("ref_") or args.isdigit()):
                user_id = message.from_user.id
                now = datetime.now()
                timestamps = self.user_actions.get(user_id, [])
                timestamps = [t for t in timestamps if (now - t).seconds < 60]
                if len(timestamps) >= 2:
                    await message.answer("⏳ Слишком частые отправки. Подождите минуту.")
                    raise CancelHandler()
                timestamps.append(now)
                self.user_actions[user_id] = timestamps