import logging
from datetime import datetime

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ContentType, InlineKeyboardMarkup, InlineKeyboardButton

from config import (
    CHANNEL_ID, REPORT_CHAT_ID, BASE_EMOJIS, VIP_EMOJIS,
    NOTIFY_REPORT
)
from database import (
    create_user, get_user, is_vip, is_banned, get_user_stats, get_user_role,
    get_top_users, get_user_by_username, update_user_activity, add_vip_days,
    activate_promo_code, create_confession, get_confession, update_confession_message_id,
    create_report, get_confessions_by_user, db_exec, db_fetch_one,
    get_user_achievements, award_achievement, get_all_achievements,
    check_text_blacklist, add_warn,
    # whois
    create_whois_game, get_whois_game, get_whois_game_by_creator,
    get_whois_game_by_opponent, set_whois_opponent, increment_questions_asked,
    complete_whois_game, is_whois_enabled,
    # battle
    add_battle_participant, remove_battle_participant, get_battle_participants,
    is_battle_enabled,
    # admin_logs
    add_admin_log, get_all_admins
)
from utils import (
    check_subscription, format_time_left, format_user_name,
    check_ban_decorator, html_escape
)
from keyboards import (
    get_subscription_keyboard, get_main_menu_keyboard, get_profile_keyboard,
    get_emoji_keyboard, get_vip_menu_keyboard, get_back_keyboard,
    get_cancel_keyboard, get_confession_keyboard, get_skip_media_keyboard,
    get_confirmation_keyboard, get_reveal_request_keyboard,
    get_whois_menu_keyboard, get_battle_menu_keyboard
)

logger = logging.getLogger(__name__)


# ==================== FSM Состояния ====================

class ConfessionForm(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_confirmation = State()

class PromoForm(StatesGroup):
    waiting_for_code = State()

class WhoIsGuessForm(StatesGroup):
    waiting_for_question = State()   # автор ожидает ввода вопроса
    waiting_for_answer = State()     # оппонент ожидает ввода ответа


# ==================== Вспомогательные функции ====================

async def require_sub(message: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_ID.replace('@','')}"))
    kb.add(InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub"))
    await message.answer("❌ Подпишись на телеграм-канал для продолжения:", reply_markup=kb)


# ==================== СТАРЫЕ КОМАНДЫ (из bot.py) ====================

@check_ban_decorator
async def cmd_start(message: types.Message, state: FSMContext):
    args = message.get_args()
    create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    if not await check_subscription(message.from_user.id, message.bot):
        await require_sub(message)
        return
    if args:
        try:
            if args.startswith("ref_"):
                target_id = int(args.split("_", 1)[1])
                if target_id == message.from_user.id:
                    await message.answer("😅 Нельзя отправлять признания самому себе.")
                    return
                await state.update_data(target_id=target_id)
                if is_vip(message.from_user.id):
                    await ConfessionForm.waiting_for_text.set()
                    await message.answer(
                        "✍️ Напиши своё анонимное признание для этого человека.\n\n"
                        "ℹ️ <b>Как VIP пользователь ты можешь:</b>\n"
                        "• Добавить фото после текста\n"
                        "• Добавить видео\n"
                        "• Добавить голосовое сообщение\n"
                        "• Добавить стикер\n\n"
                        "Напиши текст признания:",
                        reply_markup=get_cancel_keyboard()
                    )
                else:
                    await ConfessionForm.waiting_for_text.set()
                    await message.answer(
                        "✍️ Напиши своё анонимное признание для этого человека.",
                        reply_markup=get_cancel_keyboard()
                    )
            elif args.startswith("whois_"):
                # Новая логика whois
                game_id = int(args.split("_")[1])
                game = get_whois_game(game_id)
                if not game:
                    await message.answer("❌ Игра не найдена.")
                    return
                if game[3] != 'waiting':  # status
                    await message.answer("❌ Эта игра уже начата или завершена.")
                    return
                if message.from_user.id == game[1]:  # creator_id
                    await message.answer("❌ Вы не можете играть сами с собой.")
                    return
                set_whois_opponent(game_id, message.from_user.id)
                creator_id = game[1]
                try:
                    await message.bot.send_message(
                        creator_id,
                        "🎭 Кто-то перешёл по вашей ссылке! Игра началась.\n"
                        "У вас есть 3 вопроса, чтобы угадать, кто это.\n"
                        "Используйте /вопрос ваш_текст, чтобы задать вопрос.\n"
                        "После любого вопроса можете попытаться угадать: /угадать имя"
                    )
                except Exception as e:
                    logger.error(f"Не удалось уведомить автора {creator_id}: {e}")
                await state.update_data(whois_game_id=game_id, role='opponent')
                await WhoIsGuessForm.waiting_for_answer.set()
                await message.answer(
                    "✅ Вы присоединились к игре! Теперь автор будет задавать вам вопросы.\n"
                    "Отвечайте на них честно (но анонимно)."
                )
            else:
                await message.answer("❌ Неверная ссылка.")
        except Exception as e:
            logger.error(f"Ошибка в start args: {e}")
            await message.answer("❌ Неверная ссылка.")
    else:
        link = f"https://t.me/{(await message.bot.get_me()).username}?start=ref_{message.from_user.id}"
        user_vip = is_vip(message.from_user.id)
        whois_enabled = is_whois_enabled()
        battle_enabled = is_battle_enabled()
        welcome_text = (
            f"👋 Привет!\n\n"
            f"Вот твоя уникальная ссылка для признаний:\n\n"
            f"{link}\n\n"
            f"Отправь её друзьям, чтобы они могли написать тебе анонимное сообщение."
        )
        if user_vip:
            welcome_text += f"\n\n⭐ <b>Ты VIP пользователь!</b> Доступны расширенные функции:\n• Добавление фото/видео к признаниям\n• Голосовые сообщения\n• Редактирование признаний"
        await message.answer(
            welcome_text,
            reply_markup=get_main_menu_keyboard(user_vip, whois_enabled, battle_enabled)
        )


@check_ban_decorator
async def cmd_profile(message: types.Message):
    # Создаём пользователя, если его нет
    create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)

    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.answer("❌ Пользователь не найден.")
        return
    stats = get_user_stats(user_id)
    user_vip = is_vip(user_id)
    emoji = user[6] if user[6] else "💍"
    profile_text = (
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: {user_id}\n"
        f"👁️‍🗨️ Эмодзи: {emoji}\n"
    )
    if user_vip:
        vip_until = format_time_left(user[5])
        profile_text += f"⭐ VIP до: {vip_until}\n\n"
    else:
        profile_text += f"❌ Нет VIP\n\n"
    profile_text += (
        f"📊 <b>Статистика:</b>\n"
        f"📩 Получено признаний: {stats['received']}\n"
        f"📤 Отправлено признаний: {stats['sent']}\n"
        f"🚩 Подано жалоб: {stats['reports']}\n"
    )
    user_role = get_user_role(user_id)
    if user_role:
        profile_text += f"\n👮 <b>Статус: {user_role.upper()}</b>"
    await message.answer(profile_text, reply_markup=get_profile_keyboard())


@check_ban_decorator
async def cmd_top(message: types.Message):
    top_users = get_top_users(10)
    if not top_users:
        await message.answer("🏆 Топ пользователей пока пуст.")
        return
    text = "🏆 <b>Топ пользователей по полученным признаниям:</b>\n\n"
    for i, user in enumerate(top_users, 1):
        user_id, username, count = user
        display_name = f"@{username}" if username else f"User {user_id}"
        user_data = get_user(user_id)
        if user_data and user_data[6]:
            emoji = user_data[6]
            display_name = f"{emoji} {display_name}"
        user_role = get_user_role(user_id)
        if user_role:
            display_name += " 👮"
        text += f"{i}. {display_name} - {count} признаний\n"
    await message.answer(text)


@check_ban_decorator
async def cmd_promo(message: types.Message):
    await PromoForm.waiting_for_code.set()
    await message.answer(
        "🎁 Введите промокод для активации VIP:",
        reply_markup=get_cancel_keyboard()
    )


@check_ban_decorator
async def cmd_help(message: types.Message):
    help_text = (
        "📚 <b>Помощь по боту:</b>\n\n"
        "👤 <b>Основные команды:</b>\n"
        "/start - Запустить бота, получить ссылку\n"
        "/profile - Ваш профиль и статистика\n"
        "/top - Топ пользователей\n"
        "/promo - Активировать промокод\n\n"
        "📨 <b>Как отправить признание:</b>\n"
        "1. Получи свою ссылку через /start\n"
        "2. Отправь другу свою ссылку\n"
        "3. Друг переходит по ссылке и пишет признание\n"
        "4. Ты получаешь анонимное сообщение\n\n"
        "⭐ <b>VIP возможности:</b>\n"
        "• Добавление фото к признаниям\n"
        "• Добавление видео к признаниям\n"
        "• Голосовые сообщения\n"
        "• Стикеры в признаниях\n"
        "• Расширенная статистика\n"
        "• Специальные эмодзи\n"
        "• Редактирование признаний\n\n"
        "🎭 <b>Ивенты:</b>\n"
        "/whois_menu - Режим \"Кто я?\" (если активен)\n"
        "/battle_menu - Анонимный батл (если активен)\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Подписка на канал обязательна\n"
        "• Нельзя отправлять признания самому себе\n"
        "• Оскорбления и спам наказываются баном"
    )
    await message.answer(help_text)


# ==================== СТАРЫЕ ОБРАБОТЧИКИ ПРИЗНАНИЙ ====================

@check_ban_decorator
async def process_confession_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("target_id")
    text = message.text.strip()
    # Проверка на чёрный список
    if check_text_blacklist(text):
        await message.answer("❌ Ваш текст содержит запрещённые слова.")
        return
    confession_id = create_confession(message.from_user.id, target_id, text)
    await state.update_data(confession_id=confession_id, text=text)
    if is_vip(message.from_user.id):
        await ConfessionForm.waiting_for_media.set()
        await message.answer(
            "✅ Текст сохранен!\n\n"
            "📎 <b>Как VIP пользователь ты можешь добавить:</b>\n"
            "• 1 фото\n"
            "• 1 видео\n"
            "• 1 голосовое сообщение\n"
            "• 1 стикер\n\n"
            "Отправь медиа или нажми кнопку чтобы пропустить:",
            reply_markup=get_skip_media_keyboard()
        )
    else:
        await send_confession_final(message, state)


async def send_confession_final(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        target_id = data.get('target_id')
        text = data.get('text')
        confession_id = data.get('confession_id')
        if not target_id or not text:
            await message.answer("❌ Ошибка: данные не найдены.")
            await state.finish()
            return
        confession = get_confession(confession_id)
        is_vip_sender = confession[8] if confession else 0
        logger.info(f"Отправка обычного признания #{confession_id}: от {message.from_user.id} к {target_id}")
        sent = await message.bot.send_message(
            target_id,
            f"📩 Вам пришло новое анонимное признание:\n\n{text}",
            reply_markup=get_confession_keyboard(confession_id, is_vip_sender)
        )
        update_confession_message_id(confession_id, sent.message_id)
        logger.info(f"Обычное признание #{confession_id} отправлено успешно")
        await message.answer("✅ Твоё признание отправлено!")
    except Exception as e:
        logger.error(f"Ошибка отправки обычного признания: {e}")
        await message.answer("❌ Не удалось доставить сообщение.")
    await state.finish()


@check_ban_decorator
async def process_confession_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    confession_id = data.get('confession_id')
    text = data.get('text')
    media_type = None
    media_file_id = None
    if message.photo:
        media_type = 'photo'
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_type = 'video'
        media_file_id = message.video.file_id
    elif message.voice:
        media_type = 'voice'
        media_file_id = message.voice.file_id
    elif message.sticker:
        media_type = 'sticker'
        media_file_id = message.sticker.file_id
    if media_type and media_file_id:
        await state.update_data(
            media_type=media_type,
            media_file_id=media_file_id
        )
        if media_type == 'photo':
            await message.bot.send_photo(
                message.chat.id,
                media_file_id,
                caption=f"📸 <b>Превью фото:</b>\n\n{text}\n\n✅ Медиа добавлено! Отправляем признание?"
            )
        elif media_type == 'video':
            await message.bot.send_video(
                message.chat.id,
                media_file_id,
                caption=f"🎥 <b>Превью видео:</b>\n\n{text}\n\n✅ Медиа добавлено! Отправляем признание?"
            )
        elif media_type == 'voice':
            await message.bot.send_voice(
                message.chat.id,
                media_file_id,
                caption=f"🎤 <b>Превью голосового:</b>\n\n{text}\n\n✅ Медиа добавлено! Отправляем признание?"
            )
        elif media_type == 'sticker':
            await message.bot.send_sticker(message.chat.id, media_file_id)
            await message.answer(f"💬 <b>Превью стикера:</b>\n\n{text}\n\n✅ Медиа добавлено! Отправляем признание?")
        await ConfessionForm.waiting_for_confirmation.set()
        await message.answer(
            "Нажми кнопку чтобы отправить признание:",
            reply_markup=get_confirmation_keyboard(confession_id)
        )


@check_ban_decorator
async def skip_media(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    confession_id = data.get('confession_id')
    text = data.get('text')
    await call.message.edit_text(
        f"✅ Без медиа. Текст признания:\n\n{text}\n\nОтправляем?"
    )
    await ConfessionForm.waiting_for_confirmation.set()
    await call.message.answer(
        "Нажми кнопку чтобы отправить признание:",
        reply_markup=get_confirmation_keyboard(confession_id)
    )
    await call.answer()


@check_ban_decorator
async def send_confirmation(call: types.CallbackQuery, state: FSMContext):
    try:
        confession_id = int(call.data.split('_')[2])
        confession = get_confession(confession_id)
        if not confession:
            await call.answer("❌ Ошибка: признание не найдено", show_alert=True)
            return
        data = await state.get_data()
        from_user = confession[1]
        to_user = confession[2]
        text = data.get('text', '')
        media_type = data.get('media_type')
        media_file_id = data.get('media_file_id')
        is_vip_sender = confession[8] if confession else 0
        logger.info(f"Отправка признания #{confession_id}: от {from_user} к {to_user}, текст: '{text[:50]}...', медиа: {media_type}, файл: {media_file_id}")
        caption = f"📩 Вам пришло новое анонимное признание:\n\n{text}" if text else "📩 Вам пришло новое анонимное признание."
        kb = get_confession_keyboard(confession_id, is_vip_sender)
        sent_message = None
        if media_type == 'photo' and media_file_id:
            sent_message = await call.bot.send_photo(
                chat_id=to_user,
                photo=media_file_id,
                caption=caption,
                reply_markup=kb
            )
        elif media_type == 'video' and media_file_id:
            sent_message = await call.bot.send_video(
                chat_id=to_user,
                video=media_file_id,
                caption=caption,
                reply_markup=kb
            )
        elif media_type == 'voice' and media_file_id:
            sent_message = await call.bot.send_voice(
                chat_id=to_user,
                voice=media_file_id,
                caption=caption,
                reply_markup=kb
            )
        elif media_type == 'sticker' and media_file_id:
            await call.bot.send_message(
                chat_id=to_user,
                text=caption,
                reply_markup=kb
            )
            sent_message = await call.bot.send_sticker(
                chat_id=to_user,
                sticker=media_file_id
            )
        else:
            sent_message = await call.bot.send_message(
                chat_id=to_user,
                text=caption,
                reply_markup=kb
            )
        if sent_message:
            update_confession_message_id(confession_id, sent_message.message_id)
        await call.message.edit_text("✅ Твоё признание отправлено!")
        await state.finish()
        await call.answer()
    except Exception as e:
        logger.error(f"Ошибка отправки признания: {e}")
        await call.answer("❌ Не удалось доставить сообщение", show_alert=True)
        await call.message.edit_text("❌ Произошла ошибка при отправке.")


# ==================== СТАРЫЕ CALLBACK'И ====================

@check_ban_decorator
async def check_sub_callback(call: types.CallbackQuery):
    is_subscribed = await check_subscription(call.from_user.id, call.bot)
    if is_subscribed:
        create_user(call.from_user.id, call.from_user.username, call.from_user.full_name)
        await call.message.edit_text("✅ Отлично! Ты подписался.\nТеперь можешь пользоваться ботом.")
    else:
        await call.answer("❌ Ты всё ещё не подписан.", show_alert=True)


@check_ban_decorator
async def profile_callback(call: types.CallbackQuery):
    # Создаём пользователя, если его нет
    create_user(call.from_user.id, call.from_user.username, call.from_user.full_name)

    user_id = call.from_user.id
    user = get_user(user_id)
    if not user:
        await call.answer("❌ Пользователь не найден.", show_alert=True)
        return
    stats = get_user_stats(user_id)
    user_vip = is_vip(user_id)
    emoji = user[6] if user[6] else "💍"
    profile_text = (
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: {user_id}\n"
        f"👁️‍🗨️ Эмодзи: {emoji}\n"
    )
    if user_vip:
        vip_until = format_time_left(user[5])
        profile_text += f"⭐ VIP срок: {vip_until}\n\n"
    else:
        profile_text += f"❌ Нет VIP\n\n"
    profile_text += (
        f"📊 <b>Статистика:</b>\n"
        f"📩 Получено признаний: {stats['received']}\n"
        f"📤 Отправлено признаний: {stats['sent']}\n"
        f"🚩 Подано жалоб: {stats['reports']}\n"
    )
    user_role = get_user_role(user_id)
    if user_role:
        profile_text += f"\n👮 <b>Статус: {user_role.upper()}</b>"
    await call.message.edit_text(profile_text, reply_markup=get_profile_keyboard())
    await call.answer()


@check_ban_decorator
async def top_callback(call: types.CallbackQuery):
    await cmd_top(call.message)


@check_ban_decorator
async def promo_callback(call: types.CallbackQuery):
    await cmd_promo(call.message)


@check_ban_decorator
async def vip_menu_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    user_vip = is_vip(user_id)
    if user_vip:
        user = get_user(user_id)
        vip_until = format_time_left(user[5])
        text = (
            f"⭐ <b>VIP Статус</b>\n\n"
            f"Ваш VIP действует до: {vip_until}\n\n"
            f"<b>Доступные функции:</b>\n"
            f"• Добавление фото к признаниям\n"
            f"• Добавление видео к признаниям\n"
            f"• Голосовые сообщения\n"
            f"• Стикеры в признаниях\n"
            f"• Расширенная статистика\n"
            f"• Редактирование признаний\n"
            f"• Специальные эмодзи"
        )
    else:
        text = (
            "⭐ <b>VIP Подписка</b>\n\n"
            "<b>Преимущества VIP:</b>\n"
            "• Добавление фото к признаниям\n"
            "• Добавление видео к признаниям\n"
            "• Голосовые сообщения\n"
            "• Стикеры в признаниях\n"
            "• Расширенная статистика\n"
            "• Редактирование признаний\n"
            "• Специальные эмодзи\n\n"
            "Нажми 'Купить VIP' для покупки."
        )
    await call.message.edit_text(text, reply_markup=get_vip_menu_keyboard())
    await call.answer()


@check_ban_decorator
async def vip_info_callback(call: types.CallbackQuery):
    text = (
        "⭐ <b>VIP возможности:</b>\n\n"
        "• <b>Медиа в признаниях:</b>\n"
        "  - Добавление фото к признаниям\n"
        "  - Добавление видео к признаниям\n"
        "  - Голосовые сообщения\n"
        "  - Стикеры в признаниях\n\n"
        "• <b>Расширенная статистика:</b>\n"
        "  - Детальная аналитика\n\n"
        "• <b>Редактирование:(В разработке)</b>\n"
        "  - Редактирование отправленных признаний\n"
        "  - Время на редактирование: 5 минут\n\n"
        "• <b>Специальные эмодзи:</b>\n"
        "  👑 ⭐ 😎 💰 🚀\n\n"
        "• <b>Приоритетная поддержка</b>\n"
        "• <b>Повышенные лимиты</b>"
    )
    await call.message.edit_text(text, reply_markup=get_vip_menu_keyboard())
    await call.answer()


@check_ban_decorator
async def change_emoji_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    user_vip = is_vip(user_id)
    await call.message.edit_text(
        "Выбери эмодзи для профиля:",
        reply_markup=get_emoji_keyboard(user_vip)
    )


@check_ban_decorator
async def select_emoji_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    emoji = call.data.split('_')[1]
    user_vip = is_vip(user_id)
    if emoji.startswith('locked'):
        actual_emoji = emoji.replace('locked_', '')
        if actual_emoji in VIP_EMOJIS:
            await call.answer("❌ Эта эмодзи доступна только VIP пользователям!", show_alert=True)
            return
        else:
            emoji = actual_emoji
    if emoji in VIP_EMOJIS and not user_vip:
        await call.answer("❌ Эта эмодзи доступна только VIP пользователям!", show_alert=True)
        return
    if emoji not in BASE_EMOJIS and emoji not in VIP_EMOJIS:
        await call.answer("❌ Неизвестный эмодзи", show_alert=True)
        return
    db_exec("UPDATE users SET emoji = ? WHERE id = ?", (emoji, user_id))
    await call.answer(f"✅ Эмодзи изменен на {emoji}")
    await profile_callback(call)


@check_ban_decorator
async def cancel_emoji_callback(call: types.CallbackQuery):
    await profile_callback(call)


@check_ban_decorator
async def back_to_menu_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    user_vip = is_vip(user_id)
    whois_enabled = is_whois_enabled()
    battle_enabled = is_battle_enabled()
    link = f"https://t.me/{(await call.bot.get_me()).username}?start=ref_{user_id}"
    username = call.from_user.username
    full_name = call.from_user.full_name
    display_name = f"@{username}" if username else full_name
    welcome_text = (
        f"👋 Привет, {display_name}!\n\n"
        f"Вот твоя уникальная ссылка для признаний:\n\n"
        f"{link}\n\n"
        f"Отправь её друзьям, чтобы они могли написать тебе анонимное сообщение."
    )
    if user_vip:
        welcome_text += f"\n\n⭐ <b>Ты VIP пользователь!</b> Доступны расширенные функции:\n• Добавление фото/видео к признаниям\n• Голосовые сообщения\n• Редактирование признаний"
    await call.message.edit_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard(user_vip, whois_enabled, battle_enabled)
    )
    await call.answer()


@check_ban_decorator
async def reveal_request_callback(call: types.CallbackQuery):
    try:
        confession_id = int(call.data.replace("reveal_", ""))
        confession = get_confession(confession_id)
        if not confession:
            await call.answer("Сообщение не найдено", show_alert=True)
            return
        from_user, to_user, text, status = confession[1], confession[2], confession[4], confession[7]
        if status != 0:
            await call.answer("Запрос уже сделан.", show_alert=True)
            return
        update_reveal_status(confession_id, 1)
        kb = get_reveal_request_keyboard(confession_id)
        try:
            await call.bot.send_message(
                from_user,
                f"👀 Получатель вашего признания (ID {to_user}) просит раскрыть ваш username.\n\n"
                f"Текст: \"{text[:200]}\"\n\nРазрешить?",
                reply_markup=kb
            )
            await call.answer("Запрос отправлен автору.", show_alert=True)
        except Exception as e:
            logger.error(f"Не удалось связаться с автором {from_user}: {e}")
            await call.answer("Не удалось связаться с автором.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в reveal_request: {e}")
        await call.answer("❌ Ошибка", show_alert=True)


@check_ban_decorator
async def reveal_allow_callback(call: types.CallbackQuery):
    try:
        confession_id = int(call.data.replace("reveal_allow_", ""))
        confession = get_confession(confession_id)
        if not confession:
            await call.answer("Данные не найдены", show_alert=True)
            return
        from_user, to_user = confession[1], confession[2]
        if call.from_user.id != from_user:
            await call.answer("Это не ваше признание.", show_alert=True)
            return
        update_reveal_status(confession_id, 2)
        username = call.from_user.username
        if username:
            await call.bot.send_message(to_user, f"✅ Автор согласился раскрыть себя: @{username}")
        else:
            await call.bot.send_message(to_user, f"✅ Автор согласился раскрыть себя (ID: {call.from_user.id})")
        await call.message.edit_text("✅ Вы раскрыли себя.", reply_markup=None)
        await call.answer("Вы раскрыли себя.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в reveal_allow: {e}")
        await call.answer("❌ Ошибка", show_alert=True)


@check_ban_decorator
async def reveal_deny_callback(call: types.CallbackQuery):
    try:
        confession_id = int(call.data.replace("reveal_deny_", ""))
        confession = get_confession(confession_id)
        if not confession:
            await call.answer("Данные не найдены", show_alert=True)
            return
        from_user, to_user = confession[1], confession[2]
        if call.from_user.id != from_user:
            await call.answer("Это не ваше признание.", show_alert=True)
            return
        update_reveal_status(confession_id, 3)
        await call.bot.send_message(to_user, "❌ Автор отказался раскрывать себя.")
        await call.message.edit_text("❌ Вы отказались раскрывать себя.", reply_markup=None)
        await call.answer("Вы отказались раскрывать себя.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в reveal_deny: {e}")
        await call.answer("❌ Ошибка", show_alert=True)


@check_ban_decorator
async def report_callback(call: types.CallbackQuery):
    confession_id = int(call.data.split("_")[1])
    reporter_id = call.from_user.id
    confession = get_confession(confession_id)
    if not confession:
        await call.answer("Ошибка: сообщение не найдено", show_alert=True)
        return
    from_user, to_user, text = confession[1], confession[2], confession[4]
    report_id = create_report(confession_id, reporter_id)
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🚫 Забанить автора", callback_data=f"banuser_{from_user}_{report_id}"),
        InlineKeyboardButton("✅ Игнорировать", callback_data=f"ignore_{report_id}")
    )
    try:
        await call.bot.send_message(
            REPORT_CHAT_ID,
            f"🚩 <b>Новая жалоба</b>\n\n"
            f"🔸 ID жалобы: <code>{report_id}</code>\n"
            f"🔸 ID признания: <code>{confession_id}</code>\n"
            f"🔸 Текст: {html_escape(text)}\n\n"
            f"🔸 ID автора (from_user): <code>{from_user}</code>\n"
            f"🔸 ID получателя (to_user): <code>{to_user}</code>\n"
            f"🔸 ID пожаловавшегося (reporter): <code>{reporter_id}</code>",
            reply_markup=kb
        )
        await call.answer("Жалоба отправлена модераторам.", show_alert=True)
        if NOTIFY_REPORT:
            admins = get_all_admins()
            for admin_id, role in admins:
                if role in ["owner", "admin", "moderator"]:
                    try:
                        await call.bot.send_message(admin_id, f"🚩 Новая жалоба #{report_id}")
                    except:
                        pass
    except Exception as e:
        logger.error(f"Ошибка отправки жалобы: {e}")
        await call.answer("Ошибка при отправке жалобы.", show_alert=True)


@check_ban_decorator
async def vip_sender_info_callback(call: types.CallbackQuery):
    await call.answer("ℹ️ Это сообщение отправлено VIP пользователем. Они могут добавлять фото, видео и голосовые сообщения к своим признаниям.", show_alert=True)


@check_ban_decorator
async def cancel_action_callback(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    user_vip = is_vip(call.from_user.id)
    whois_enabled = is_whois_enabled()
    battle_enabled = is_battle_enabled()
    await call.message.edit_text(
        "❌ Действие отменено.",
        reply_markup=get_main_menu_keyboard(user_vip, whois_enabled, battle_enabled)
    )


# ==================== ПРОМОКОД ====================

@check_ban_decorator
async def process_promo_code(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    if not code:
        await message.answer("❌ Промокод не может быть пустым.")
        return
    vip_days = activate_promo_code(message.from_user.id, code)
    if vip_days:
        add_vip_days(message.from_user.id, vip_days)
        await message.answer(
            f"✅ Промокод активирован!\n"
            f"⭐ VIP подписка продлена на {vip_days} дней."
        )
    else:
        await message.answer("❌ Неверный промокод, лимит исчерпан или промокод уже был активирован.")
    await state.finish()


@check_ban_decorator
async def cancel_promo(message: types.Message, state: FSMContext):
    await state.finish()
    user_vip = is_vip(message.from_user.id)
    whois_enabled = is_whois_enabled()
    battle_enabled = is_battle_enabled()
    await message.answer(
        "❌ Активация промокода отменена.",
        reply_markup=get_main_menu_keyboard(user_vip, whois_enabled, battle_enabled)
    )


# ==================== ДОСТИЖЕНИЯ ====================

@check_ban_decorator
async def my_achievements_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    # Создаём пользователя, если его нет (на всякий случай)
    create_user(user_id, call.from_user.username, call.from_user.full_name)
    achievements = get_user_achievements(user_id)
    if not achievements:
        text = "🏅 У вас пока нет достижений."
    else:
        text = "🏅 <b>Ваши достижения:</b>\n\n"
        for a in achievements:
            text += f"• {a[1]} – {a[3][:10]}\n"
    await call.message.edit_text(text, reply_markup=get_back_keyboard())


# ==================== НОВЫЙ РЕЖИМ "КТО Я?" ====================

@check_ban_decorator
async def cmd_whois_menu(message: types.Message):
    if not is_whois_enabled():
        await message.answer("🎭 Режим 'Кто я?' сейчас не активен.")
        return
    await message.answer(
        "🎭 <b>Режим \"Кто я?\"</b>\n\n"
        "Создайте игру и отправьте ссылку другу. Вы будете задавать вопросы, а ваш собеседник – отвечать.\n"
        "У вас есть 3 вопроса, чтобы угадать его личность.",
        reply_markup=get_whois_menu_keyboard()
    )


@check_ban_decorator
async def whois_create_callback(call: types.CallbackQuery):
    if not is_whois_enabled():
        await call.answer("Режим не активен", show_alert=True)
        return
    user_id = call.from_user.id
    existing = get_whois_game_by_creator(user_id, 'waiting')
    if existing:
        await call.answer("У вас уже есть ожидающая игра.", show_alert=True)
        return
    game_id = create_whois_game(user_id)
    bot_username = (await call.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=whois_{game_id}"
    await call.message.edit_text(
        f"🎭 Ваша игра создана!\n\nСсылка для друга:\n{link}\n\n"
        f"Как только кто-то перейдёт по ней, вы получите уведомление.",
        reply_markup=get_back_keyboard()
    )


@check_ban_decorator
async def whois_question_cmd(message: types.Message, state: FSMContext):
    """Команда /вопрос текст – задать вопрос (только для автора)"""
    user_id = message.from_user.id
    data = await state.get_data()
    game_id = data.get('whois_game_id')
    if not game_id:
        game = get_whois_game_by_creator(user_id, 'active')
        if not game:
            await message.answer("❌ У вас нет активной игры.")
            return
        game_id = game[0]
        await state.update_data(whois_game_id=game_id, role='creator')
    else:
        if data.get('role') != 'creator':
            await message.answer("❌ Вы не автор этой игры.")
            return
        game = get_whois_game(game_id)
        if not game or game[3] != 'active':
            await message.answer("❌ Игра не активна.")
            return
    text = message.get_args().strip()
    if not text:
        await message.answer("❌ Введите текст вопроса. Пример: /вопрос Какой у тебя любимый цвет?")
        return
    if game[4] >= 3:  # questions_asked
        await message.answer("❌ Вы уже задали 3 вопроса. Игра завершена.")
        complete_whois_game(game_id, game[2])  # opponent_id
        await state.finish()
        return
    opponent_id = game[2]
    try:
        await message.bot.send_message(
            opponent_id,
            f"❓ Вопрос от автора: {text}\n\nОтветьте текстом."
        )
        increment_questions_asked(game_id)
        await message.answer("✅ Вопрос отправлен. Ожидайте ответ.")
    except Exception as e:
        logger.error(f"Не удалось отправить вопрос оппоненту {opponent_id}: {e}")
        await message.answer("❌ Не удалось отправить вопрос. Возможно, оппонент покинул бота.")


@check_ban_decorator
async def whois_answer_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    game_id = data.get('whois_game_id')
    if not game_id:
        await message.answer("❌ Ошибка: игра не найдена.")
        await state.finish()
        return
    game = get_whois_game(game_id)
    if not game or game[3] != 'active':
        await message.answer("❌ Игра не активна.")
        await state.finish()
        return
    creator_id = game[1]
    answer = message.text.strip()
    try:
        await message.bot.send_message(
            creator_id,
            f"💬 Ответ на ваш вопрос: {answer}\n\n"
            f"Вы можете задать следующий вопрос (/вопрос) или попытаться угадать (/угадать имя)."
        )
        await message.answer("✅ Ответ отправлен автору.")
    except Exception as e:
        logger.error(f"Не удалось отправить ответ автору {creator_id}: {e}")
        await message.answer("❌ Не удалось доставить ответ.")


@check_ban_decorator
async def whois_guess_cmd(message: types.Message, state: FSMContext):
    """Команда /угадать имя – попытка угадать (только для автора)"""
    user_id = message.from_user.id
    data = await state.get_data()
    game_id = data.get('whois_game_id')
    if not game_id:
        game = get_whois_game_by_creator(user_id, 'active')
        if not game:
            await message.answer("❌ У вас нет активной игры.")
            return
        game_id = game[0]
        await state.update_data(whois_game_id=game_id, role='creator')
    else:
        if data.get('role') != 'creator':
            await message.answer("❌ Вы не автор этой игры.")
            return
    game = get_whois_game(game_id)
    if not game or game[3] != 'active':
        await message.answer("❌ Игра не активна.")
        return
    guess = message.get_args().strip().lower()
    if not guess:
        await message.answer("❌ Введите имя или username для угадывания. Пример: /угадать @username")
        return
    opponent_id = game[2]
    opponent = get_user(opponent_id)
    if not opponent:
        await message.answer("❌ Ошибка: оппонент не найден.")
        return
    correct_username = opponent[1].lower() if opponent[1] else ""
    correct_name = opponent[2].lower() if opponent[2] else ""
    if guess == correct_username or guess in correct_name or guess == correct_name:
        complete_whois_game(game_id, user_id)
        await message.answer("✅ Поздравляю! Вы угадали. Вы победили!")
        try:
            await message.bot.send_message(opponent_id, "😢 Вы проиграли. Автор угадал вашу личность.")
        except:
            pass
        await state.finish()
    else:
        if game[4] >= 3:
            complete_whois_game(game_id, opponent_id)
            await message.answer("❌ Вы не угадали и исчерпали все вопросы. Вы проиграли.")
            try:
                await message.bot.send_message(opponent_id, "🎉 Вы победили! Автор не смог угадать.")
            except:
                pass
            await state.finish()
        else:
            await message.answer("❌ Неверно. У вас остались вопросы. Можете задать ещё.")


# ==================== АНОНИМНЫЙ БАТЛ ====================

@check_ban_decorator
async def cmd_battle_menu(message: types.Message):
    if not is_battle_enabled():
        await message.answer("⚔ Анонимный батл сейчас не активен.")
        return
    participants = get_battle_participants()
    count = len(participants)
    text = (
        f"⚔ <b>Анонимный батл</b>\n\n"
        f"Участников: {count}\n\n"
        f"Присоединяйтесь и сражайтесь анонимно!"
    )
    await message.answer(text, reply_markup=get_battle_menu_keyboard())


@check_ban_decorator
async def battle_join_callback(call: types.CallbackQuery):
    if not is_battle_enabled():
        await call.answer("Батл не активен", show_alert=True)
        return
    user_id = call.from_user.id
    if add_battle_participant(user_id):
        await call.answer("✅ Вы присоединились к батлу!", show_alert=True)
        participants = get_battle_participants()
        count = len(participants)
        await call.message.edit_text(
            f"⚔ Вы в батле! Участников: {count}",
            reply_markup=get_battle_menu_keyboard()
        )
    else:
        await call.answer("❌ Вы уже в батле", show_alert=True)


@check_ban_decorator
async def battle_leave_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    remove_battle_participant(user_id)
    await call.answer("❌ Вы покинули батл", show_alert=True)
    participants = get_battle_participants()
    count = len(participants)
    await call.message.edit_text(
        f"⚔ Вы покинули батл. Участников: {count}",
        reply_markup=get_battle_menu_keyboard()
    )


@check_ban_decorator
async def battle_stats_callback(call: types.CallbackQuery):
    participants = get_battle_participants()
    if not participants:
        await call.answer("Участников пока нет", show_alert=True)
        return
    text = "⚔ Участники батла:\n\n"
    for uid in participants:
        user = get_user(uid)
        name = format_user_name(user)
        text += f"• {name}\n"
    await call.message.edit_text(text, reply_markup=get_battle_menu_keyboard())


# ==================== РЕГИСТРАЦИЯ ХЕНДЛЕРОВ ====================

def register_user_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=['start'], state='*')
    dp.register_message_handler(cmd_profile, commands=['profile'], state=None)
    dp.register_message_handler(cmd_top, commands=['top'], state=None)
    dp.register_message_handler(cmd_promo, commands=['promo'], state=None)
    dp.register_message_handler(cmd_help, commands=['help'], state=None)
    dp.register_message_handler(cmd_whois_menu, commands=['whois_menu'], state=None)
    dp.register_message_handler(cmd_battle_menu, commands=['battle_menu'], state=None)
    dp.register_message_handler(whois_question_cmd, commands=['вопрос'], state='*')
    dp.register_message_handler(whois_guess_cmd, commands=['угадать'], state='*')

    dp.register_message_handler(process_confession_text, state=ConfessionForm.waiting_for_text, content_types=ContentType.TEXT)
    dp.register_message_handler(process_confession_media, state=ConfessionForm.waiting_for_media, content_types=[ContentType.PHOTO, ContentType.VIDEO, ContentType.VOICE, ContentType.STICKER])
    dp.register_message_handler(process_promo_code, state=PromoForm.waiting_for_code, content_types=ContentType.TEXT)
    dp.register_message_handler(cancel_promo, commands=['cancel'], state=PromoForm.waiting_for_code)
    dp.register_message_handler(whois_answer_handler, state=WhoIsGuessForm.waiting_for_answer, content_types=ContentType.TEXT)

    dp.register_callback_query_handler(check_sub_callback, lambda c: c.data == 'check_sub')
    dp.register_callback_query_handler(profile_callback, lambda c: c.data == 'profile')
    dp.register_callback_query_handler(top_callback, lambda c: c.data == 'top_users')
    dp.register_callback_query_handler(promo_callback, lambda c: c.data == 'promo_code')
    dp.register_callback_query_handler(vip_menu_callback, lambda c: c.data == 'vip_menu')
    dp.register_callback_query_handler(vip_info_callback, lambda c: c.data == 'vip_info')
    dp.register_callback_query_handler(change_emoji_callback, lambda c: c.data == 'change_emoji')
    dp.register_callback_query_handler(select_emoji_callback, lambda c: c.data.startswith('emoji_'))
    dp.register_callback_query_handler(cancel_emoji_callback, lambda c: c.data == 'cancel_emoji')
    dp.register_callback_query_handler(back_to_menu_callback, lambda c: c.data == 'back_to_menu')
    dp.register_callback_query_handler(reveal_request_callback, lambda c: c.data.startswith('reveal_') and not c.data.startswith('reveal_allow_') and not c.data.startswith('reveal_deny_'))
    dp.register_callback_query_handler(reveal_allow_callback, lambda c: c.data.startswith('reveal_allow_'))
    dp.register_callback_query_handler(reveal_deny_callback, lambda c: c.data.startswith('reveal_deny_'))
    dp.register_callback_query_handler(report_callback, lambda c: c.data.startswith('report_'))
    dp.register_callback_query_handler(vip_sender_info_callback, lambda c: c.data.startswith('vip_sender_'))
    dp.register_callback_query_handler(cancel_action_callback, lambda c: c.data == 'cancel_action', state='*')
    dp.register_callback_query_handler(skip_media, lambda c: c.data == 'skip_media', state=ConfessionForm.waiting_for_media)
    dp.register_callback_query_handler(send_confirmation, lambda c: c.data.startswith('send_confession_'), state=ConfessionForm.waiting_for_confirmation)
    dp.register_callback_query_handler(my_achievements_callback, lambda c: c.data == 'my_achievements')

    # whois callbacks
    dp.register_callback_query_handler(whois_create_callback, lambda c: c.data == 'whois_create')

    # battle callbacks
    dp.register_callback_query_handler(battle_join_callback, lambda c: c.data == 'battle_join')
    dp.register_callback_query_handler(battle_leave_callback, lambda c: c.data == 'battle_leave')
    dp.register_callback_query_handler(battle_stats_callback, lambda c: c.data == 'battle_stats')