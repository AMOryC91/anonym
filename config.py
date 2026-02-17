import os

# Токен бота
API_TOKEN = "8439192645:AAFnDuw0XhfWxqkAODE-9_oq0aB8_79PMFU"

# Владельцы (список ID)
OWNER = [1890263091]

# Канал для подписки
CHANNEL_ID = "@Anonymconfessions"

# ID чата для жалоб
REPORT_CHAT_ID = -1003371392566

# Ссылка на покупку VIP
VIP_PAYMENT_LINK = "https://t.me/XAP4KTEP_bot"
VIP_CONTACT_USERNAME = "XAP4KTEP_bot"

# Эмодзи
BASE_EMOJIS = ["💍", "🪬", "⚔️"]
VIP_EMOJIS = ["👑", "⭐", "😎", "💰", "🚀"]
ALL_EMOJIS = BASE_EMOJIS + VIP_EMOJIS

# Пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "logs", "bot.log")
DB_PATH = os.path.join(BASE_DIR, "confessions.db")
BACKUP_PATH = os.path.join(BASE_DIR, "backups")

# Лимиты
MAX_PHOTO_PER_CONFESSION = 1
MAX_VIDEO_PER_CONFESSION = 1
MAX_VOICE_PER_CONFESSION = 1
MAX_STICKER_PER_CONFESSION = 1
EDIT_TIMEOUT_MINUTES = 5
VIP_EDIT_TIMEOUT_MINUTES = 5
MAX_TEXT_LENGTH = 4000
MAX_USERNAME_LENGTH = 32

# Баны
BAN_DURATIONS = {
    "1_day": 1,
    "3_days": 3,
    "7_days": 7,
    "30_days": 30,
    "forever": 0
}

# Промокоды
PROMO_CODE_LENGTH = 8
MIN_PROMO_ACTIVATIONS = 1
MAX_PROMO_ACTIVATIONS = 1000

# Рассылка
BROADCAST_DELAY = 0.1
MAX_BROADCAST_RETRIES = 3

# Логирование
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Уведомления
NOTIFY_VIP_EXPIRE_DAYS = [7, 3, 1]
NOTIFY_REPORT = True
NOTIFY_AUTO_REPORTS = True
AUTO_REPORT_TIME = "09:00"
