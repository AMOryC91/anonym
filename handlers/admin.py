from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ContentType, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
from datetime import datetime, timedelta
import logging

from config import OWNER, REPORT_CHAT_ID, BROADCAST_DELAY, CHANNEL_ID
from database import (
    get_user_role, get_all_admins, get_admin_logs, get_active_users_count,
    get_total_confessions_count, get_pending_reports_count, db_fetch, db_exec,
    get_user, get_user_by_username, get_user_stats, is_vip, ban_user, unban_user,
    add_vip_days, remove_vip, get_banned_users, get_vip_users, get_all_users,
    add_admin_log, set_admin_settings, get_admin_settings,
    add_blacklist_word, remove_blacklist_word, get_blacklist_words, check_text_blacklist,
    add_warn, remove_warn, get_warns,
    set_maintenance, is_maintenance,
    create_achievement, delete_achievement, get_all_achievements, award_achievement, remove_achievement,
    create_promo_code, get_promo_codes, delete_promo_code, get_promo_activations,
    create_confession, get_confession, delete_confession,
    update_reveal_status, create_report, delete_report,
    get_top_users,
    # whois
    is_whois_enabled,
    # battle
    is_battle_enabled, clear_battle_participants
)
from utils import format_user_name, html_escape, generate_csv
from keyboards import get_admin_main_keyboard, get_back_keyboard, get_feed_keyboard

logger = logging.getLogger(__name__)

# Состояния для админки
class BanForm(StatesGroup):
    waiting_for_ban_details = State()

class WarnForm(StatesGroup):
    waiting_for_warn_details = State()

class PromoCreateForm(StatesGroup):
    waiting_for_data = State()

class AchievementForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()

class MaintenanceForm(StatesGroup):
    waiting_for_reason = State()
    waiting_for_duration = State()

# ===== ДЕКОРАТОР ПРОВЕРКИ РОЛИ =====
def admin_required(role_required="moderator"):
    def decorator(func):
        async def wrapper(message: types.Message, *args, **kwargs):
            user_role = get_user_role(message.from_user.id)
            if not user_role:
                return
            role_level = {"intern": 1, "moderator": 2, "admin": 3, "owner": 4}
            if role_level.get(user_role, 0) < role_level.get(role_required, 0):
                await message.answer("❌ Недостаточно прав.")
                return
            return await func(message, *args, **kwargs)
        return wrapper
    return decorator

# ===== ОСНОВНЫЕ КМД =====

async def cmd_admin(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if not user_role:
        return
    await message.answer("⚙️ Админ-панель", reply_markup=get_admin_main_keyboard(user_role))

async def admin_stats_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if not user_role:
        await call.answer("Доступ запрещен", show_alert=True)
        return
    total_users = db_fetch_one("SELECT COUNT(*) FROM users")[0]
    active_users = get_active_users_count()
    banned_users = db_fetch_one("SELECT COUNT(*) FROM users WHERE banned = 1")[0]
    vip_users = db_fetch_one("SELECT COUNT(*) FROM users WHERE vip_until > datetime('now')")[0]
    total_confs = get_total_confessions_count()
    today_confs = db_fetch_one("SELECT COUNT(*) FROM confessions WHERE created_at > datetime('now', '-1 day')")[0]
    week_confs = db_fetch_one("SELECT COUNT(*) FROM confessions WHERE created_at > datetime('now', '-7 days')")[0]
    pending_reports = get_pending_reports_count()
    total_reports = db_fetch_one("SELECT COUNT(*) FROM reports")[0]
    text = f"""
📊 Подробная статистика

👥 Пользователи:
• Всего: {total_users}
• Активных: {active_users}
• Забаненных: {banned_users}
• VIP: {vip_users}

📩 Признания:
• Всего отправлено: {total_confs}
• За сутки: {today_confs}
• За неделю: {week_confs}

🚩 Модерация:
• Ожидающих жалоб: {pending_reports}
• Всего жалоб: {total_reports}

🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_users_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if not user_role:
        await call.answer("Доступ запрещен", show_alert=True)
        return
    text = """
👤 Управление пользователями

Команды:
• /ban id дни причина - Забанить
• /unban id - Разбанить
• /banned - Список забаненных
• /find id/@username - Найти пользователя
• /vip_add id дни - Добавить VIP
• /vip_remove id - Удалить VIP
• /warn @username/id причина - Выдать предупреждение
• /unwarn @username/id - Снять предупреждение
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_confessions_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        await call.answer("Доступ запрещен", show_alert=True)
        return
    text = """
📨 Управление признаниями

Команды:
• /confession id - Информация о признании
• /delete_confession id - Удалить признание
• /reports - Список жалоб

Введите ID признания для просмотра:
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_vip_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role not in ["owner", "admin"]:
        await call.answer("Доступ запрещен", show_alert=True)
        return
    text = """
⭐ Управление VIP

Команды:
• /vip_add id дни - Добавить VIP
• /vip_remove id - Удалить VIP
• /vip_list - Список VIP пользователей

Для добавления VIP введите:
/vip_add id количество_дней
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_promo_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role not in ["owner", "admin"]:
        await call.answer("Доступ запрещен", show_alert=True)
        return
    text = """
🎁 Управление промокодами

Команды:
• /addpromo код количество дни [срок_дни] - Создать промокод
• /promo_list - Список промокодов
• /promo_delete код - Удалить промокод
• /promo_activations код - Список активаций

Для создания промокода:
/addpromo VIP2024 10 30 7 (действует 7 дней)
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_settings_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role != "owner":
        await call.answer("Доступ запрещен", show_alert=True)
        return
    settings = get_admin_settings()
    text = "⚙️ Системные настройки\n\n"
    for key, value in settings:
        text += f"{key}: {value}\n"
    text += "\nДля изменения настройки:\n/set ключ значение"
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_tools_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role != "owner":
        await call.answer("Доступ запрещен", show_alert=True)
        return
    text = """
🔧 Технические инструменты

Команды:
• /backup - Создать бэкап БД
• /logs количество - Показать логи
• /cleanup - Очистка старых данных
• /export users|confessions|achievements - Экспорт в CSV
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_logs_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role not in ["owner", "admin"]:
        await call.answer("Доступ запрещен", show_alert=True)
        return
    logs = get_admin_logs(10)
    text = "📁 Последние логи:\n\n"
    for log in logs:
        log_id, admin_id, action, details, created_at = log
        text += f"{created_at}: {action} - {details}\n"
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_moderation_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        await call.answer("Доступ запрещен", show_alert=True)
        return
    text = """
🛡️ Модерация

Команды:
• /blacklist_add слово - Добавить слово в чёрный список
• /blacklist_remove слово - Удалить слово
• /blacklist_list - Список запрещённых слов
• /reports - Список жалоб
• /moderate - Начать модерацию (последняя жалоба)
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_broadcast_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role not in ["owner", "admin"]:
        await call.answer("Доступ запрещен", show_alert=True)
        return
    text = """
📢 Рассылка сообщений

Команды:
• /broadcast_all текст - Всем пользователям
• /broadcast_vip текст - Только VIP
• /broadcast_nonvip текст - Только не VIP
• /broadcast_active текст - Активным (были в боте за последние 7 дней)
• /broadcast_inactive текст - Неактивным
• /broadcast_filter all|vip|banned|active текст
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

# ===== НОВЫЕ РАЗДЕЛЫ =====

async def admin_maintenance_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role != "owner":
        await call.answer("Доступ запрещен", show_alert=True)
        return
    text = """
🛠 Технические работы

Команды:
• /maintenance_on - Включить режим техработ
• /maintenance_off - Выключить
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_achievements_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role != "owner":
        await call.answer("Доступ запрещен", show_alert=True)
        return
    text = """
🏆 Управление достижениями

Команды:
• /create_ach - Создать достижение
• /delete_ach ID - Удалить достижение
• /give_ach @username/id ID - Выдать достижение
• /take_ach @username/id ID - Забрать достижение
• /ach_list - Список всех достижений
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_whois_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role != "owner":
        await call.answer("Доступ запрещен", show_alert=True)
        return
    status = "включён" if is_whois_enabled() else "выключен"
    text = f"""
🎭 Режим "Кто я?"

Статус: {status}

Команды:
• /whois_on - Включить режим
• /whois_off - Выключить
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_battle_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role != "owner":
        await call.answer("Доступ запрещен", show_alert=True)
        return
    status = "включён" if is_battle_enabled() else "выключен"
    text = f"""
⚔ Анонимный батл

Статус: {status}

Команды:
• /battle_on - Запустить батл
• /battle_off - Остановить
• /battle_clear - Очистить список участников
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_analytics_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role not in ["owner", "admin"]:
        await call.answer("Доступ запрещен", show_alert=True)
        return
    new_today = db_fetch_one("SELECT COUNT(*) FROM users WHERE created_at > datetime('now', '-1 day')")[0]
    new_week = db_fetch_one("SELECT COUNT(*) FROM users WHERE created_at > datetime('now', '-7 days')")[0]
    conf_today = db_fetch_one("SELECT COUNT(*) FROM confessions WHERE created_at > datetime('now', '-1 day')")[0]
    conf_week = db_fetch_one("SELECT COUNT(*) FROM confessions WHERE created_at > datetime('now', '-7 days')")[0]
    # Активность по часам
    hours = db_fetch("SELECT strftime('%H', created_at) as h, COUNT(*) FROM confessions GROUP BY h ORDER BY h")
    hours_text = "\n".join([f"{h:02d}:00 – {cnt}" for h, cnt in hours]) if hours else "Нет данных"
    text = f"""
📈 Аналитика

Новых пользователей:
• за день: {new_today}
• за неделю: {new_week}

Признаний:
• за день: {conf_today}
• за неделю: {conf_week}

Активность по часам:
{hours_text}
"""
    await call.message.edit_text(text, reply_markup=get_back_keyboard())

async def admin_feed_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role != "owner":
        await call.answer("Доступ запрещен", show_alert=True)
        return
    await feed_cmd(call.message, 1)

# ===== КОМАНДЫ =====

async def stat_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if not user_role:
        return
    users = get_active_users_count()
    confs = get_total_confessions_count()
    reports = get_pending_reports_count()
    await message.answer(f"📊 Статистика:\n👥 Пользователей: {users}\n📩 Признаний: {confs}\n🚩 Жалоб: {reports}")

async def find_user_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator", "intern"]:
        return
    args = message.get_args().strip()
    if not args:
        await message.answer("Использование: /find id/@username")
        return
    user_id = None
    user = None
    if args.startswith("@"):
        username = args[1:]
        user = get_user_by_username(username)
        if user:
            user_id = user[0]
    else:
        try:
            user_id = int(args)
            user = get_user(user_id)
        except:
            pass
    if not user:
        await message.answer("❌ Пользователь не найден.")
        return
    stats = get_user_stats(user_id)
    user_vip = is_vip(user_id)
    emoji = user[6] if user[6] else "💍"
    ban_status = "Да" if user[3] == 1 else "Нет"
    ban_until = user[4] if user[4] else "Нет"
    vip_until = format_time_left(user[5])
    warns = get_warns(user_id)
    warns_count = len(warns)
    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Имя: {user[2]}\n"
        f"🔗 Username: @{user[1] if user[1] else 'нет'}\n"
        f"👁️‍🗨️ Эмодзи: {emoji}\n"
        f"🚫 Бан: {ban_status}\n"
        f"⏰ Бан до: {ban_until}\n"
        f"⭐ VIP: {'Да' if user_vip else 'Нет'}\n"
        f"📅 VIP до: {vip_until}\n"
        f"⚠️ Предупреждений: {warns_count}/3\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"📩 Получено признаний: {stats['received']}\n"
        f"📤 Отправлено признаний: {stats['sent']}\n"
        f"🚩 Подано жалоб: {stats['reports']}\n"
    )
    user_role_info = get_user_role(user_id)
    if user_role_info:
        text += f"\n👮 <b>Роль: {user_role_info.upper()}</b>"
    await message.answer(text)

async def ban_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    args = message.get_args().strip()
    if not args:
        await message.answer("Использование: /ban user_id дни причина\nПример: /ban 1234567 7 Спам")
        return
    parts = args.split()
    if len(parts) < 3:
        await message.answer("Использование: /ban user_id дни причина\nПример: /ban 1234567 7 Спам")
        return
    try:
        uid = int(parts[0])
        days = int(parts[1])
        reason = " ".join(parts[2:])
        if days < 0:
            await message.answer("❌ Количество дней не может быть отрицательным")
            return
        ban_user(uid, days, reason)
        if days == 0:
            ban_text = "навсегда"
        else:
            ban_text = f"{days} дней"
        await message.answer(f"✅ Пользователь {uid} забанен на {ban_text}\nПричина: {reason}")
        add_admin_log(message.from_user.id, "ban", f"Забанен пользователь {uid} на {days} дней. Причина: {reason}")
        try:
            if days == 0:
                ban_time = "навсегда"
            else:
                ban_time = f"{days} дней"
            await message.bot.send_message(
                uid,
                f"🚫 Вы были забанены администратором.\n"
                f"Время: {ban_time}\n"
                f"Причина: {reason}"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о бане пользователю {uid}: {e}")
    except ValueError:
        await message.answer("❌ ID и количество дней должны быть числами")
    except Exception as e:
        logger.error(f"Ошибка бана: {e}")
        await message.answer(f"❌ Ошибка: {e}")

async def unban_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    args = message.get_args().strip()
    if not args:
        await message.answer("Использование: /unban user_id")
        return
    try:
        uid = int(args)
        unban_user(uid)
        await message.answer(f"✅ Пользователь {uid} разбанен.")
        add_admin_log(message.from_user.id, "unban", f"Разбанен пользователь {uid}")
        try:
            await message.bot.send_message(uid, "✅ Ваш бан был снят администратором.")
        except:
            pass
    except:
        await message.answer("❌ Укажите корректный числовой ID.")

async def banned_list_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    res = get_banned_users()
    if not res:
        await message.answer("✅ Нет забаненных пользователей.")
        return
    text = "🚫 Забаненные пользователи:\n"
    for user in res:
        user_id, username = user
        display_name = f"@{username}" if username else f"User {user_id}"
        text += f"{display_name} ({user_id})\n"
    await message.answer(text)

async def warn_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    args = message.get_args().split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Использование: /warn @username/id причина")
        return
    target, reason = args[0], args[2]
    user = get_user_by_username(target[1:]) if target.startswith('@') else get_user(int(target))
    if not user:
        await message.answer("❌ Пользователь не найден.")
        return
    banned = add_warn(user[0], message.from_user.id, reason)
    if banned:
        await message.answer(f"⚠️ Пользователь {target} получил 3-е предупреждение и забанен навсегда.")
    else:
        warns = get_warns(user[0])
        await message.answer(f"⚠️ Предупреждение выдано. Всего предупреждений: {len(warns)}")
    add_admin_log(message.from_user.id, "warn", f"Выдано предупреждение {user[0]}: {reason}")

async def unwarn_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    args = message.get_args().split()
    if len(args) < 1:
        await message.answer("Использование: /unwarn @username/id")
        return
    target = args[0]
    user = get_user_by_username(target[1:]) if target.startswith('@') else get_user(int(target))
    if not user:
        await message.answer("❌ Пользователь не найден.")
        return
    remove_warn(user[0])
    await message.answer(f"✅ Последнее предупреждение удалено.")
    add_admin_log(message.from_user.id, "unwarn", f"Снято предупреждение {user[0]}")

async def vip_add_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin"]:
        return
    args = message.get_args().strip()
    if not args:
        await message.answer("Использование: /vip_add id дни")
        return
    parts = args.split()
    if len(parts) < 2:
        await message.answer("Использование: /vip_add id дни")
        return
    try:
        user_id = int(parts[0])
        days = int(parts[1])
        if days <= 0:
            await message.answer("❌ Количество дней должно быть положительным числом.")
            return
        user = get_user(user_id)
        if not user:
            await message.answer("❌ Пользователь не найден.")
            return
        add_vip_days(user_id, days)
        await message.answer(f"✅ Пользователю {user_id} добавлено {days} дней VIP.")
        add_admin_log(message.from_user.id, "vip_add", f"Добавлено {days} дней VIP пользователю {user_id}")
        try:
            await message.bot.send_message(user_id, f"⭐ Вам добавлено {days} дней VIP подписки администратором!")
        except:
            pass
    except ValueError:
        await message.answer("❌ ID и дни должны быть числами.")

async def vip_remove_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin"]:
        return
    args = message.get_args().strip()
    if not args:
        await message.answer("Использование: /vip_remove id")
        return
    try:
        user_id = int(args)
        user = get_user(user_id)
        if not user:
            await message.answer("❌ Пользователь не найден.")
            return
        if not is_vip(user_id):
            await message.answer("❌ У пользователя нет VIP.")
            return
        remove_vip(user_id)
        await message.answer(f"✅ VIP удален у пользователя {user_id}.")
        add_admin_log(message.from_user.id, "vip_remove", f"Удален VIP у пользователя {user_id}")
        try:
            await message.bot.send_message(user_id, "⚠️ Ваша VIP подписка была удалена администратором.")
        except:
            pass
    except ValueError:
        await message.answer("❌ ID должен быть числом.")

async def vip_list_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin"]:
        return
    vip_users = get_vip_users()
    if not vip_users:
        await message.answer("⭐ Нет VIP пользователей.")
        return
    text = "⭐ <b>Список VIP пользователей:</b>\n\n"
    for i, user in enumerate(vip_users, 1):
        user_id, username, vip_until = user
        display_name = f"@{username}" if username else f"User {user_id}"
        time_left = format_time_left(vip_until)
        text += f"{i}. {display_name} (ID: {user_id}) - до: {time_left}\n"
    await message.answer(text)

async def blacklist_add_cmd(message: types.Message):
    word = message.get_args().strip().lower()
    if not word:
        await message.answer("Укажите слово.")
        return
    if add_blacklist_word(word):
        await message.answer(f"✅ Слово '{word}' добавлено в чёрный список.")
    else:
        await message.answer("❌ Такое слово уже есть.")

async def blacklist_remove_cmd(message: types.Message):
    word = message.get_args().strip().lower()
    remove_blacklist_word(word)
    await message.answer(f"✅ Слово '{word}' удалено из чёрного списка.")

async def blacklist_list_cmd(message: types.Message):
    words = get_blacklist_words()
    if not words:
        await message.answer("📭 Чёрный список пуст.")
    else:
        text = "🚫 Чёрный список:\n" + "\n".join(f"• {w}" for w in words)
        await message.answer(text)

async def confession_info_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    args = message.get_args().strip()
    if not args:
        await message.answer("Использование: /confession id")
        return
    try:
        confession_id = int(args)
        confession = get_confession(confession_id)
        if not confession:
            await message.answer("❌ Признание не найдено.")
            return
        from_user = confession[1]
        to_user = confession[2]
        text = confession[4]
        media_type = confession[5]
        media_file_id = confession[6]
        reveal_status = confession[7]
        is_vip_sender = confession[8]
        created_at = confession[9]
        from_user_info = get_user(from_user)
        to_user_info = get_user(to_user)
        from_name = format_user_name(from_user_info)
        to_name = format_user_name(to_user_info)
        reveal_text = ""
        if reveal_status == 0:
            reveal_text = "Не запрашивался"
        elif reveal_status == 1:
            reveal_text = "Запрос отправлен"
        elif reveal_status == 2:
            reveal_text = "Разрешен"
        elif reveal_status == 3:
            reveal_text = "Отказано"
        text_display = f"<code>{html_escape(text)}</code>" if text else "Нет текста"
        info_text = (
            f"📄 <b>Информация о признании #{confession_id}</b>\n\n"
            f"👤 <b>От:</b> {from_name} (ID: {from_user})\n"
            f"👤 <b>Кому:</b> {to_name} (ID: {to_user})\n"
            f"⭐ <b>VIP отправитель:</b> {'Да' if is_vip_sender else 'Нет'}\n"
            f"🔍 <b>Статус раскрытия:</b> {reveal_text}\n"
            f"📅 <b>Создано:</b> {created_at}\n\n"
            f"📝 <b>Текст:</b>\n{text_display}\n\n"
        )
        if media_type:
            info_text += f"📎 <b>Медиа:</b> {media_type}\n"
            if media_file_id:
                info_text += f"🆔 <b>ID медиа:</b> {media_file_id[:20]}...\n"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🗑️ Удалить признание", callback_data=f"admin_delete_conf_{confession_id}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_confessions"))
        await message.answer(info_text, reply_markup=kb)
    except ValueError:
        await message.answer("❌ ID должен быть числом.")

async def delete_confession_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    args = message.get_args().strip()
    if not args:
        await message.answer("Использование: /delete_confession id")
        return
    try:
        confession_id = int(args)
        confession = get_confession(confession_id)
        if not confession:
            await message.answer("❌ Признание не найдено.")
            return
        delete_confession(confession_id)
        await message.answer(f"✅ Признание #{confession_id} удалено.")
        add_admin_log(message.from_user.id, "delete_confession", f"Удалено признание #{confession_id}")
    except ValueError:
        await message.answer("❌ ID должен быть числом.")

async def reports_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    reps = db_fetch("SELECT id, confession_id, reporter_id, created_at FROM reports ORDER BY created_at DESC LIMIT 50")
    if not reps:
        await message.answer("🚩 Жалоб нет.")
        return
    text = "🚩 Жалобы:\n\n"
    for r in reps:
        text += f"#{r[0]} | Confession: {r[1]} | Reporter: {r[2]} | At: {r[3]}\n"
    await message.answer(text)

async def add_promo_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin"]:
        return
    args = message.get_args().split()
    if len(args) < 3:
        await message.answer("Использование: /addpromo КОД КОЛ-ВО ДНИ [СРОК_ДНИ]\nПример: /addpromo VIP2024 10 30 7")
        return
    code = args[0].upper()
    try:
        activations = int(args[1])
        vip_days = int(args[2])
        expires_days = int(args[3]) if len(args) > 3 else None
    except:
        await message.answer("❌ Числовые значения должны быть числами.")
        return
    expires_at = (datetime.now() + timedelta(days=expires_days)).strftime("%Y-%m-%d %H:%M:%S") if expires_days else None
    create_promo_code(code, activations, vip_days, message.from_user.id, expires_at)
    await message.answer(f"✅ Промокод {code} создан.")
    add_admin_log(message.from_user.id, "add_promo", f"{code}")

async def promo_list_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin"]:
        return
    promos = get_promo_codes()
    if not promos:
        await message.answer("🎁 Нет созданных промокодов.")
        return
    text = "🎁 <b>Список промокодов:</b>\n\n"
    for promo in promos:
        code, activations, activations_left, vip_days, created_by, created_at, expires_at = promo
        creator = get_user(created_by)
        creator_name = format_user_name(creator) if creator else f"User {created_by}"
        text += f"<b>Код:</b> {code}\n"
        text += f"<b>Активаций:</b> {activations_left}/{activations}\n"
        text += f"<b>VIP дней:</b> {vip_days}\n"
        text += f"<b>Создал:</b> {creator_name}\n"
        text += f"<b>Создан:</b> {created_at}\n"
        if expires_at:
            text += f"<b>Истекает:</b> {expires_at}\n"
        text += "─" * 20 + "\n"
    await message.answer(text)

async def promo_delete_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin"]:
        return
    code = message.get_args().strip().upper()
    if not code:
        await message.answer("Укажите код.")
        return
    delete_promo_code(code)
    await message.answer(f"✅ Промокод {code} удален.")
    add_admin_log(message.from_user.id, "promo_delete", f"Удален промокод {code}")

async def promo_activations_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin"]:
        return
    code = message.get_args().strip().upper()
    if not code:
        await message.answer("Укажите код.")
        return
    activations = get_promo_activations(code)
    if not activations:
        await message.answer("Нет активаций.")
        return
    text = f"📊 Активации промокода {code}:\n"
    for user_id, activated_at in activations:
        user = get_user(user_id)
        name = format_user_name(user)
        text += f"• {name} – {activated_at}\n"
    await message.answer(text)

async def set_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role != "owner":
        return
    args = message.get_args().strip()
    if not args:
        await message.answer("Использование: /set ключ значение")
        return
    parts = args.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /set ключ значение")
        return
    key, value = parts[0], parts[1]
    set_admin_settings(key, value)
    await message.answer(f"✅ Настройка {key} изменена на: {value}")
    add_admin_log(message.from_user.id, "set", f"Изменена настройка {key} на {value}")

async def backup_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role != "owner":
        return
    import shutil, os
    from config import BACKUP_PATH, DB_PATH
    try:
        os.makedirs(BACKUP_PATH, exist_ok=True)
        backup_name = f"confessions_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db"
        backup_file = os.path.join(BACKUP_PATH, backup_name)
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, backup_file)
            await message.answer(f"✅ Бэкап создан: {backup_name}")
            add_admin_log(message.from_user.id, "backup", f"Создан бэкап {backup_name}")
        else:
            await message.answer("❌ Файл базы данных не найден.")
    except Exception as e:
        logger.error(f"Ошибка создания бэкапа: {e}")
        await message.answer(f"❌ Ошибка создания бэкапа: {e}")

async def logs_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role != "owner":
        return
    args = message.get_args().strip()
    try:
        lines = int(args) if args else 20
        lines = min(lines, 100)
    except:
        lines = 20
    from config import LOG_PATH
    try:
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, 'r', encoding='utf-8') as f:
                log_lines = f.readlines()[-lines:]
            if log_lines:
                log_text = "".join(log_lines[-50:])
                if len(log_text) > 4000:
                    log_text = log_text[-4000:]
                await message.answer(f"<pre>{html_escape(log_text)}</pre>")
            else:
                await message.answer("📁 Логи пусты.")
        else:
            await message.answer("❌ Файл логов не найден.")
    except Exception as e:
        logger.error(f"Ошибка чтения логов: {e}")
        await message.answer(f"❌ Ошибка чтения логов: {e}")

async def cleanup_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role != "owner":
        return
    try:
        old_reports = db_exec("DELETE FROM reports WHERE created_at < datetime('now', '-30 days')")
        old_confs = db_exec("DELETE FROM confessions WHERE created_at < datetime('now', '-90 days')")
        await message.answer(f"✅ Очистка выполнена.\nУдалено признаний: {old_confs}\nУдалено жалоб: {old_reports}")
        add_admin_log(message.from_user.id, "cleanup", f"Очистка: {old_confs} признаний, {old_reports} жалоб")
    except Exception as e:
        logger.error(f"Ошибка очистки: {e}")
        await message.answer(f"❌ Ошибка очистки: {e}")

async def moderate_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    reports = db_fetch("SELECT id, confession_id, reporter_id, created_at FROM reports ORDER BY created_at DESC LIMIT 1")
    if not reports:
        await message.answer("🚩 Нет жалоб для модерации.")
        return
    report = reports[0]
    report_id, confession_id, reporter_id, created_at = report
    confession = get_confession(confession_id)
    if not confession:
        await message.answer("❌ Признание не найдено.")
        return
    from_user, to_user, text = confession[1], confession[2], confession[4]
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🚫 Забанить автора", callback_data=f"banuser_{from_user}_{report_id}"),
        InlineKeyboardButton("✅ Игнорировать", callback_data=f"ignore_{report_id}")
    )
    text_display = f"<code>{html_escape(text[:500])}</code>" if len(text) > 500 else f"<code>{html_escape(text)}</code>"
    await message.answer(
        f"🚩 <b>Жалоба #{report_id}</b>\n\n"
        f"🔸 ID признания: <code>{confession_id}</code>\n"
        f"🔸 Текст: {text_display}\n\n"
        f"🔸 ID автора: <code>{from_user}</code>\n"
        f"🔸 ID получателя: <code>{to_user}</code>\n"
        f"🔸 ID жалующегося: <code>{reporter_id}</code>\n"
        f"🔸 Время: {created_at}",
        reply_markup=kb
    )

async def broadcast_cmd_generic(message: types.Message, filter_type: str):
    text = message.get_args().strip()
    if not text:
        await message.answer(f"Использование: /broadcast_{filter_type} текст")
        return
    users = []
    if filter_type == "all":
        users = get_all_users()
    elif filter_type == "vip":
        vip_data = get_vip_users()
        users = [(uid,) for uid, _, _ in vip_data]
    elif filter_type == "nonvip":
        all_users = get_all_users()
        vip_ids = {uid for uid, _, _ in get_vip_users()}
        users = [(uid,) for uid, in all_users if uid not in vip_ids]
    elif filter_type == "active":
        # активные за последние 7 дней
        users = db_fetch("SELECT id FROM users WHERE last_active > datetime('now', '-7 days') AND banned=0")
    elif filter_type == "inactive":
        users = db_fetch("SELECT id FROM users WHERE last_active <= datetime('now', '-7 days') AND banned=0")
    elif filter_type == "filter":
        args = text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("Использование: /broadcast_filter all|vip|banned|active текст")
            return
        ftype, text = args[0].lower(), args[1]
        if ftype == "all":
            users = get_all_users()
        elif ftype == "vip":
            vip_data = get_vip_users()
            users = [(uid,) for uid, _, _ in vip_data]
        elif ftype == "banned":
            users = get_banned_users()
        elif ftype == "active":
            users = db_fetch("SELECT id FROM users WHERE last_active > datetime('now', '-7 days') AND banned=0")
        else:
            await message.answer("Неверный фильтр.")
            return
    else:
        await message.answer("Неизвестный тип рассылки.")
        return
    if not users:
        await message.answer(f"❌ Нет пользователей для рассылки.")
        return
    success = 0
    fail = 0
    for (uid,) in users:
        try:
            await message.bot.send_message(uid, f"{text}")
            success += 1
            await asyncio.sleep(BROADCAST_DELAY)
        except Exception:
            fail += 1
    await message.answer(f"✅ Рассылка завершена.\nДоставлено: {success}\nОшибок: {fail}")
    add_admin_log(message.from_user.id, "broadcast", f"{filter_type}: {text[:50]}...")

async def broadcast_all_cmd(message: types.Message):
    await broadcast_cmd_generic(message, "all")

async def broadcast_vip_cmd(message: types.Message):
    await broadcast_cmd_generic(message, "vip")

async def broadcast_nonvip_cmd(message: types.Message):
    await broadcast_cmd_generic(message, "nonvip")

async def broadcast_active_cmd(message: types.Message):
    await broadcast_cmd_generic(message, "active")

async def broadcast_inactive_cmd(message: types.Message):
    await broadcast_cmd_generic(message, "inactive")

async def broadcast_filter_cmd(message: types.Message):
    await broadcast_cmd_generic(message, "filter")

async def add_role_cmd(message: types.Message):
    if message.from_user.id not in OWNER:
        return
    args = message.get_args().strip()
    if not args:
        await message.answer("Использование: /add роль id/@username")
        return
    parts = args.split()
    if len(parts) < 2:
        await message.answer("Использование: /add роль id/@username")
        return
    role = parts[0].lower()
    if role not in ["intern", "moderator", "admin"]:
        await message.answer("❌ Доступные роли: intern, moderator, admin")
        return
    target = parts[1]
    user_id = None
    if target.startswith("@"):
        user = get_user_by_username(target[1:])
        if user:
            user_id = user[0]
    else:
        try:
            user_id = int(target)
        except:
            pass
    if not user_id:
        await message.answer("❌ Пользователь не найден")
        return
    add_admin_role(user_id, role, message.from_user.id)
    await message.answer(f"✅ Роль {role} назначена пользователю {user_id}")
    try:
        await message.bot.send_message(user_id, f"👮 Вам назначена роль {role.upper()}")
    except:
        pass

async def del_role_cmd(message: types.Message):
    if message.from_user.id not in OWNER:
        return
    args = message.get_args().strip()
    if not args:
        await message.answer("Использование: /del роль id/@username")
        return
    parts = args.split()
    if len(parts) < 2:
        await message.answer("Использование: /del роль id/@username")
        return
    role = parts[0].lower()
    if role not in ["intern", "moderator", "admin"]:
        await message.answer("❌ Доступные роли: intern, moderator, admin")
        return
    target = parts[1]
    user_id = None
    if target.startswith("@"):
        user = get_user_by_username(target[1:])
        if user:
            user_id = user[0]
    else:
        try:
            user_id = int(target)
        except:
            pass
    if not user_id:
        await message.answer("❌ Пользователь не найден")
        return
    remove_admin_role(user_id, role, message.from_user.id)
    await message.answer(f"✅ Роль {role} удалена у пользователя {user_id}")
    try:
        await message.bot.send_message(user_id, f"👮 У вас удалена роль {role.upper()}")
    except:
        pass

async def handle_banuser_callback(call: types.CallbackQuery):
    parts = call.data.split("_")
    if len(parts) >= 3:
        user_id = int(parts[1])
        report_id = int(parts[2])
        await BanForm.waiting_for_ban_details.set()
        await call.message.bot.current_state(user=call.from_user.id, chat=call.message.chat.id).update_data(
            ban_user_id=user_id,
            ban_report_id=report_id
        )
        await call.message.edit_text(
            call.message.text + f"\n\n🚫 Выбран пользователь {user_id} для бана.\n\n"
            "Введите время бана и причину через пробел:\n"
            "Формат: дни причина\nПримеры:\n7 Оскорбления\n30 Спам\n0 Нарушение правил (бан навсегда)\n\n"
            "Причина может состоять из нескольких слов."
        )
        await call.answer("Введите время и причину бана")
    else:
        await call.answer("Ошибка", show_alert=True)

async def handle_ignore_callback(call: types.CallbackQuery):
    report_id = int(call.data.split("_")[1])
    delete_report(report_id)
    await call.message.edit_text(call.message.text + "\n\n✅ Жалоба проигнорирована (удалена).")
    await call.answer("Жалоба проигнорирована.", show_alert=True)

async def process_ban_details(message: types.Message, state: FSMContext):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        await state.finish()
        return
    data = await state.get_data()
    user_id = data.get('ban_user_id')
    report_id = data.get('ban_report_id')
    if not user_id:
        await message.answer("❌ Ошибка: данные не найдены.")
        await state.finish()
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Неверный формат. Используйте: дни причина\nПример: 7 Оскорбления")
        return
    try:
        days = int(parts[0])
        reason = " ".join(parts[1:])
        if days < 0:
            await message.answer("❌ Количество дней не может быть отрицательным")
            return
        ban_user(user_id, days, reason)
        if report_id:
            delete_report(report_id)
        if days == 0:
            ban_text = "навсегда"
        else:
            ban_text = f"{days} дней"
        await message.answer(f"✅ Пользователь {user_id} забанен на {ban_text}\nПричина: {reason}")
        add_admin_log(message.from_user.id, "ban", f"Забанен пользователь {user_id} на {days} дней. Причина: {reason}")
        try:
            if days == 0:
                ban_time = "навсегда"
            else:
                ban_time = f"{days} дней"
            await message.bot.send_message(
                user_id,
                f"🚫 Вы были забанены администратором.\n"
                f"Время: {ban_time}\n"
                f"Причина: {reason}"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о бане пользователю {user_id}: {e}")
        try:
            await message.bot.edit_message_text(
                chat_id=REPORT_CHAT_ID,
                message_id=message.message_id - 1,
                text=f"{html_escape(message.text)}\n\n🚫 Пользователь {user_id} забанен админом {message.from_user.id} на {ban_text}.\nПричина: {html_escape(reason)}"
            )
        except:
            pass
    except ValueError:
        await message.answer("❌ Количество дней должно быть числом")
    except Exception as e:
        logger.error(f"Ошибка при бане: {e}")
        await message.answer(f"❌ Ошибка: {e}")
    await state.finish()

async def admin_delete_conf_callback(call: types.CallbackQuery):
    user_role = get_user_role(call.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        await call.answer("Доступ запрещен", show_alert=True)
        return
    confession_id = int(call.data.split("_")[3])
    confession = get_confession(confession_id)
    if not confession:
        await call.answer("❌ Признание не найдено", show_alert=True)
        return
    delete_confession(confession_id)
    await call.message.edit_text(f"✅ Признание #{confession_id} удалено.")
    add_admin_log(call.from_user.id, "delete_confession", f"Удалено признание #{confession_id}")
    await call.answer("Признание удалено", show_alert=True)

# ===== ДОСТИЖЕНИЯ =====

async def create_achievement_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role != "owner":
        return
    await AchievementForm.waiting_for_name.set()
    await message.answer("Введите название достижения:")

async def achievement_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await AchievementForm.waiting_for_description.set()
    await message.answer("Введите описание:")

async def achievement_description_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data['name']
    desc = message.text
    create_achievement(name, desc)
    await message.answer(f"✅ Достижение '{name}' создано.")
    await state.finish()

async def delete_achievement_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role != "owner":
        return
    try:
        ach_id = int(message.get_args())
    except:
        await message.answer("Укажите ID достижения.")
        return
    delete_achievement(ach_id)
    await message.answer("✅ Достижение удалено.")

async def give_achievement_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    args = message.get_args().split()
    if len(args) < 2:
        await message.answer("Использование: /give_ach @username/id ID_достижения")
        return
    target = args[0]
    ach_id = int(args[1])
    user = get_user_by_username(target[1:]) if target.startswith('@') else get_user(int(target))
    if not user:
        await message.answer("❌ Пользователь не найден.")
        return
    if award_achievement(user[0], ach_id):
        await message.answer("✅ Достижение выдано.")
        try:
            await message.bot.send_message(user[0], f"🏅 Вы получили достижение!")
        except:
            pass
    else:
        await message.answer("❌ У пользователя уже есть это достижение.")

async def take_achievement_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    args = message.get_args().split()
    if len(args) < 2:
        await message.answer("Использование: /take_ach @username/id ID_достижения")
        return
    target = args[0]
    ach_id = int(args[1])
    user = get_user_by_username(target[1:]) if target.startswith('@') else get_user(int(target))
    if not user:
        await message.answer("❌ Пользователь не найден.")
        return
    remove_achievement(user[0], ach_id)
    await message.answer("✅ Достижение удалено у пользователя.")

async def ach_list_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role not in ["owner", "admin", "moderator"]:
        return
    achievements = get_all_achievements()
    if not achievements:
        await message.answer("🏅 Нет созданных достижений.")
        return
    text = "🏅 <b>Все достижения:</b>\n\n"
    for a in achievements:
        text += f"ID {a[0]}: {a[1]} – {a[2]}\n"
    await message.answer(text)

# ===== ТЕХРАБОТЫ =====

async def maintenance_on_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role != "owner":
        return
    await MaintenanceForm.waiting_for_reason.set()
    await message.answer("Введите причину техработ:")

async def maintenance_reason_handler(message: types.Message, state: FSMContext):
    await state.update_data(reason=message.text)
    await MaintenanceForm.waiting_for_duration.set()
    await message.answer("Введите длительность (например: 2ч, 30мин, 1д):")

async def maintenance_duration_handler(message: types.Message, state: FSMContext):
    duration_str = message.text
    try:
        if duration_str.endswith('ч'):
            hours = int(duration_str[:-1])
            delta = timedelta(hours=hours)
        elif duration_str.endswith('мин'):
            minutes = int(duration_str[:-3])
            delta = timedelta(minutes=minutes)
        elif duration_str.endswith('д'):
            days = int(duration_str[:-1])
            delta = timedelta(days=days)
        else:
            await message.answer("Неверный формат. Используйте например: 2ч, 30мин, 1д")
            return
    except:
        await message.answer("Ошибка парсинга.")
        return
    data = await state.get_data()
    reason = data['reason']
    until = (datetime.now() + delta).strftime("%Y-%m-%d %H:%M:%S")
    set_maintenance(True, reason, until)
    # Уведомляем всех пользователей
    users = get_all_users()
    sent = 0
    for (uid,) in users:
        try:
            await message.bot.send_message(uid, f"🛠 Ведутся техработы до {until}\nПричина: {reason}")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await message.answer(f"✅ Режим техработ включён. Уведомлено {sent} пользователей.")
    add_admin_log(message.from_user.id, "maintenance_on", f"Причина: {reason}, до {until}")
    await state.finish()

async def maintenance_off_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role != "owner":
        return
    set_maintenance(False)
    users = get_all_users()
    sent = 0
    for (uid,) in users:
        try:
            await message.bot.send_message(uid, "✅ Техработы завершены. Бот снова доступен.")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await message.answer(f"✅ Режим техработ выключен. Уведомлено {sent} пользователей.")
    add_admin_log(message.from_user.id, "maintenance_off", "")

# ===== ЛЕНТА ПРИЗНАНИЙ =====

async def feed_cmd(message: types.Message, page=1):
    per_page = 5
    offset = (page - 1) * per_page
    confessions = db_fetch("SELECT id, from_user, to_user, text, created_at FROM confessions ORDER BY id DESC LIMIT ? OFFSET ?", (per_page, offset))
    total = db_fetch_one("SELECT COUNT(*) FROM confessions")[0]
    total_pages = (total + per_page - 1) // per_page
    if not confessions:
        await message.answer("Признаний нет.")
        return
    text = f"📜 Лента признаний (стр. {page}/{total_pages})\n\n"
    for c in confessions:
        from_user = get_user(c[1])
        to_user = get_user(c[2])
        from_name = format_user_name(from_user)
        to_name = format_user_name(to_user)
        short_text = (c[3][:50] + '...') if c[3] and len(c[3]) > 50 else c[3]
        text += f"#{c[0]} {from_name} → {to_name}\n{short_text}\n\n"
    await message.answer(text, reply_markup=get_feed_keyboard(page, total_pages))

async def feed_page_callback(call: types.CallbackQuery):
    page = int(call.data.split('_')[2])
    await feed_cmd(call.message, page)

# ===== ЭКСПОРТ =====

async def export_cmd(message: types.Message):
    user_role = get_user_role(message.from_user.id)
    if user_role != "owner":
        return
    table = message.get_args().strip().lower()
    if table not in ['users', 'confessions', 'achievements']:
        await message.answer("Доступные таблицы: users, confessions, achievements")
        return
    if table == 'users':
        data = db_fetch("SELECT id, username, full_name, banned, vip_until, created_at FROM users")
        headers = ['id', 'username', 'full_name', 'banned', 'vip_until', 'created_at']
    elif table == 'confessions':
        data = db_fetch("SELECT id, from_user, to_user, text, created_at FROM confessions")
        headers = ['id', 'from_user', 'to_user', 'text', 'created_at']
    else:
        data = db_fetch("SELECT id, name, description, created_at FROM achievements")
        headers = ['id', 'name', 'description', 'created_at']
    csv_data = generate_csv(data, headers)
    await message.answer_document(types.InputFile.from_bytes(csv_data, filename=f"{table}.csv"))

# ===== УПРАВЛЕНИЕ ИВЕНТАМИ =====

async def whois_on_cmd(message: types.Message):
    if message.from_user.id not in OWNER:
        return
    set_admin_settings("whois_enabled", "1")
    await message.answer("✅ Режим 'Кто я?' включён.")

async def whois_off_cmd(message: types.Message):
    if message.from_user.id not in OWNER:
        return
    set_admin_settings("whois_enabled", "0")
    await message.answer("✅ Режим 'Кто я?' выключён.")

async def battle_on_cmd(message: types.Message):
    if message.from_user.id not in OWNER:
        return
    set_admin_settings("battle_enabled", "1")
    await message.answer("✅ Анонимный батл запущен.")

async def battle_off_cmd(message: types.Message):
    if message.from_user.id not in OWNER:
        return
    set_admin_settings("battle_enabled", "0")
    await message.answer("✅ Анонимный батл остановлен.")

async def battle_clear_cmd(message: types.Message):
    if message.from_user.id not in OWNER:
        return
    clear_battle_participants()
    await message.answer("✅ Список участников батла очищен.")

# ===== РЕГИСТРАЦИЯ =====

def register_admin_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_admin, commands=['admin', 'admin_panel'])
    dp.register_message_handler(stat_cmd, commands=['stat'])
    dp.register_message_handler(find_user_cmd, commands=['find'])
    dp.register_message_handler(ban_cmd, commands=['ban'])
    dp.register_message_handler(unban_cmd, commands=['unban'])
    dp.register_message_handler(banned_list_cmd, commands=['banned'])
    dp.register_message_handler(warn_cmd, commands=['warn'])
    dp.register_message_handler(unwarn_cmd, commands=['unwarn'])
    dp.register_message_handler(vip_add_cmd, commands=['vip_add'])
    dp.register_message_handler(vip_remove_cmd, commands=['vip_remove'])
    dp.register_message_handler(vip_list_cmd, commands=['vip_list'])
    dp.register_message_handler(blacklist_add_cmd, commands=['blacklist_add'])
    dp.register_message_handler(blacklist_remove_cmd, commands=['blacklist_remove'])
    dp.register_message_handler(blacklist_list_cmd, commands=['blacklist_list'])
    dp.register_message_handler(confession_info_cmd, commands=['confession'])
    dp.register_message_handler(delete_confession_cmd, commands=['delete_confession'])
    dp.register_message_handler(reports_cmd, commands=['reports'])
    dp.register_message_handler(add_promo_cmd, commands=['addpromo'])
    dp.register_message_handler(promo_list_cmd, commands=['promo_list'])
    dp.register_message_handler(promo_delete_cmd, commands=['promo_delete'])
    dp.register_message_handler(promo_activations_cmd, commands=['promo_activations'])
    dp.register_message_handler(set_cmd, commands=['set'])
    dp.register_message_handler(backup_cmd, commands=['backup'])
    dp.register_message_handler(logs_cmd, commands=['logs'])
    dp.register_message_handler(cleanup_cmd, commands=['cleanup'])
    dp.register_message_handler(moderate_cmd, commands=['moderate'])
    dp.register_message_handler(broadcast_all_cmd, commands=['broadcast_all'])
    dp.register_message_handler(broadcast_vip_cmd, commands=['broadcast_vip'])
    dp.register_message_handler(broadcast_nonvip_cmd, commands=['broadcast_nonvip'])
    dp.register_message_handler(broadcast_active_cmd, commands=['broadcast_active'])
    dp.register_message_handler(broadcast_inactive_cmd, commands=['broadcast_inactive'])
    dp.register_message_handler(broadcast_filter_cmd, commands=['broadcast_filter'])
    dp.register_message_handler(add_role_cmd, commands=['add'])
    dp.register_message_handler(del_role_cmd, commands=['del'])
    dp.register_message_handler(create_achievement_cmd, commands=['create_ach'])
    dp.register_message_handler(delete_achievement_cmd, commands=['delete_ach'])
    dp.register_message_handler(give_achievement_cmd, commands=['give_ach'])
    dp.register_message_handler(take_achievement_cmd, commands=['take_ach'])
    dp.register_message_handler(ach_list_cmd, commands=['ach_list'])
    dp.register_message_handler(maintenance_on_cmd, commands=['maintenance_on'])
    dp.register_message_handler(maintenance_off_cmd, commands=['maintenance_off'])
    dp.register_message_handler(export_cmd, commands=['export'])
    dp.register_message_handler(feed_cmd, commands=['feed'])
    dp.register_message_handler(whois_on_cmd, commands=['whois_on'])
    dp.register_message_handler(whois_off_cmd, commands=['whois_off'])
    dp.register_message_handler(battle_on_cmd, commands=['battle_on'])
    dp.register_message_handler(battle_off_cmd, commands=['battle_off'])
    dp.register_message_handler(battle_clear_cmd, commands=['battle_clear'])
    
    # Обработчики состояний
    dp.register_message_handler(process_ban_details, state=BanForm.waiting_for_ban_details, content_types=ContentType.TEXT)
    dp.register_message_handler(maintenance_reason_handler, state=MaintenanceForm.waiting_for_reason, content_types=ContentType.TEXT)
    dp.register_message_handler(maintenance_duration_handler, state=MaintenanceForm.waiting_for_duration, content_types=ContentType.TEXT)
    dp.register_message_handler(achievement_name_handler, state=AchievementForm.waiting_for_name, content_types=ContentType.TEXT)
    dp.register_message_handler(achievement_description_handler, state=AchievementForm.waiting_for_description, content_types=ContentType.TEXT)
    
    # Callback'и
    dp.register_callback_query_handler(admin_stats_callback, lambda c: c.data == 'admin_stats')
    dp.register_callback_query_handler(admin_users_callback, lambda c: c.data == 'admin_users')
    dp.register_callback_query_handler(admin_confessions_callback, lambda c: c.data == 'admin_confessions')
    dp.register_callback_query_handler(admin_vip_callback, lambda c: c.data == 'admin_vip')
    dp.register_callback_query_handler(admin_promo_callback, lambda c: c.data == 'admin_promo')
    dp.register_callback_query_handler(admin_settings_callback, lambda c: c.data == 'admin_settings')
    dp.register_callback_query_handler(admin_tools_callback, lambda c: c.data == 'admin_tools')
    dp.register_callback_query_handler(admin_logs_callback, lambda c: c.data == 'admin_logs')
    dp.register_callback_query_handler(admin_moderation_callback, lambda c: c.data == 'admin_moderation')
    dp.register_callback_query_handler(admin_broadcast_callback, lambda c: c.data == 'admin_broadcast')
    dp.register_callback_query_handler(admin_maintenance_callback, lambda c: c.data == 'admin_maintenance')
    dp.register_callback_query_handler(admin_achievements_callback, lambda c: c.data == 'admin_achievements')
    dp.register_callback_query_handler(admin_whois_callback, lambda c: c.data == 'admin_whois')
    dp.register_callback_query_handler(admin_battle_callback, lambda c: c.data == 'admin_battle')
    dp.register_callback_query_handler(admin_analytics_callback, lambda c: c.data == 'admin_analytics')
    dp.register_callback_query_handler(admin_feed_callback, lambda c: c.data == 'admin_feed')
    
    dp.register_callback_query_handler(handle_banuser_callback, lambda c: c.data.startswith('banuser_'))
    dp.register_callback_query_handler(handle_ignore_callback, lambda c: c.data.startswith('ignore_'))
    dp.register_callback_query_handler(admin_delete_conf_callback, lambda c: c.data.startswith('admin_delete_conf_'))
    dp.register_callback_query_handler(feed_page_callback, lambda c: c.data.startswith('feed_page_'))