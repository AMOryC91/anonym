import html
import csv
import functools
import inspect
from io import StringIO
from datetime import datetime
from aiogram import Bot, types
from config import CHANNEL_ID
from database import get_user, is_banned, unban_user

async def check_subscription(user_id: int, bot: Bot) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def format_time_left(vip_until_str):
    if not vip_until_str:
        return "Нет"
    try:
        if isinstance(vip_until_str, str):
            vip_until = datetime.strptime(vip_until_str, '%Y-%m-%d %H:%M:%S')
        else:
            vip_until = vip_until_str
        now = datetime.now()
        if vip_until < now:
            return "Истекла"
        delta = vip_until - now
        if delta.days > 0:
            return f"{delta.days} дн."
        elif delta.seconds // 3600 > 0:
            return f"{delta.seconds // 3600} час."
        else:
            return f"{delta.seconds // 60} мин."
    except:
        return "Ошибка"

def format_user_name(user_info):
    if not user_info:
        return "Неизвестный пользователь"
    username = user_info[1] if len(user_info) > 1 else None
    full_name = user_info[2] if len(user_info) > 2 else None
    if username:
        return f"@{username}"
    elif full_name:
        return full_name
    else:
        return f"Пользователь {user_info[0]}"

def html_escape(text: str) -> str:
    return html.escape(text)

def generate_csv(data, headers):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(data)
    return output.getvalue().encode('utf-8')

# Декоратор для обратной совместимости (используется в старом коде)
def check_ban_decorator(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        message = None
        call = None
        for arg in args:
            if isinstance(arg, types.Message):
                message = arg
                break
            elif isinstance(arg, types.CallbackQuery):
                call = arg
                break
        if message:
            user_id = message.from_user.id
        elif call:
            user_id = call.from_user.id
        else:
            return await func(*args, **kwargs)
        if is_banned(user_id):
            user = get_user(user_id)
            if user and len(user) > 8:
                ban_until = user[4]
                ban_reason = user[8]
                if ban_until:
                    try:
                        if isinstance(ban_until, str):
                            ban_until_dt = datetime.strptime(ban_until, '%Y-%m-%d %H:%M:%S')
                            time_left = ban_until_dt - datetime.now()
                            days = time_left.days
                            if days > 0:
                                ban_text = f"{days} дней"
                            else:
                                hours = time_left.seconds // 3600
                                if hours > 0:
                                    ban_text = f"{hours} часов"
                                else:
                                    ban_text = f"{time_left.seconds // 60} минут"
                        else:
                            ban_text = "навсегда"
                    except:
                        ban_text = "навсегда"
                else:
                    ban_text = "навсегда"
                if message:
                    await message.answer(f"🚫 Вы забанены на {ban_text}\nПричина: {ban_reason}")
                elif call:
                    await call.answer(f"🚫 Вы забанены на {ban_text}\nПричина: {ban_reason}", show_alert=True)
            else:
                if message:
                    await message.answer("🚫 Вы заблокированы администрацией.")
                elif call:
                    await call.answer("🚫 Вы заблокированы администрацией.", show_alert=True)
            return
        
        sig = inspect.signature(func)
        params = sig.parameters
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in params}
        return await func(*args, **filtered_kwargs)
    return wrapper