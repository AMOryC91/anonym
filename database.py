import sqlite3
import logging
from datetime import datetime, timedelta
from config import DB_PATH, OWNER

logger = logging.getLogger(__name__)

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Существующие таблицы
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        banned INTEGER DEFAULT 0,
        ban_until DATETIME DEFAULT NULL,
        vip_until DATETIME DEFAULT NULL,
        emoji TEXT DEFAULT '💍',
        ban_reason TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_active DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS confessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER,
        to_user INTEGER,
        message_id INTEGER,
        text TEXT,
        media_type TEXT,
        media_file_id TEXT,
        reveal_status INTEGER DEFAULT 0,
        is_vip_sender INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        can_edit_until DATETIME DEFAULT NULL
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        confession_id INTEGER,
        reporter_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS promo_codes (
        code TEXT PRIMARY KEY,
        activations INTEGER DEFAULT 1,
        activations_left INTEGER,
        vip_days INTEGER,
        created_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS promo_activations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        promo_code TEXT,
        activated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, promo_code)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_roles (
        user_id INTEGER PRIMARY KEY,
        role TEXT NOT NULL,
        granted_by INTEGER,
        granted_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        message TEXT,
        sent INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT,
        details TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # ===== НОВЫЕ ТАБЛИЦЫ =====
    
    # Чёрный список слов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS blacklist_words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT UNIQUE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Предупреждения (warn)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        admin_id INTEGER,
        reason TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Достижения
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Достижения пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_achievements (
        user_id INTEGER,
        achievement_id INTEGER,
        awarded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, achievement_id)
    )''')
    
    # Игры "Кто я?" (новая структура)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS whois_games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER,
        opponent_id INTEGER,
        status TEXT DEFAULT 'waiting',  -- waiting, active, completed
        questions_asked INTEGER DEFAULT 0,
        winner_id INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Участники батлов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS battle_participants (
        user_id INTEGER PRIMARY KEY,
        joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Кеш рейтинга (для топа)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rating_cache (
        period TEXT,
        place INTEGER,
        user_id INTEGER,
        username TEXT,
        emoji TEXT,
        count INTEGER,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (period, place)
    )''')
    
    conn.commit()
    
    # Добавляем владельцев
    for owner_id in OWNER:
        cursor.execute("INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)",
                      (owner_id, None, "Владелец"))
        cursor.execute("INSERT OR IGNORE INTO admin_roles (user_id, role, granted_by) VALUES (?, ?, ?)",
                      (owner_id, "owner", owner_id))
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

# ===== БАЗОВЫЕ ФУНКЦИИ =====
def db_exec(query: str, params: tuple = ()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    lastrowid = cur.lastrowid
    conn.close()
    return lastrowid

def db_fetch(query: str, params: tuple = ()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows

def db_fetch_one(query: str, params: tuple = ()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    conn.close()
    return row

# ===== СТАРЫЕ ФУНКЦИИ (полностью из исходного bot.py) =====

def create_user(user_id: int, username: str, full_name: str):
    return db_exec(
        "INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)",
        (user_id, username, full_name)
    )

def get_user(user_id: int):
    return db_fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))

def get_user_by_username(username: str):
    return db_fetch_one("SELECT * FROM users WHERE username = ?", (username,))

def update_user_activity(user_id: int):
    return db_exec(
        "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id = ?",
        (user_id,)
    )

def is_banned(user_id: int) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    if user[3] == 1:
        ban_until = user[4]
        if ban_until:
            try:
                if isinstance(ban_until, str):
                    ban_until_dt = datetime.strptime(ban_until, '%Y-%m-%d %H:%M:%S')
                else:
                    ban_until_dt = ban_until
                if datetime.now() > ban_until_dt:
                    unban_user(user_id)
                    return False
                return True
            except Exception as e:
                logger.error(f"Ошибка проверки срока бана: {e}")
                return True
        return True
    return False

def ban_user(user_id: int, ban_duration_days: int = 0, ban_reason: str = "не указана"):
    try:
        if ban_duration_days > 0:
            ban_until = (datetime.now() + timedelta(days=ban_duration_days)).strftime('%Y-%m-%d %H:%M:%S')
        else:
            ban_until = None
        user = get_user(user_id)
        if not user:
            return db_exec(
                """INSERT INTO users (id, username, full_name, banned, ban_until, ban_reason) 
                   VALUES (?, ?, ?, 1, ?, ?)""",
                (user_id, None, None, ban_until, ban_reason)
            )
        else:
            return db_exec(
                """UPDATE users SET banned = 1, ban_until = ?, ban_reason = ? WHERE id = ?""",
                (ban_until, ban_reason, user_id)
            )
    except Exception as e:
        logger.error(f"Ошибка бана пользователя {user_id}: {e}")
        return None

def unban_user(user_id: int):
    return db_exec(
        "UPDATE users SET banned = 0, ban_until = NULL, ban_reason = NULL WHERE id = ?",
        (user_id,)
    )

def is_vip(user_id: int) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    vip_until = user[5]
    if vip_until:
        try:
            if isinstance(vip_until, str):
                vip_until_dt = datetime.strptime(vip_until, '%Y-%m-%d %H:%M:%S')
            else:
                vip_until_dt = vip_until
            return datetime.now() < vip_until_dt
        except Exception as e:
            logger.error(f"Ошибка проверки VIP: {e}")
            return False
    return False

def add_vip_days(user_id: int, days: int):
    user = get_user(user_id)
    if user:
        current_vip = user[5]
        if current_vip:
            try:
                if isinstance(current_vip, str):
                    current_vip_dt = datetime.strptime(current_vip, '%Y-%m-%d %H:%M:%S')
                else:
                    current_vip_dt = current_vip
                if current_vip_dt > datetime.now():
                    new_date = current_vip_dt + timedelta(days=days)
                else:
                    new_date = datetime.now() + timedelta(days=days)
            except:
                new_date = datetime.now() + timedelta(days=days)
        else:
            new_date = datetime.now() + timedelta(days=days)
        db_exec(
            "UPDATE users SET vip_until = ? WHERE id = ?",
            (new_date.strftime('%Y-%m-%d %H:%M:%S'), user_id)
        )
        return True
    return False

def remove_vip(user_id: int):
    return db_exec(
        "UPDATE users SET vip_until = NULL WHERE id = ?",
        (user_id,)
    )

def create_confession(from_user: int, to_user: int, text: str):
    is_vip_sender_val = 1 if is_vip(from_user) else 0
    can_edit_until = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    if text is None:
        text = ""
    logger.info(f"Создание признания: от {from_user} к {to_user}, VIP: {is_vip_sender_val}, текст: {text[:50]}...")
    return db_exec(
        """INSERT INTO confessions (from_user, to_user, message_id, text, media_type, media_file_id, is_vip_sender, can_edit_until) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (from_user, to_user, None, text, None, None, is_vip_sender_val, can_edit_until)
    )

def get_confession(confession_id: int):
    return db_fetch_one("SELECT * FROM confessions WHERE id = ?", (confession_id,))

def get_confessions_by_user(user_id: int):
    return db_fetch("SELECT * FROM confessions WHERE from_user = ? OR to_user = ?", (user_id, user_id))

def delete_confession(confession_id: int):
    return db_exec("DELETE FROM confessions WHERE id = ?", (confession_id,))

def update_confession_message_id(confession_id: int, message_id: int):
    return db_exec(
        "UPDATE confessions SET message_id = ? WHERE id = ?",
        (message_id, confession_id)
    )

def update_reveal_status(confession_id: int, status: int):
    return db_exec(
        "UPDATE confessions SET reveal_status = ? WHERE id = ?",
        (status, confession_id)
    )

def create_report(confession_id: int, reporter_id: int):
    return db_exec(
        "INSERT INTO reports (confession_id, reporter_id) VALUES (?, ?)",
        (confession_id, reporter_id)
    )

def delete_report(report_id: int):
    return db_exec("DELETE FROM reports WHERE id = ?", (report_id,))

def create_promo_code(code: str, activations: int, vip_days: int, created_by: int, expires_at: str = None):
    return db_exec(
        """INSERT INTO promo_codes (code, activations, activations_left, vip_days, created_by, expires_at) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (code, activations, activations, vip_days, created_by, expires_at)
    )

def get_promo_codes():
    return db_fetch("SELECT * FROM promo_codes ORDER BY created_at DESC")

def delete_promo_code(code: str):
    return db_exec("DELETE FROM promo_codes WHERE code = ?", (code,))

def get_promo_code(code: str):
    # проверяем срок действия
    promo = db_fetch_one(
        "SELECT * FROM promo_codes WHERE code = ? AND activations_left > 0 AND (expires_at IS NULL OR expires_at > datetime('now'))",
        (code,)
    )
    return promo

def activate_promo_code(user_id: int, code: str):
    existing_activation = db_fetch_one(
        "SELECT id FROM promo_activations WHERE user_id = ? AND promo_code = ?",
        (user_id, code)
    )
    if existing_activation:
        return None
    promo = get_promo_code(code)
    if not promo:
        return None
    if promo[2] <= 0:
        return None
    db_exec(
        "UPDATE promo_codes SET activations_left = activations_left - 1 WHERE code = ?",
        (code,)
    )
    db_exec(
        "INSERT INTO promo_activations (user_id, promo_code) VALUES (?, ?)",
        (user_id, code)
    )
    return promo[3]  # vip_days

def get_promo_activations(code: str):
    return db_fetch("SELECT user_id, activated_at FROM promo_activations WHERE promo_code = ? ORDER BY activated_at DESC", (code,))

def get_user_stats(user_id: int):
    received = db_fetch_one(
        "SELECT COUNT(*) FROM confessions WHERE to_user = ?",
        (user_id,)
    )[0] or 0
    sent = db_fetch_one(
        "SELECT COUNT(*) FROM confessions WHERE from_user = ?",
        (user_id,)
    )[0] or 0
    reports = db_fetch_one(
        "SELECT COUNT(*) FROM reports WHERE reporter_id = ?",
        (user_id,)
    )[0] or 0
    return {
        'received': received,
        'sent': sent,
        'reports': reports
    }

def get_top_users(limit: int = 10):
    return db_fetch(
        """SELECT u.id, u.username, COUNT(c.id) as confession_count 
           FROM users u 
           LEFT JOIN confessions c ON u.id = c.to_user 
           WHERE u.banned = 0
           GROUP BY u.id 
           ORDER BY confession_count DESC 
           LIMIT ?""",
        (limit,)
    )

def get_all_users():
    return db_fetch("SELECT id FROM users WHERE banned = 0")

def get_vip_users():
    return db_fetch("SELECT id, username, vip_until FROM users WHERE vip_until > datetime('now')")

def get_active_users_count():
    result = db_fetch_one("SELECT COUNT(*) FROM users WHERE banned = 0")
    return result[0] if result else 0

def get_total_confessions_count():
    result = db_fetch_one("SELECT COUNT(*) FROM confessions")
    return result[0] if result else 0

def get_pending_reports_count():
    result = db_fetch_one("SELECT COUNT(*) FROM reports")
    return result[0] if result else 0

def get_banned_users():
    return db_fetch("SELECT id, username FROM users WHERE banned = 1")

def get_user_role(user_id: int):
    result = db_fetch_one("SELECT role FROM admin_roles WHERE user_id = ?", (user_id,))
    return result[0] if result else None

def add_admin_role(user_id: int, role: str, granted_by: int):
    existing = db_fetch_one("SELECT user_id FROM admin_roles WHERE user_id = ?", (user_id,))
    if existing:
        db_exec("UPDATE admin_roles SET role = ?, granted_by = ?, granted_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (role, granted_by, user_id))
    else:
        db_exec("INSERT INTO admin_roles (user_id, role, granted_by) VALUES (?, ?, ?)",
                (user_id, role, granted_by))
    db_exec("INSERT INTO admin_logs (admin_id, action, details) VALUES (?, ?, ?)",
            (granted_by, "add_role", f"Добавлена роль {role} пользователю {user_id}"))

def remove_admin_role(user_id: int, role: str, removed_by: int):
    db_exec("DELETE FROM admin_roles WHERE user_id = ? AND role = ?", (user_id, role))
    db_exec("INSERT INTO admin_logs (admin_id, action, details) VALUES (?, ?, ?)",
            (removed_by, "remove_role", f"Удалена роль {role} у пользователя {user_id}"))

def get_all_admins():
    return db_fetch("SELECT user_id, role FROM admin_roles")

def get_admin_settings(key: str = None):
    if key:
        result = db_fetch_one("SELECT value FROM admin_settings WHERE key = ?", (key,))
        return result[0] if result else None
    else:
        return db_fetch("SELECT key, value FROM admin_settings")

def set_admin_settings(key: str, value: str):
    db_exec("INSERT OR REPLACE INTO admin_settings (key, value) VALUES (?, ?)", (key, value))

def add_notification(user_id: int, type: str, message: str):
    db_exec("INSERT INTO notifications (user_id, type, message) VALUES (?, ?, ?)", (user_id, type, message))

def get_pending_notifications():
    return db_fetch("SELECT * FROM notifications WHERE sent = 0")

def mark_notification_sent(notification_id: int):
    db_exec("UPDATE notifications SET sent = 1 WHERE id = ?", (notification_id,))

def add_admin_log(admin_id: int, action: str, details: str):
    db_exec("INSERT INTO admin_logs (admin_id, action, details) VALUES (?, ?, ?)", (admin_id, action, details))

def get_admin_logs(limit: int = 50):
    return db_fetch("SELECT * FROM admin_logs ORDER BY created_at DESC LIMIT ?", (limit,))

# ===== НОВЫЕ ФУНКЦИИ =====

# --- Чёрный список ---
def add_blacklist_word(word: str):
    try:
        db_exec("INSERT INTO blacklist_words (word) VALUES (?)", (word.lower(),))
        return True
    except sqlite3.IntegrityError:
        return False

def remove_blacklist_word(word: str):
    db_exec("DELETE FROM blacklist_words WHERE word = ?", (word.lower(),))

def get_blacklist_words():
    rows = db_fetch("SELECT word FROM blacklist_words ORDER BY word")
    return [row[0] for row in rows]

def check_text_blacklist(text: str) -> bool:
    words = get_blacklist_words()
    text_lower = text.lower()
    for word in words:
        if word in text_lower:
            return True
    return False

# --- Warn система ---
def add_warn(user_id: int, admin_id: int, reason: str):
    db_exec("INSERT INTO warnings (user_id, admin_id, reason) VALUES (?, ?, ?)",
            (user_id, admin_id, reason))
    # Проверяем количество варнов
    count = db_fetch_one("SELECT COUNT(*) FROM warnings WHERE user_id = ?", (user_id,))[0]
    if count >= 3:
        ban_user(user_id, 0, "Автоматический бан за 3 предупреждения")
        return True  # означает, что пользователь забанен
    return False

def remove_warn(user_id: int, warn_id: int = None):
    if warn_id:
        db_exec("DELETE FROM warnings WHERE id = ?", (warn_id,))
    else:
        # удаляем последнее предупреждение
        warn = db_fetch_one("SELECT id FROM warnings WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
        if warn:
            db_exec("DELETE FROM warnings WHERE id = ?", (warn[0],))

def get_warns(user_id: int):
    return db_fetch("SELECT id, admin_id, reason, created_at FROM warnings WHERE user_id = ? ORDER BY created_at DESC", (user_id,))

# --- Техработы ---
def set_maintenance(enabled: bool, reason: str = "", until: str = ""):
    set_admin_settings("maintenance_enabled", "1" if enabled else "0")
    set_admin_settings("maintenance_reason", reason)
    set_admin_settings("maintenance_until", until)

def is_maintenance():
    return get_admin_settings("maintenance_enabled") == "1"

# --- Достижения ---
def create_achievement(name: str, description: str):
    return db_exec("INSERT INTO achievements (name, description) VALUES (?, ?)", (name, description))

def delete_achievement(achievement_id: int):
    db_exec("DELETE FROM achievements WHERE id = ?", (achievement_id,))
    db_exec("DELETE FROM user_achievements WHERE achievement_id = ?", (achievement_id,))

def get_all_achievements():
    return db_fetch("SELECT id, name, description FROM achievements ORDER BY id")

def get_achievement(achievement_id: int):
    return db_fetch_one("SELECT id, name, description FROM achievements WHERE id = ?", (achievement_id,))

def award_achievement(user_id: int, achievement_id: int):
    try:
        db_exec("INSERT INTO user_achievements (user_id, achievement_id) VALUES (?, ?)",
                (user_id, achievement_id))
        return True
    except sqlite3.IntegrityError:
        return False

def remove_achievement(user_id: int, achievement_id: int):
    db_exec("DELETE FROM user_achievements WHERE user_id = ? AND achievement_id = ?",
            (user_id, achievement_id))

def get_user_achievements(user_id: int):
    rows = db_fetch("""
        SELECT a.id, a.name, a.description, ua.awarded_at
        FROM user_achievements ua
        JOIN achievements a ON a.id = ua.achievement_id
        WHERE ua.user_id = ?
        ORDER BY ua.awarded_at
    """, (user_id,))
    return rows

def check_achievement_milestones(user_id: int):
    """Проверка на получение достижений за количество полученных признаний"""
    received = get_user_stats(user_id)['received']
    milestones = [10, 20, 50, 100, 500]
    for m in milestones:
        if received >= m:
            ach = db_fetch_one("SELECT id FROM achievements WHERE name = ?", (f"{m} признаний",))
            if ach:
                award_achievement(user_id, ach[0])

# ===== ИГРА "КТО Я?" =====
def create_whois_game(creator_id: int) -> int:
    """Создаёт новую игру в статусе waiting, возвращает ID игры"""
    return db_exec(
        "INSERT INTO whois_games (creator_id) VALUES (?)",
        (creator_id,)
    )

def get_whois_game(game_id: int):
    return db_fetch_one("SELECT * FROM whois_games WHERE id = ?", (game_id,))

def get_whois_game_by_creator(creator_id: int, status: str = None):
    query = "SELECT * FROM whois_games WHERE creator_id = ?"
    params = [creator_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT 1"
    return db_fetch_one(query, tuple(params))

def get_whois_game_by_opponent(opponent_id: int, status: str = None):
    query = "SELECT * FROM whois_games WHERE opponent_id = ?"
    params = [opponent_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT 1"
    return db_fetch_one(query, tuple(params))

def set_whois_opponent(game_id: int, opponent_id: int):
    """Устанавливает оппонента и переводит игру в active"""
    db_exec(
        "UPDATE whois_games SET opponent_id = ?, status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (opponent_id, game_id)
    )

def increment_questions_asked(game_id: int):
    db_exec(
        "UPDATE whois_games SET questions_asked = questions_asked + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (game_id,)
    )

def complete_whois_game(game_id: int, winner_id: int):
    """Завершает игру, фиксирует победителя"""
    db_exec(
        "UPDATE whois_games SET status = 'completed', winner_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (winner_id, game_id)
    )

def delete_whois_game(game_id: int):
    db_exec("DELETE FROM whois_games WHERE id = ?", (game_id,))

def is_whois_enabled() -> bool:
    """Проверяет, включён ли режим whois (хранится в admin_settings)"""
    return get_admin_settings("whois_enabled") == "1"

# ===== АНОНИМНЫЙ БАТЛ =====
def add_battle_participant(user_id: int) -> bool:
    """Добавляет пользователя в батл. Возвращает True, если добавлен, False если уже был."""
    try:
        db_exec("INSERT INTO battle_participants (user_id) VALUES (?)", (user_id,))
        return True
    except sqlite3.IntegrityError:
        return False

def remove_battle_participant(user_id: int):
    db_exec("DELETE FROM battle_participants WHERE user_id = ?", (user_id,))

def get_battle_participants():
    rows = db_fetch("SELECT user_id FROM battle_participants")
    return [row[0] for row in rows]

def clear_battle_participants():
    db_exec("DELETE FROM battle_participants")

def is_battle_enabled() -> bool:
    return get_admin_settings("battle_enabled") == "1"