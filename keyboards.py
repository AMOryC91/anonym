from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHANNEL_ID, VIP_PAYMENT_LINK, BASE_EMOJIS, VIP_EMOJIS

def get_subscription_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}"),
        InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub")
    )
    return keyboard

def get_main_menu_keyboard(is_vip=False, whois_enabled=False, battle_enabled=False):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Профиль", callback_data="profile"),
        InlineKeyboardButton("🏆 Топ", callback_data="top_users"),
        InlineKeyboardButton("🎁 Промокод", callback_data="promo_code"),
        InlineKeyboardButton("⭐ VIP" if not is_vip else "⭐ VIP ✅", callback_data="vip_menu")
    )
    if whois_enabled:
        keyboard.add(InlineKeyboardButton("🎭 Кто я?", callback_data="whois_menu"))
    if battle_enabled:
        keyboard.add(InlineKeyboardButton("⚔ Батл", callback_data="battle_menu"))
    return keyboard

def get_profile_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✏️ Изменить эмодзи", callback_data="change_emoji"),
        InlineKeyboardButton("🏅 Достижения", callback_data="my_achievements"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
    )
    return keyboard

def get_emoji_keyboard(is_vip):
    keyboard = InlineKeyboardMarkup(row_width=5)
    buttons = []
    for emoji in BASE_EMOJIS:
        buttons.append(InlineKeyboardButton(emoji, callback_data=f"emoji_{emoji}"))
    if is_vip:
        for emoji in VIP_EMOJIS:
            buttons.append(InlineKeyboardButton(emoji, callback_data=f"emoji_{emoji}"))
    else:
        for emoji in VIP_EMOJIS:
            buttons.append(InlineKeyboardButton("🔒", callback_data=f"emoji_locked_{emoji}"))
    for i in range(0, len(buttons), 5):
        keyboard.row(*buttons[i:i+5])
    keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_emoji"))
    return keyboard

def get_confession_keyboard(confession_id, is_vip_sender=False):
    keyboard = InlineKeyboardMarkup()
    if is_vip_sender:
        keyboard.row(
            InlineKeyboardButton("👀 Запросить автора", callback_data=f"reveal_{confession_id}"),
            InlineKeyboardButton("🔍 VIP отправитель", callback_data=f"vip_sender_")
        )
    else:
        keyboard.row(
            InlineKeyboardButton("👀 Запросить автора", callback_data=f"reveal_{confession_id}"),
            InlineKeyboardButton("🚩 Пожаловаться", callback_data=f"report_{confession_id}")
        )
    if is_vip_sender:
        keyboard.row(InlineKeyboardButton("🚩 Пожаловаться", callback_data=f"report_{confession_id}"))
    return keyboard

def get_reveal_request_keyboard(confession_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Разрешить", callback_data=f"reveal_allow_{confession_id}"),
        InlineKeyboardButton("❌ Отказать", callback_data=f"reveal_deny_{confession_id}")
    )
    return keyboard

def get_skip_media_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⏭️ Пропустить медиа", callback_data="skip_media"))
    return keyboard

def get_confirmation_keyboard(confession_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Отправить", callback_data=f"send_confession_{confession_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_action")
    )
    return keyboard

def get_vip_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("⭐ Купить VIP", url=VIP_PAYMENT_LINK),
        InlineKeyboardButton("ℹ️ Информация", callback_data="vip_info"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
    )
    return keyboard

def get_back_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return keyboard

def get_cancel_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    return keyboard

def get_admin_main_keyboard(user_role):
    keyboard = InlineKeyboardMarkup(row_width=2)
    if user_role in ["owner", "admin", "moderator", "intern"]:
        keyboard.add(
            InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton("👤 Пользователи", callback_data="admin_users")
        )
    if user_role in ["owner", "admin", "moderator"]:
        keyboard.add(
            InlineKeyboardButton("📨 Признания", callback_data="admin_confessions"),
            InlineKeyboardButton("🛡️ Модерация", callback_data="admin_moderation")
        )
    if user_role in ["owner", "admin"]:
        keyboard.add(
            InlineKeyboardButton("⭐ VIP", callback_data="admin_vip"),
            InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promo")
        )
    if user_role == "owner":
        keyboard.add(
            InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings"),
            InlineKeyboardButton("🔧 Тех.инструменты", callback_data="admin_tools")
        )
    if user_role in ["owner", "admin"]:
        keyboard.add(
            InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
            InlineKeyboardButton("📁 Логи", callback_data="admin_logs")
        )
    # Новые кнопки
    if user_role == "owner":
        keyboard.add(
            InlineKeyboardButton("🛠 Техработы", callback_data="admin_maintenance"),
            InlineKeyboardButton("🏆 Достижения", callback_data="admin_achievements"),
            InlineKeyboardButton("🎭 Кто я?", callback_data="admin_whois"),
            InlineKeyboardButton("⚔ Батл", callback_data="admin_battle"),
            InlineKeyboardButton("📊 Аналитика", callback_data="admin_analytics"),
            InlineKeyboardButton("📜 Лента признаний", callback_data="admin_feed")
        )
    keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu"))
    return keyboard

def get_feed_keyboard(page: int, total_pages: int):
    kb = InlineKeyboardMarkup(row_width=3)
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("◀️", callback_data=f"feed_page_{page-1}"))
    buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="feed_current"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("▶️", callback_data=f"feed_page_{page+1}"))
    kb.row(*buttons)
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return kb

def get_whois_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🎲 Создать игру", callback_data="whois_create"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
    )
    return keyboard

def get_battle_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("⚔ Присоединиться", callback_data="battle_join"),
        InlineKeyboardButton("🚪 Покинуть", callback_data="battle_leave"),
        InlineKeyboardButton("📊 Статистика", callback_data="battle_stats"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
    )
    return keyboard