import asyncio
import logging
import sys
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import API_TOKEN, OWNER, LOG_PATH
from database import init_db
from middlewares import BanMiddleware, MaintenanceMiddleware, RoleMiddleware, AntiSpamMiddleware
from handlers.user import register_user_handlers
from handlers.admin import register_admin_handlers
import utils

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Создание папок
def create_folders():
    import os
    from config import LOG_PATH, BACKUP_PATH
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    os.makedirs(BACKUP_PATH, exist_ok=True)

# Планировщики
async def auto_delete_scheduler():
    """Автоудаление признаний старше 3 дней"""
    while True:
        await asyncio.sleep(86400)  # раз в сутки
        from database import db_exec
        deleted = db_exec("DELETE FROM confessions WHERE created_at < datetime('now', '-3 days')")
        logger.info(f"🧹 Автоудаление: удалено {deleted} признаний")

async def rating_cache_scheduler():
    """Обновление кеша рейтинга каждые 5 минут"""
    while True:
        await asyncio.sleep(300)
        # обновляем топ в таблице rating_cache
        # (реализация опущена для краткости)
        pass

async def on_startup(dp: Dispatcher):
    create_folders()
    init_db()
    await dp.bot.set_my_commands([
        types.BotCommand("start", "Запустить бота"),
        types.BotCommand("profile", "Профиль"),
        types.BotCommand("top", "Топ пользователей"),
        types.BotCommand("promo", "Активировать промокод"),
        types.BotCommand("help", "Помощь"),
    ])
    # Запуск планировщиков
    asyncio.create_task(auto_delete_scheduler())
    asyncio.create_task(rating_cache_scheduler())
    # Уведомление владельцам
    for owner in OWNER:
        try:
            await dp.bot.send_message(owner, f"✅ Бот запущен {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            pass
    logger.info("🚀 Бот запущен")

async def on_shutdown(dp: Dispatcher):
    await dp.storage.close()
    await dp.storage.wait_closed()
    for owner in OWNER:
        try:
            await dp.bot.send_message(owner, "🛑 Бот остановлен")
        except:
            pass
    logger.info("🛑 Бот остановлен")

def main():
    bot = Bot(token=API_TOKEN, parse_mode="HTML")
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)

    # Подключаем middleware
    dp.middleware.setup(BanMiddleware())
    dp.middleware.setup(MaintenanceMiddleware())
    dp.middleware.setup(RoleMiddleware())
    dp.middleware.setup(AntiSpamMiddleware())

    # Регистрируем хендлеры
    register_user_handlers(dp)
    register_admin_handlers(dp)

    # Запуск
    from aiogram import executor
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup,
        on_shutdown=on_shutdown
    )

if __name__ == '__main__':
    main()