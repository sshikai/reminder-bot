import os
import re
import time
import random
import sqlite3
import threading
import json
import datetime
import urllib.request
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

VK_TOKEN = os.environ.get("VK_TOKEN", "").strip()
CREATOR_ID = 479753606
LEADER_ID = 639963159

MSK_TZ = datetime.timezone(datetime.timedelta(hours=3))
def get_msk_now():
    return datetime.datetime.now(MSK_TZ)

DATA_DIR = "/app/data" if os.path.isdir("/app/data") else os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DATA_DIR, "bot.db")
CONN = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
CONN.row_factory = sqlite3.Row
DB_LOCK = threading.RLock()

VK = None
NAME_CACHE = {}
OWNER_CACHE = {}
MEMBER_SYNC_CACHE = {}

LEADER_BDAY_TEXT = (
    "Дорогой лидер Million Dollars🎉\n"
    "От лица всего состава поздравляю тебя с днем рождения!\n\n"
    "Спасибо за твой огромный вклад в развитие Million Dollars и за то, что собрал под одним крылом таких крутых ребят.\n\n"
    "Желаем тебе железобетонного терпения, преданных замов, огромного онлайна и чтобы никто не портил тебе настроение. "
    "Пусть наша семья гремит по всему серверу! 💰\n\n{mention}"
)
DEFAULT_BDAY_TEXT = "Поздравляем {mention}. У него сегодня день рождения!"

VALID_COMMANDS = [
    "команды", "админы", "участник", "ники", "ник", "парк", "прем", "чат",
    "пред", "-пред", "лимит_предов", "кд_предов", "старт_контроль", "стоп_контроль",
    "время_опросов", "защита", "-защита", "бан", "адмчат", "admg", "номер_чата",
    "текст_др", "создать", "список", "удалить", "редактировать", "включить", "отключить", "развернуть",
    "назначить", "снять", "голоса", "тишина", "тишина_офф", "проверка_опроса", "бр",
    "мут", "-мут", "мутлист", "предлист", "статус", "статусы", "проверка"
]

# ===== СИСТЕМА РОЛЕЙ =====
ROLE_NAMES = {0: "Участник", 1: "👮‍♂️ Модератор", 2: "🛡 Админ", 3: "🥷 Главный Админ", 4: "👑 Владелец"}

def get_user_role(peer, user_id):
    if user_id == CREATOR_ID or user_id == get_chat_owner(peer):
        return 4
    with DB_LOCK:
        row = CONN.execute("SELECT role FROM roles WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
        return row["role"] if row else 0

def set_user_role(peer, user_id, role):
    with DB_LOCK:
        CONN.execute("INSERT OR REPLACE INTO roles(user_id, peer_id, role) VALUES(?,?,?)", (user_id, peer, role))
        CONN.commit()

def get_users_with_min_role(peer, min_role):
    with DB_LOCK:
        return [int(r["user_id"]) for r in CONN.execute("SELECT user_id FROM roles WHERE peer_id=? AND role>=?", (peer, min_role)).fetchall()]

# ===== ИСТОРИЯ НАКАЗАНИЙ =====
def add_punishment(peer, user_id, p_type, reason, message_id, issued_by, duration_minutes=0):
    with DB_LOCK:
        CONN.execute("""INSERT INTO punishment_history 
                        (peer_id, user_id, type, reason, message_id, issued_by, issued_at, duration_minutes) 
                        VALUES(?,?,?,?,?,?,?,?)""",
                     (peer, user_id, p_type, reason, message_id or 0, issued_by, int(time.time()), duration_minutes))
        CONN.commit()
# ===== КОНЕЦ ИСТОРИИ =====

# ===== BLACK RUSSIA API =====
BR_API_URL = "https://api.blackrussia.online/servers.json"
BR_CACHE = {"time": 0.0, "data": None}
BR_PER_PAGE = 20
BR_COLOR_EMOJI = {
    "RED": "🟥", "GREEN": "🟩", "BLUE": "🟦", "YELLOW": "🟨",
    "ORANGE": "🟧", "PURPLE": "🟪", "VIOLET": "🟪", "BLACK": "⬛",
    "WHITE": "⬜", "PINK": "🌸", "CYAN": "🟦", "TURQUOISE": "🟦", "LIME": "🟩",
    "CHERRY": "🍒", "INDIGO": "🦋", "MAGENTA": "🎀", "CRIMSON": "🌺",
    "GOLD": "⭐️", "AZURE": "🧿", "PLATINUM": "💍", "AQUA": "🐟",
    "GRAY": "🐰", "GREY": "🐰", "ICE": "🧊",
}

def fetch_br_servers():
    now = time.time()
    if BR_CACHE["data"] is not None and (now - BR_CACHE["time"]) < 300:
        return BR_CACHE["data"]
    try:
        req = urllib.request.Request(BR_API_URL, headers={"User-Agent": "Mozilla/5.0 (MD BOT)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, list):
            BR_CACHE["time"] = now
            BR_CACHE["data"] = data
            return data
        return BR_CACHE["data"]
    except Exception as e:
        print("BR API error:", e)
        return BR_CACHE["data"]

def build_br_page(page):
    servers = fetch_br_servers()
    if not servers:
        return None, None, 1
    total = len(servers)
    total_pages = max(1, (total + BR_PER_PAGE - 1) // BR_PER_PAGE)
    try:
        page = int(page)
    except Exception:
        page = 1
    page = max(1, min(page, total_pages))
    total_online = 0
    total_max = 0
    for s in servers:
        try: total_online += int(s.get("online", 0) or 0)
        except Exception: pass
        try: total_max += int(s.get("maxonline", 0) or 0)
        except Exception: pass
    chunk = servers[(page - 1) * BR_PER_PAGE: page * BR_PER_PAGE]
    lines = [
        "📱 Общий онлайн проекта BlackRussia: {}".format(total_online),
        "🏆 Общий рекордный онлайн за день: {}\n".format(total_max),
    ]
    start_idx = (page - 1) * BR_PER_PAGE
    for i, s in enumerate(chunk, start_idx + 1):
        fname = str(s.get("firstname", "") or s.get("name", "")).strip()
        emoji = BR_COLOR_EMOJI.get(fname.upper(), "🎮")
        try: online = int(s.get("online", 0) or 0)
        except Exception: online = 0
        try: maxonline = int(s.get("maxonline", 0) or 0)
        except Exception: maxonline = 0
        lines.append("{}. {}{} - {} / {}.".format(i, emoji, fname, online, maxonline))
    buttons = []
    if page > 1:
        buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "br_prev", "page": page - 1})}, "color": "secondary"})
    buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
    if page < total_pages:
        buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "br_next", "page": page + 1})}, "color": "secondary"})
    keyboard_json = json.dumps({"inline": True, "buttons": [buttons]})
    return "\n".join(lines), keyboard_json, total_pages

def init_db():
    with DB_LOCK:
        CONN.execute("""CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, name TEXT, text TEXT,
            attachments TEXT, source_message_id INTEGER DEFAULT 0, interval_minutes INTEGER,
            repeat_count INTEGER DEFAULT 1, next_trigger REAL, enabled INTEGER DEFAULT 1, UNIQUE(peer_id, name))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS extra_admins (peer_id INTEGER, user_id INTEGER, UNIQUE(peer_id, user_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS settings (peer_id INTEGER, key TEXT, value TEXT, UNIQUE(peer_id, key))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS birthdays (user_id INTEGER, peer_id INTEGER, bdate TEXT, updated_at INTEGER, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS birthday_congratulated (user_id INTEGER, peer_id INTEGER, year INTEGER, congratulated_at INTEGER, PRIMARY KEY(user_id, peer_id, year))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER, peer_id INTEGER, nickname TEXT DEFAULT '', warnings INTEGER DEFAULT 0,
            warn_durations TEXT DEFAULT '', warn_expiry INTEGER DEFAULT 0, last_active TEXT DEFAULT '',
            streak INTEGER DEFAULT 0, poll_protected INTEGER DEFAULT 0, join_time INTEGER DEFAULT 0,
            last_vote_time INTEGER DEFAULT 0, last_vote_warn_time INTEGER DEFAULT 0, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS roles (
            user_id INTEGER, peer_id INTEGER, role INTEGER DEFAULT 0, UNIQUE(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, name TEXT, UNIQUE(peer_id, name))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS user_statuses (
            user_id INTEGER, peer_id INTEGER, status_id INTEGER, UNIQUE(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS punishment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peer_id INTEGER, user_id INTEGER, type TEXT, reason TEXT,
            message_id INTEGER DEFAULT 0, issued_by INTEGER, issued_at INTEGER,
            duration_minutes INTEGER DEFAULT 0)""")
        try:
            CONN.execute("ALTER TABLE poll_votes RENAME TO poll_votes_old")
        except Exception:
            pass
        CONN.execute("""CREATE TABLE IF NOT EXISTS poll_votes (
            vote_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, peer_id INTEGER, poll_time INTEGER, date TEXT)""")
        try:
            CONN.execute("INSERT INTO poll_votes (user_id, peer_id, poll_time, date) SELECT user_id, peer_id, 0, date FROM poll_votes_old")
            CONN.execute("DROP TABLE poll_votes_old")
        except Exception:
            pass
        CONN.execute("""CREATE TABLE IF NOT EXISTS info_blocks (peer_id INTEGER, key TEXT, text TEXT, PRIMARY KEY(peer_id, key))""")
        migrations = [
            "ALTER TABLE members ADD COLUMN warn_durations TEXT DEFAULT ''",
            "ALTER TABLE members ADD COLUMN last_vote_time INTEGER DEFAULT 0",
            "ALTER TABLE members ADD COLUMN last_vote_warn_time INTEGER DEFAULT 0",
            "ALTER TABLE members ADD COLUMN mute_until INTEGER DEFAULT 0",
            "ALTER TABLE members ADD COLUMN mute_reason TEXT DEFAULT ''",
            "ALTER TABLE members ADD COLUMN warn_reasons TEXT DEFAULT ''"
        ]
        for sql in migrations:
            try:
                CONN.execute(sql)
            except Exception:
                pass
        try:
            cols = [row[1] for row in CONN.execute("PRAGMA table_info(reminders)").fetchall()]
            if "attachments" not in cols: CONN.execute("ALTER TABLE reminders ADD COLUMN attachments TEXT")
            if "source_message_id" not in cols: CONN.execute("ALTER TABLE reminders ADD COLUMN source_message_id INTEGER DEFAULT 0")
            if "repeat_count" not in cols: CONN.execute("ALTER TABLE reminders ADD COLUMN repeat_count INTEGER DEFAULT 1")
        except Exception as e:
            print("migration error:", e)
        CONN.commit()

def get_setting(peer, key, default=""):
    with DB_LOCK:
        row = CONN.execute("SELECT value FROM settings WHERE peer_id=? AND key=?", (peer, key)).fetchone()
        return row["value"] if row else default

def set_setting(peer, key, value):
    with DB_LOCK:
        CONN.execute("INSERT OR REPLACE INTO settings(peer_id, key, value) VALUES(?,?,?)", (peer, key, value))
        CONN.commit()

def get_extra_admins(peer):
    with DB_LOCK:
        return [int(r["user_id"]) for r in CONN.execute("SELECT user_id FROM extra_admins WHERE peer_id=?", (peer,)).fetchall()]

def add_extra_admin(peer, user_id):
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO extra_admins(peer_id, user_id) VALUES(?,?)", (peer, user_id))
        CONN.commit()

def remove_extra_admin(peer, user_id):
    with DB_LOCK:
        CONN.execute("DELETE FROM extra_admins WHERE peer_id=? AND user_id=?", (peer, user_id))
        CONN.commit()

def get_chat_owner(peer):
    if VK is None or peer in OWNER_CACHE:
        return OWNER_CACHE.get(peer, 0)
    oid = 0
    try:
        r = VK.messages.getConversationsById(peer_ids=peer)
        items = r.get("items", [])
        if items:
            oid = items[0].get("conversation", {}).get("chat_settings", {}).get("owner_id", 0) or 0
            if oid == 0:
                oid = items[0].get("conversation", {}).get("owner_id", 0) or 0
    except Exception as e:
        print("owner method 1 error:", e)
    if oid == 0:
        try:
            members_resp = VK.messages.getConversationMembers(peer_id=peer)
            for item in members_resp.get("items", []):
                if item.get("is_owner"):
                    oid = int(item.get("member_id", 0))
                    break
            if oid == 0:
                for profile in members_resp.get("profiles", []):
                    if profile.get("is_owner"):
                        oid = int(profile.get("id", 0))
                        break
        except Exception as e:
            print("owner method 2 error:", e)
    OWNER_CACHE[peer] = oid
    return oid

def is_moderator(sender, peer):
    if sender <= 0: return False
    if sender == CREATOR_ID or sender == get_chat_owner(peer): return True
    return get_user_role(peer, sender) >= 1

def is_admin(sender, peer):
    if sender <= 0: return False
    if sender == CREATOR_ID or sender == get_chat_owner(peer): return True
    return get_user_role(peer, sender) >= 2

def is_main_admin(sender, peer):
    if sender <= 0: return False
    if sender == CREATOR_ID or sender == get_chat_owner(peer): return True
    return get_user_role(peer, sender) >= 3

def is_owner(sender, peer):
    return sender > 0 and (sender == CREATOR_ID or sender == get_chat_owner(peer))

def send_msg(peer, text, attachments=None, keyboard=None):
    if VK is None or not peer: return
    try:
        params = {'peer_id': peer, 'message': text, 'random_id': random.getrandbits(31)}
        if attachments: params['attachment'] = attachments
        if keyboard: params['keyboard'] = json.dumps(keyboard)
        VK.messages.send(**params)
    except Exception as e:
        print("send error:", e)

def get_user_name(user_id):
    if user_id in NAME_CACHE: return NAME_CACHE[user_id]
    name = "Пользователь"
    try:
        r = VK.users.get(user_ids=user_id)
        if r: name = "{} {}".format(r[0].get('first_name', ''), r[0].get('last_name', '')).strip() or "Пользователь"
    except: pass
    NAME_CACHE[user_id] = name
    return name

def mention(user_id): return "[id{}|{}]".format(user_id, get_user_name(user_id))

def extract_targets(text, reply_from):
    ids = []
    for m in re.finditer(r"\[id(\d+)\|", text, re.I): ids.append(int(m.group(1)))
    for m in re.finditer(r"[@\*]id(\d+)", text, re.I): ids.append(int(m.group(1)))
    for m in re.finditer(r"\b(\d{5,})\b", text): ids.append(int(m.group(1)))
    seen, result = set(), []
    for v in ids:
        if v not in seen: seen.add(v); result.append(v)
    if not result and reply_from and reply_from > 0: result = [reply_from]
    return result

def norm(s): return re.sub(r"\s+", " ", s.strip().lower().rstrip(".,;:!?")).strip()

def parse_reply_attachments(reply_obj):
    if not reply_obj or not isinstance(reply_obj, dict): return ""
    parts = []
    for att in reply_obj.get("attachments", []) or []:
        if att.get("type") == "photo":
            ph = att.get("photo", {})
            if ph.get("owner_id") and ph.get("id"): parts.append("photo{}_{}".format(ph['owner_id'], ph['id']))
    return ",".join(parts)

def sync_members(peer):
    now = time.time()
    if peer in MEMBER_SYNC_CACHE and (now - MEMBER_SYNC_CACHE[peer]) < 300:
        return
    try:
        members_resp = VK.messages.getConversationMembers(peer_id=peer)
        profiles = members_resp.get("profiles", [])
        today = get_msk_now().strftime("%Y-%m-%d")
        current_members = set()
        for profile in profiles:
            user_id = int(profile.get("id", 0))
            if user_id > 0: current_members.add(user_id)
        with DB_LOCK:
            for user_id in current_members:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id, last_active, streak) VALUES(?,?,?,?)", (user_id, peer, today, 0))
            all_db_members = CONN.execute("SELECT user_id FROM members WHERE peer_id=?", (peer,)).fetchall()
            for row in all_db_members:
                if row["user_id"] not in current_members:
                    CONN.execute("DELETE FROM members WHERE user_id=? AND peer_id=?", (row["user_id"], peer))
            CONN.commit()
        MEMBER_SYNC_CACHE[peer] = now
    except Exception as e:
        print("sync_members error:", e)

def sync_all_peers(peers_list):
    for peer in peers_list:
        sync_members(peer)
        time.sleep(1)

def update_member_activity(peer, user_id):
    today = get_msk_now().strftime("%Y-%m-%d")
    with DB_LOCK:
        row = CONN.execute("SELECT last_active, streak FROM members WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
        if row:
            last_active, streak = row["last_active"], row["streak"]
            if last_active != today:
                yesterday = (get_msk_now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                new_streak = streak + 1 if last_active == yesterday else 1
                CONN.execute("UPDATE members SET last_active=?, streak=? WHERE user_id=? AND peer_id=?", (today, new_streak, user_id, peer))
        else:
            CONN.execute("INSERT INTO members(user_id, peer_id, last_active, streak) VALUES(?,?,?,?)", (user_id, peer, today, 1))
        CONN.commit()

def get_streak_emoji(streak):
    if streak >= 30: return "👑"
    if streak >= 25: return "🤑"
    if streak >= 20: return "😈"
    if streak >= 15: return "🤠"
    if streak >= 10: return "😇"
    if streak >= 5: return "😎"
    return "🤓"

def check_birthdays(peer):
    now_msk = get_msk_now()
    today_str = now_msk.strftime("%Y-%m-%d")
    current_year = now_msk.year
    last_check = get_setting(peer, "last_bday_check_date", "")
    if last_check == today_str: return
    sync_members(peer)
    with DB_LOCK:
        rows = [dict(r) for r in CONN.execute("SELECT user_id, bdate FROM birthdays WHERE peer_id=? AND bdate IS NOT NULL", (peer,)).fetchall()]
    for r in rows:
        user_id, bdate = r["user_id"], r["bdate"]
        with DB_LOCK:
            member_row = CONN.execute("SELECT 1 FROM members WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
        if not member_row: continue
        parts = bdate.split(".")
        if len(parts) >= 2 and int(parts[0]) == now_msk.day and int(parts[1]) == now_msk.month:
            with DB_LOCK:
                row = CONN.execute("SELECT 1 FROM birthday_congratulated WHERE user_id=? AND peer_id=? AND year=?", (user_id, peer, current_year)).fetchone()
                if row: continue
            if user_id == LEADER_ID:
                text = LEADER_BDAY_TEXT.format(mention=mention(user_id))
            else:
                custom_row = CONN.execute("SELECT value FROM settings WHERE peer_id=? AND key='birthday_text'", (peer,)).fetchone()
                custom = custom_row["value"] if custom_row else None
                text = (custom.rstrip() + "\n\n" + mention(user_id)) if custom else DEFAULT_BDAY_TEXT.format(mention=mention(user_id))
            send_msg(peer, text)
            with DB_LOCK:
                CONN.execute("INSERT OR REPLACE INTO birthday_congratulated(user_id, peer_id, year, congratulated_at) VALUES(?,?,?,?)", (user_id, peer, current_year, int(time.time())))
                CONN.commit()
    set_setting(peer, "last_bday_check_date", today_str)


# ===== КНОПКИ =====
def get_help_main_buttons():
    return {
        "inline": True,
        "buttons": [
            [
                {"action": {"type": "callback", "label": "Общие", "payload": json.dumps({"cmd": "help_general"})}, "color": "primary"},
                {"action": {"type": "callback", "label": "Системы MD", "payload": json.dumps({"cmd": "help_systems"})}, "color": "negative"}
            ],
            [
                {"action": {"type": "callback", "label": "Управление", "payload": json.dumps({"cmd": "help_manage"})}, "color": "negative"},
                {"action": {"type": "callback", "label": "BLACK RUSSIA", "payload": json.dumps({"cmd": "help_br"})}, "color": "positive"}
            ]
        ]
    }

def get_help_systems_buttons():
    return {
        "inline": True,
        "buttons": [
            [
                {"action": {"type": "callback", "label": "Напоминалка", "payload": json.dumps({"cmd": "help_remind"})}, "color": "primary"},
                {"action": {"type": "callback", "label": "Опросы", "payload": json.dumps({"cmd": "help_polls"})}, "color": "primary"}
            ],
            [
                {"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_back"})}, "color": "secondary"}
            ]
        ]
    }

def get_help_manage_buttons():
    return {
        "inline": True,
        "buttons": [
            [
                {"action": {"type": "callback", "label": "Владелец", "payload": json.dumps({"cmd": "help_owner"})}, "color": "negative"},
                {"action": {"type": "callback", "label": "Главный Админ", "payload": json.dumps({"cmd": "help_main_admin"})}, "color": "negative"}
            ],
            [
                {"action": {"type": "callback", "label": "Администратор", "payload": json.dumps({"cmd": "help_admin"})}, "color": "negative"},
                {"action": {"type": "callback", "label": "Модератор", "payload": json.dumps({"cmd": "help_moderator"})}, "color": "negative"}
            ],
            [
                {"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_back"})}, "color": "secondary"}
            ]
        ]
    }

def get_help_back_button():
    """Назад на главную"""
    return {
        "inline": True,
        "buttons": [[{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_back"})}, "color": "secondary"}]]
    }

def get_help_back_to_manage():
    """Назад в меню Управление"""
    return {
        "inline": True,
        "buttons": [[{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_manage"})}, "color": "secondary"}]]
    }

def get_help_back_to_systems():
    """Назад в меню Системы MD"""
    return {
        "inline": True,
        "buttons": [[{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_systems"})}, "color": "secondary"}]]
    }

# ===== ТЕКСТЫ СПРАВКИ =====
HELP_GENERAL_TEXT = (
    "👥 Общие:\n"
    "1. Мд админы — список руководителей чата.\n"
    "2. Мд участник — твоя статистика.\n"
    "3. Мд ник — установить ник.\n"
    "4. Мд парк — информация об автопарке.\n"
    "5. Мд прем — информация о премиях и зарплатах.\n"
    "6. Мд чат — ссылка на чат для отчетов.\n"
    "7. Мд статусы — список статусов участников."
)

HELP_ADMIN_TEXT = (
    "🛡 Команды Администратора:\n"
    "1. Мд ник [@юз] <имя> — установить ник другому участнику.\n"
    "2. Мд номер чата — узнать ID текущего чата и создателя.\n"
    "3. Мд проверка [@юз] — история наказаний участника.\n"
    "4. Мд ники — список ников и предупреждений.\n"
    "5. Мд тишина — запретить писать всем, кроме админов.\n"
    "6. Мд тишина офф — разрешить писать всем.\n"
    "7. Мд назначить @игрок <номер ранга> — повышает участника.\n"
    "8. Мд снять @игрок — снимает роль в беседе.\n"
    "Имеет возможности прошлых ролей."
)

HELP_REMIND_TEXT = (
    "🔔 Напоминалка:\n"
    "1. Мд создать <название> <минуты> [количество] — создать напоминание (ответом на сообщение).\n"
    "2. Мд список — список всех напоминаний.\n"
    "3. Мд удалить <название или номер> — удалить напоминание.\n"
    "4. Мд редактировать <название или номер> <минуты> [кол-во] — изменить интервал.\n"
    "5. Мд отключить — отключить все напоминания.\n"
    "6. Мд отключить <название или номер> — отключить одно напоминание.\n"
    "7. Мд включить — включить все напоминания.\n"
    "8. Мд включить <название или номер> — включить одно напоминание.\n"
    "9. Мд развернуть <название или номер> — показать текст напоминания."
)

HELP_OWNER_TEXT = (
    "👑 Команды владельца:\n"
    "1. Мд адмчат <id> — установить чат для отчетов о банах.\n"
    "2. Мд адмчат удалить — отвязать чат для отчетов о банах.\n"
    "3. Мд лимит предов <число> — макс. количество предов до кика (по умолч. 3).\n"
    "4. Мд кд предов <дней> — изменить срок дефолтного преда.\n"
    "5. Мд текст др — установить текст поздравления с ДР (ответом на сообщение).\n"
    "6. Мд назначить @игрок <номер ранга> — повышает участника.\n"
    "7. Мд снять @игрок — снимает роль в беседе.\n"
    "Имеет возможности прошлых ролей."
)

HELP_POLLS_TEXT = (
    "📢 Система опросов:\n\n"
    "🛡️Админские👇\n"
    "1. Мд голоса — посмотреть, кто проголосовал сегодня.\n"
    "2. Мд голоса вчера — посмотреть голоса за вчера.\n"
    "3. Мд защита [@юз] — добавить защиту от опросов.\n"
    "4. Мд -защита [@юз] — убрать защиту от опросов.\n\n"
    "🤴Владельца👇\n"
    "1. Мд старт контроль — включить систему опросов и контроля.\n"
    "2. Мд стоп контроль — выключить систему опросов.\n"
    "3. Мд время опросов <ЧЧ:ММ> <ЧЧ:ММ> — изменить время опросов.\n"
    "4. Мд проверка опроса <ЧЧ:ММ> — изменить время проверки опроса."
)

HELP_BR_TEXT = (
    "🎮 BLACK RUSSIA:\n"
    "1. Мд бр — список всех серверов BlackRussia и их онлайн."
)

HELP_MODERATOR_TEXT = (
    "👮‍♂️ Команды Модератора:\n"
    "1. Мд пред [@юз] причина — выдать пред.\n"
    "2. Мд пред <дней> [@юз] причина — выдать пред на N дней.\n"
    "3. Мд пред навсегда [@юз] причина — выдать вечный пред.\n"
    "4. Мд -пред [@юз] — снять предупреждение.\n"
    "5. Мд бан [@юз] — забанить участника.\n"
    "6. Мд мут [@юз] <минуты> причина — выдать мут.\n"
    "7. Мд -мут [@юз] — снять мут.\n"
    "8. Мд участник [@юз] — посмотреть статистику участника.\n"
    "9. Мд мутлист — список замученных.\n"
    "10. Мд предлист — список предупреждений.\n"
    "При указании причины: с ответом на сообщение — не обязательна, без ответа — обязательна."
)

HELP_MAIN_ADMIN_TEXT = (
    "🥷 Команды Главного Админа:\n"
    "1. Мд статус @игрок <номер статуса> — назначает статус.\n"
    "2. Мд статус создать <название> — создать статус.\n"
    "3. Мд статус удалить <номер статуса> — удалить статус.\n"
    "4. Мд статус редактировать <номер статуса> <новое название> — переименовать.\n"
    "5. Мд статус снять @игрок — убрать статус.\n"
    "Имеет возможности прошлых ролей."
)


def handle_event(event):
    try:
        obj = event.object if hasattr(event, 'object') else event.obj
        if not isinstance(obj, dict): return
        event_id = obj.get("event_id")
        user_id = int(obj.get("user_id", 0))
        peer_id = int(obj.get("peer_id", 0))
        payload = obj.get("payload", "{}")
        if isinstance(payload, str):
            try: payload = json.loads(payload)
            except: payload = {}
        cmd = payload.get("cmd", "")

        if cmd == "poll_vote":
            now_ts = int(time.time())
            today_str = get_msk_now().strftime("%Y-%m-%d")
            payload_time = payload.get("time", 0)
            if payload_time > 0 and (now_ts - payload_time) > 600:
                VK.messages.sendMessageEventAnswer(
                    event_id=event_id, user_id=user_id, peer_id=peer_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "⏰ Время голосования вышло!"})
                )
                return
            try:
                with DB_LOCK:
                    existing_vote = CONN.execute("SELECT 1 FROM poll_votes WHERE user_id=? AND peer_id=? AND poll_time=?", (user_id, peer_id, payload_time)).fetchone()
                    if existing_vote:
                        VK.messages.sendMessageEventAnswer(
                            event_id=event_id, user_id=user_id, peer_id=peer_id,
                            event_data=json.dumps({"type": "show_snackbar", "text": "⚠️ Вы уже голосовали в этом опросе!"})
                        )
                    else:
                        mem_row = CONN.execute("SELECT last_vote_time FROM members WHERE user_id=? AND peer_id=?", (user_id, peer_id)).fetchone()
                        last_vote = mem_row["last_vote_time"] if mem_row and mem_row["last_vote_time"] else 0
                        if (now_ts - last_vote) < 3600:
                            remaining_mins = (3600 - (now_ts - last_vote)) // 60
                            VK.messages.sendMessageEventAnswer(
                                event_id=event_id, user_id=user_id, peer_id=peer_id,
                                event_data=json.dumps({"type": "show_snackbar", "text": "⏳ КД на голосование: осталось {}м".format(remaining_mins)})
                            )
                        else:
                            CONN.execute("INSERT INTO poll_votes(user_id, peer_id, poll_time, date) VALUES(?,?,?,?)", (user_id, peer_id, payload_time, today_str))
                            CONN.execute("UPDATE members SET last_vote_time=? WHERE user_id=? AND peer_id=?", (now_ts, user_id, peer_id))
                            CONN.commit()
                            send_msg(peer_id, "✅ {} Зайдет на этот кд!".format(mention(user_id)))
                            VK.messages.sendMessageEventAnswer(
                                event_id=event_id, user_id=user_id, peer_id=peer_id,
                                event_data=json.dumps({"type": "show_snackbar", "text": "✅ Ты отметился!"})
                            )
            except Exception as e:
                print("DB error in poll_vote: {}".format(e))
            return

        if cmd == "page_info":
            page = payload.get("page", 1)
            total = payload.get("total", 1)
            VK.messages.sendMessageEventAnswer(
                event_id=event_id, user_id=user_id, peer_id=peer_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "📄 Страница {} из {}".format(page, total)})
            )
            return

        if cmd in ["niki_prev", "niki_next"]:
            if not is_admin(user_id, peer_id):
                try:
                    VK.messages.sendMessageEventAnswer(
                        event_id=event_id, user_id=user_id, peer_id=peer_id,
                        event_data=json.dumps({"type": "show_snackbar", "text": "🚫 Только для админов"})
                    )
                except: pass
                return
            page = int(payload.get("page", 1))
            with DB_LOCK:
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=?", (peer_id,)).fetchone()[0]
                rows = CONN.execute("SELECT user_id, nickname, warnings, warn_durations FROM members WHERE peer_id=? ORDER BY user_id LIMIT 40 OFFSET ?", (peer_id, (page - 1) * 40)).fetchall()
            per_page = 40
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = max(1, min(page, total_pages))
            user_ids = [r["user_id"] for r in rows]
            try:
                users_data = VK.users.get(user_ids=",".join(map(str, user_ids)))
                for u in users_data:
                    NAME_CACHE[u["id"]] = "{} {}".format(u.get('first_name', ''), u.get('last_name', '')).strip() or "Пользователь"
            except Exception as e:
                print("Batch name fetch error:", e)
            lines = ["📝 Ники пользователей чата (страница {} из {}):\n".format(page, total_pages)]
            max_warns = int(get_setting(peer_id, "max_warns", "3") or "3")
            for idx, r in enumerate(rows, (page - 1) * per_page + 1):
                name = get_user_name(r["user_id"])
                nick = r["nickname"] or "Не установлен"
                warns = r["warnings"] or 0
                durations = r["warn_durations"] or "0"
                warn_icon = "⚠️" if warns > 0 else "✅"
                lines.append('{}. {} - "{}" ({}/{}) ({} дн.) {}'.format(idx, name, nick, warns, max_warns, durations, warn_icon))
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "niki_prev", "page": page - 1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "niki_next", "page": page + 1})}, "color": "secondary"})
            keyboard_json = json.dumps({"inline": True, "buttons": [buttons]})
            conversation_message_id = obj.get("conversation_message_id")
            if conversation_message_id:
                try:
                    VK.messages.edit(peer_id=peer_id, conversation_message_id=conversation_message_id, message="\n".join(lines), keyboard=keyboard_json)
                except Exception as e:
                    print("Edit error: {}".format(e))
                    VK.messages.send(peer_id=peer_id, message="\n".join(lines), keyboard=keyboard_json, random_id=random.getrandbits(31))
            else:
                VK.messages.send(peer_id=peer_id, message="\n".join(lines), keyboard=keyboard_json, random_id=random.getrandbits(31))
            try:
                VK.messages.sendMessageEventAnswer(
                    event_id=event_id, user_id=user_id, peer_id=peer_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "📄 Страница {}".format(page)})
                )
            except: pass
            return

        if cmd in ["br_prev", "br_next"]:
            page = int(payload.get("page", 1))
            text, keyboard_json, total_pages = build_br_page(page)
            if text is None:
                try:
                    VK.messages.sendMessageEventAnswer(
                        event_id=event_id, user_id=user_id, peer_id=peer_id,
                        event_data=json.dumps({"type": "show_snackbar", "text": "❌ Не удалось получить данные"})
                    )
                except: pass
                return
            conversation_message_id = obj.get("conversation_message_id")
            if conversation_message_id:
                try:
                    VK.messages.edit(peer_id=peer_id, conversation_message_id=conversation_message_id, message=text, keyboard=keyboard_json)
                except Exception as e:
                    print("BR edit error: {}".format(e))
                    VK.messages.send(peer_id=peer_id, message=text, keyboard=keyboard_json, random_id=random.getrandbits(31))
            else:
                VK.messages.send(peer_id=peer_id, message=text, keyboard=keyboard_json, random_id=random.getrandbits(31))
            try:
                VK.messages.sendMessageEventAnswer(
                    event_id=event_id, user_id=user_id, peer_id=peer_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "📄 Страница {}".format(page)})
                )
            except: pass
            return

        if cmd in ["status_prev", "status_next"]:
            page = int(payload.get("page", 1))
            text, keyboard_json, total_pages = build_status_page(peer_id, page)
            if text is None:
                try:
                    VK.messages.sendMessageEventAnswer(
                        event_id=event_id, user_id=user_id, peer_id=peer_id,
                        event_data=json.dumps({"type": "show_snackbar", "text": "❌ Статусов нет"})
                    )
                except: pass
                return
            conversation_message_id = obj.get("conversation_message_id")
            if conversation_message_id:
                try:
                    VK.messages.edit(peer_id=peer_id, conversation_message_id=conversation_message_id, message=text, keyboard=keyboard_json)
                except Exception as e:
                    print("Status edit error: {}".format(e))
                    VK.messages.send(peer_id=peer_id, message=text, keyboard=keyboard_json, random_id=random.getrandbits(31))
            else:
                VK.messages.send(peer_id=peer_id, message=text, keyboard=keyboard_json, random_id=random.getrandbits(31))
            try:
                VK.messages.sendMessageEventAnswer(
                    event_id=event_id, user_id=user_id, peer_id=peer_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "📄 Страница {}".format(page)})
                )
            except: pass
            return

        if cmd in ["help_general", "help_systems", "help_manage", "help_remind", "help_polls",
                   "help_admin", "help_moderator", "help_main_admin", "help_owner", "help_br", "help_back"]:
            # Проверка прав доступа к разделам
            if cmd == "help_systems":
                if not is_admin(user_id, peer_id):
                    try:
                        VK.messages.sendMessageEventAnswer(
                            event_id=event_id, user_id=user_id, peer_id=peer_id,
                            event_data=json.dumps({"type": "show_snackbar", "text": "У вас нет прав⛔️"})
                        )
                    except: pass
                    return
            elif cmd in ["help_manage", "help_moderator"]:
                if not is_moderator(user_id, peer_id):
                    try:
                        VK.messages.sendMessageEventAnswer(
                            event_id=event_id, user_id=user_id, peer_id=peer_id,
                            event_data=json.dumps({"type": "show_snackbar", "text": "У вас нет прав⛔️"})
                        )
                    except: pass
                    return
            elif cmd == "help_admin":
                if not is_admin(user_id, peer_id):
                    try:
                        VK.messages.sendMessageEventAnswer(
                            event_id=event_id, user_id=user_id, peer_id=peer_id,
                            event_data=json.dumps({"type": "show_snackbar", "text": "У вас нет прав⛔️"})
                        )
                    except: pass
                    return
            elif cmd == "help_main_admin":
                if not is_main_admin(user_id, peer_id):
                    try:
                        VK.messages.sendMessageEventAnswer(
                            event_id=event_id, user_id=user_id, peer_id=peer_id,
                            event_data=json.dumps({"type": "show_snackbar", "text": "У вас нет прав⛔️"})
                        )
                    except: pass
                    return
            elif cmd == "help_owner":
                if not is_owner(user_id, peer_id):
                    try:
                        VK.messages.sendMessageEventAnswer(
                            event_id=event_id, user_id=user_id, peer_id=peer_id,
                            event_data=json.dumps({"type": "show_snackbar", "text": "У вас нет прав⛔️"})
                        )
                    except: pass
                    return
            elif cmd in ["help_remind", "help_polls"]:
                if not is_admin(user_id, peer_id):
                    try:
                        VK.messages.sendMessageEventAnswer(
                            event_id=event_id, user_id=user_id, peer_id=peer_id,
                            event_data=json.dumps({"type": "show_snackbar", "text": "У вас нет прав⛔️"})
                        )
                    except: pass
                    return

            conversation_message_id = obj.get("conversation_message_id")
            if cmd == "help_back":
                message_text = "📖 Команды MD BOT"
                keyboard_json = json.dumps(get_help_main_buttons())
            elif cmd == "help_general":
                message_text = HELP_GENERAL_TEXT
                keyboard_json = json.dumps(get_help_back_button())
            elif cmd == "help_systems":
                message_text = "⚙️ Системы MD:\nВыберите раздел:"
                keyboard_json = json.dumps(get_help_systems_buttons())
            elif cmd == "help_manage":
                message_text = "🎛 Управление:\nВыберите роль:"
                keyboard_json = json.dumps(get_help_manage_buttons())
            elif cmd == "help_remind":
                message_text = HELP_REMIND_TEXT
                keyboard_json = json.dumps(get_help_back_to_systems())
            elif cmd == "help_polls":
                message_text = HELP_POLLS_TEXT
                keyboard_json = json.dumps(get_help_back_to_systems())
            elif cmd == "help_admin":
                message_text = HELP_ADMIN_TEXT
                keyboard_json = json.dumps(get_help_back_to_manage())
            elif cmd == "help_moderator":
                message_text = HELP_MODERATOR_TEXT
                keyboard_json = json.dumps(get_help_back_to_manage())
            elif cmd == "help_main_admin":
                message_text = HELP_MAIN_ADMIN_TEXT
                keyboard_json = json.dumps(get_help_back_to_manage())
            elif cmd == "help_owner":
                message_text = HELP_OWNER_TEXT
                keyboard_json = json.dumps(get_help_back_to_manage())
            elif cmd == "help_br":
                message_text = HELP_BR_TEXT
                keyboard_json = json.dumps(get_help_back_button())
            else:
                return
            if conversation_message_id:
                try:
                    VK.messages.edit(peer_id=peer_id, conversation_message_id=conversation_message_id, message=message_text, keyboard=keyboard_json)
                except Exception as e:
                    print("Help edit error: {}".format(e))
                    VK.messages.send(peer_id=peer_id, message=message_text, keyboard=keyboard_json, random_id=random.getrandbits(31))
            else:
                VK.messages.send(peer_id=peer_id, message=message_text, keyboard=keyboard_json, random_id=random.getrandbits(31))
            try:
                VK.messages.sendMessageEventAnswer(
                    event_id=event_id, user_id=user_id, peer_id=peer_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "✅ Выполнено"})
                )
            except: pass
            return
    except Exception as e:
        print("event error:", e)


# ===== ПАГИНАЦИЯ СТАТУСОВ =====
STATUS_PER_PAGE = 10

def build_status_page(peer, page):
    with DB_LOCK:
        statuses = CONN.execute("SELECT id, name FROM statuses WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
    if not statuses:
        return None, None, 1
    total = len(statuses)
    total_pages = max(1, (total + STATUS_PER_PAGE - 1) // STATUS_PER_PAGE)
    try:
        page = int(page)
    except Exception:
        page = 1
    page = max(1, min(page, total_pages))
    chunk = statuses[(page - 1) * STATUS_PER_PAGE: page * STATUS_PER_PAGE]
    lines = ["📋 Статусы (страница {} из {}):\n".format(page, total_pages)]
    for idx, s in enumerate(chunk, (page - 1) * STATUS_PER_PAGE + 1):
        with DB_LOCK:
            users = CONN.execute("SELECT user_id FROM user_statuses WHERE status_id=? AND peer_id=?", (s["id"], peer)).fetchall()
        user_mentions = [mention(u["user_id"]) for u in users]
        if user_mentions:
            lines.append("{} {}\n{}".format(idx, s["name"], "\n".join(user_mentions)))
        else:
            lines.append("{} {}\n(пусто)".format(idx, s["name"]))
        lines.append("")
    buttons = []
    if page > 1:
        buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "status_prev", "page": page - 1})}, "color": "secondary"})
    buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
    if page < total_pages:
        buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "status_next", "page": page + 1})}, "color": "secondary"})
    keyboard_json = json.dumps({"inline": True, "buttons": [buttons]})
    return "\n".join(lines), keyboard_json, total_pages


def handle_message(peer, sender, text, msg_obj):
    clean_text = text.strip()

    if clean_text.lower() in ["!!чаты", "!!тест"]:
        if int(sender) != CREATOR_ID: return
        send_msg(CREATOR_ID, "⏳ Загрузка списка бесед...")
        with DB_LOCK:
            peers_members = [row["peer_id"] for row in CONN.execute("SELECT DISTINCT peer_id FROM members").fetchall()]
            peers_reminders = [row["peer_id"] for row in CONN.execute("SELECT DISTINCT peer_id FROM reminders").fetchall()]
            peers = list(set(peers_members + peers_reminders))
        if not peers:
            send_msg(CREATOR_ID, "📭 Бот пока не зафиксировал ни одной беседы.")
        else:
            lines = ["📊 Список бесед с ботом:\n"]
            for i in range(0, len(peers), 100):
                chunk = peers[i:i+100]
                try:
                    convos = VK.messages.getConversationsById(peer_ids=chunk)
                    for item in convos.get("items", []):
                        p_id = item.get("peer", {}).get("id", 0)
                        title = item.get("chat_settings", {}).get("title", "Недоступно")
                        owner = item.get("chat_settings", {}).get("owner_id", 0)
                        owner_name = get_user_name(owner) if owner > 0 else "Нет/ЛС"
                        lines.append("• ID: {} | Название: {} | Владелец: {} ({})".format(p_id, title, owner_name, owner))
                except Exception as e:
                    lines.append("• Ошибка: {}".format(e))
            msg_text = "\n".join(lines)
            if len(msg_text) > 4000:
                for i in range(0, len(msg_text), 4000):
                    send_msg(CREATOR_ID, msg_text[i:i+4000])
            else:
                send_msg(CREATOR_ID, msg_text)
        return

    if peer < 2000000000: return

    action = msg_obj.get("action", {})
    if action.get("type") == "chat_invite_user":
        user_id = action.get("member_id")
        if not user_id: return
        with DB_LOCK:
            row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
            if row:
                CONN.execute("UPDATE members SET join_time=?, warnings=0, warn_durations='', warn_expiry=0 WHERE user_id=? AND peer_id=?", (int(time.time()), user_id, peer))
            else:
                CONN.execute("INSERT INTO members(user_id, peer_id, join_time, warnings, warn_durations, warn_expiry) VALUES(?,?,?,0,'',0)", (user_id, peer, int(time.time())))
            CONN.commit()
        if get_setting(peer, "control_active") == "1":
            send_msg(peer, "Добро пожаловать, {}! 🎉\nПожалуйста, установи свой ник с помощью команды:\n`Мд ник <твой_ник>`".format(mention(user_id)))
        return

    if action.get("type") == "chat_kick_user":
        user_id = action.get("member_id")
        if user_id:
            with DB_LOCK:
                nick_row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
            nick = nick_row["nickname"] if nick_row and nick_row["nickname"] else mention(user_id)
            with DB_LOCK:
                CONN.execute("DELETE FROM members WHERE user_id=? AND peer_id=?", (user_id, peer))
                CONN.commit()
            print("User {} kicked from peer {}, removed from DB".format(user_id, peer))
            admin_chat_raw = get_setting(peer, "admin_report_chat", "")
            admin_chat_clean = "".join(filter(str.isdigit, str(admin_chat_raw)))
            if len(admin_chat_clean) >= 9:
                report_peer = int(admin_chat_clean)
                chat_name = "Неизвестная беседа"
                try:
                    conv = VK.messages.getConversationsById(peer_ids=peer)
                    if conv.get("items"):
                        chat_name = conv["items"][0].get("chat_settings", {}).get("title", "Неизвестная беседа")
                except: pass
                report_text = (
                    "🚨 **ПРИВЕТСТВУЮ, АДМИНИСТРАТОРЫ!** 😀\n\n"
                    "Игрок {} ({}) был исключен из беседы '{}'.\n"
                    "Прошу принять меры и исключить его из семьи в игре. 👊"
                ).format(mention(user_id), nick, chat_name)
                try:
                    send_msg(report_peer, report_text)
                except Exception as e:
                    print("Error sending kick report to {}: {}".format(report_peer, e))
            return

    # ПРОВЕРКА МУТА (до всех команд)
    with DB_LOCK:
        mute_row = CONN.execute("SELECT mute_until FROM members WHERE user_id=? AND peer_id=?", (sender, peer)).fetchone()
    if mute_row and mute_row["mute_until"] and mute_row["mute_until"] > time.time():
        try:
            conv_msg_id = msg_obj.get("conversation_message_id")
            if conv_msg_id:
                VK.messages.delete(peer_id=peer, conversation_message_ids=[conv_msg_id], delete_for_all=1)
        except Exception as e:
            print("Mute delete error:", e)
        return

    if get_setting(peer, "silence_mode", "0") == "1":
        if not is_admin(sender, peer):
            try:
                conv_msg_id = msg_obj.get("conversation_message_id")
                if conv_msg_id:
                    VK.messages.delete(peer_id=peer, conversation_message_ids=[conv_msg_id], delete_for_all=1)
            except Exception as e:
                print("Silence delete error:", e)
            return

    update_member_activity(peer, sender)

    # Берём оригинальную строку для аргументов (чтобы сохранить регистр)
    first_line = text.split("\n")[0].strip()
    first = norm(first_line)
    if not first.startswith("мд "): return

    # Нормализованные части (для поиска команды)
    parts_norm = first[3:].strip().split()
    if not parts_norm:
        send_msg(peer, "Меня кто то звал?🧐 «Мд команды» список команд.")
        return

    # Оригинальные части (для аргументов с сохранением регистра)
    parts_orig = first_line[3:].strip().split()

    found_cmd = None
    found_args_norm = []
    found_idx = -1
    for i in range(len(parts_norm), 0, -1):
        candidate = "_".join(parts_norm[:i]).lower()
        if candidate in VALID_COMMANDS:
            found_cmd = candidate
            found_args_norm = parts_norm[i:]
            found_idx = i
            break
    if not found_cmd:
        found_cmd = parts_norm[0].lower()
        found_args_norm = parts_norm[1:]
        found_idx = 1

    cmd = found_cmd
    # Оригинальные аргументы берём из parts_orig по найденному индексу
    args = parts_orig[found_idx:] if found_idx <= len(parts_orig) else []

    if cmd not in VALID_COMMANDS:
        send_msg(peer, "Меня кто то звал?🧐 «Мд команды» список команд.")
        return

    owner = is_owner(sender, peer)
    admin = is_admin(sender, peer)
    moderator = is_moderator(sender, peer)
    main_admin = is_main_admin(sender, peer)
    sender_role = get_user_role(peer, sender)

    # Информация о reply для мут/пред
    reply_obj = msg_obj.get("reply_message", {}) or {}
    has_reply = bool(reply_obj and isinstance(reply_obj, dict) and reply_obj.get("from_id"))
    reply_msg_id = reply_obj.get("conversation_message_id", 0) if has_reply else 0

    if cmd == "команды":
        send_msg(peer, "📖 Команды MD BOT", keyboard=get_help_main_buttons())

    elif cmd == "админы":
        chat_owner_id = get_chat_owner(peer)
        lines = ["👥 Администраторы:\n"]
        if chat_owner_id:
            lines.append("👑 Владелец: {}".format(mention(chat_owner_id)))
        else:
            lines.append("👑 Владелец: не определён")
        with DB_LOCK:
            main_admins = [r["user_id"] for r in CONN.execute("SELECT user_id FROM roles WHERE peer_id=? AND role=3", (peer,)).fetchall()]
            admins_list = [r["user_id"] for r in CONN.execute("SELECT user_id FROM roles WHERE peer_id=? AND role=2", (peer,)).fetchall()]
            moderators_list = [r["user_id"] for r in CONN.execute("SELECT user_id FROM roles WHERE peer_id=? AND role=1", (peer,)).fetchall()]
        lines.append("🥷 Главные Админы(3): {}".format(", ".join(mention(u) for u in main_admins) if main_admins else "отсутствуют"))
        lines.append("🛡 Админы(2): {}".format(", ".join(mention(u) for u in admins_list) if admins_list else "отсутствуют"))
        lines.append("👮‍♂️ Модераторы(1): {}".format(", ".join(mention(u) for u in moderators_list) if moderators_list else "отсутствуют"))
        lines.append("👑 chatbot creator: Саша Майер")
        send_msg(peer, "\n".join(lines))

    elif cmd == "участник":
        target_id = sender
        if moderator and args:
            targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
            if targets: target_id = targets[0]
        with DB_LOCK:
            row = CONN.execute("SELECT nickname, warnings, warn_durations, warn_expiry, streak FROM members WHERE user_id=? AND peer_id=?", (target_id, peer)).fetchone()
        if not row:
            send_msg(peer, "ℹ️ Участник {} еще не проявлял активность в системе.".format(mention(target_id)))
            return
        nick = row["nickname"] or "Не установлен"
        warns = row["warnings"] or 0
        durations = row["warn_durations"] or "0"
        max_warns = int(get_setting(peer, "max_warns", "3") or "3")
        if row["warn_expiry"] > 0 and warns > 0:
            days_left = max(0, int((row["warn_expiry"] - time.time()) // 86400))
            days_str = "∞" if days_left > 365 else str(days_left)
        else:
            days_str = "0"
        streak = row["streak"] or 0
        emoji = get_streak_emoji(streak)
        role = get_user_role(peer, target_id)
        role_str = ROLE_NAMES.get(role, "Участник")
        msg = (
            "👥 Участник {}:\n"
            "🎮 Ник: {}\n"
            "⚠️ Предупреждений: {}/{} ({} дн.)\n"
            "🙆‍♂️Роль: {}\n"
            "🔥 Серия посещения: {} дн. {}"
        ).format(mention(target_id), nick, warns, max_warns, durations, role_str, streak, emoji)
        send_msg(peer, msg)

    elif cmd == "ники":
        try:
            if not admin:
                send_msg(peer, "⛔ Только администраторы могут смотреть полный список.")
                return
            send_msg(peer, "⏳ Загрузка списка участников...")
            threading.Thread(target=sync_members, args=(peer,), daemon=True).start()
            page = int(args[0]) if args and args[0].isdigit() else 1
            with DB_LOCK:
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=?", (peer,)).fetchone()[0]
                rows = CONN.execute("SELECT user_id, nickname, warnings, warn_durations FROM members WHERE peer_id=? ORDER BY user_id LIMIT 40 OFFSET ?", (peer, (page - 1) * 40)).fetchall()
            if not rows:
                send_msg(peer, "📝 Список участников пуст. Попробуйте через минуту, если чат большой.")
                return
            user_ids = [r["user_id"] for r in rows]
            try:
                users_data = VK.users.get(user_ids=",".join(map(str, user_ids)))
                for u in users_data:
                    NAME_CACHE[u["id"]] = "{} {}".format(u.get('first_name', ''), u.get('last_name', '')).strip() or "Пользователь"
            except Exception as e:
                print("Batch name fetch error:", e)
            per_page = 40
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = max(1, min(page, total_pages))
            lines = ["📝 Ники пользователей чата (страница {} из {}):\n".format(page, total_pages)]
            max_warns = int(get_setting(peer, "max_warns", "3") or "3")
            for idx, r in enumerate(rows, (page - 1) * per_page + 1):
                name = get_user_name(r["user_id"])
                nick = r["nickname"] or "Не установлен"
                warns = r["warnings"] or 0
                durations = r["warn_durations"] or "0"
                warn_icon = "⚠️" if warns > 0 else "✅"
                lines.append('{}. {} - "{}" ({}/{}) ({} дн.) {}'.format(idx, name, nick, warns, max_warns, durations, warn_icon))
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "niki_prev", "page": page - 1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "niki_next", "page": page + 1})}, "color": "secondary"})
            keyboard_json = json.dumps({"inline": True, "buttons": [buttons]})
            VK.messages.send(peer_id=peer, message="\n".join(lines), keyboard=keyboard_json, random_id=random.getrandbits(31))
        except Exception as e:
            print("НИКИ ERROR:", e)
            send_msg(peer, "❌ Произошла ошибка при выполнении команды 'Мд ники': {}".format(e))

    elif cmd == "ник":
        if not args:
            send_msg(peer, "❌ Формат: `Мд ник <ваш_ник>` или `Мд ник @юзер <ник>`")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if targets and admin:
            target_id = targets[0]
            nick_args = []
            for arg in args:
                if not re.match(r"^\[id\d+\|", arg) and not re.match(r"^@id\d+", arg) and not re.match(r"^\d{5,}$", arg):
                    nick_args.append(arg)
            if not nick_args:
                send_msg(peer, "❌ Укажите новый ник: `Мд ник @юзер <ник>`")
                return
            new_nick = " ".join(nick_args)
            with DB_LOCK:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (target_id, peer))
                CONN.execute("UPDATE members SET nickname=? WHERE user_id=? AND peer_id=?", (new_nick, target_id, peer))
                CONN.commit()
            send_msg(peer, "✅ Ник {} установлен: **{}**".format(mention(target_id), new_nick))
        else:
            new_nick = " ".join(args)
            with DB_LOCK:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (sender, peer))
                CONN.execute("UPDATE members SET nickname=? WHERE user_id=? AND peer_id=?", (new_nick, sender, peer))
                CONN.commit()
            send_msg(peer, "✅ Твой ник установлен: **{}**".format(new_nick))

    elif cmd == "проверка":
        if not admin:
            send_msg(peer, "⛔ Только администратор и выше.")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите пользователя: `Мд проверка @игрок`")
            return
        target_id = targets[0]
        month_ago = int(time.time()) - 30 * 86400
        with DB_LOCK:
            rows = CONN.execute("""
                SELECT type, reason, message_id, issued_by, issued_at, duration_minutes 
                FROM punishment_history 
                WHERE peer_id=? AND user_id=? AND issued_at>=? 
                ORDER BY issued_at DESC
            """, (peer, target_id, month_ago)).fetchall()
        if not rows:
            send_msg(peer, "ℹ️ У {} нет наказаний за последний месяц.".format(mention(target_id)))
            return
        lines = ["📜 История наказаний {} за месяц:\n".format(mention(target_id))]
        for idx, r in enumerate(rows, 1):
            dt = datetime.datetime.fromtimestamp(r["issued_at"], MSK_TZ).strftime("%d.%m %H:%M")
            issuer = mention(r["issued_by"]) if r["issued_by"] else "Неизвестно"
            ptype = "🔇 Мут" if r["type"] == "mute" else "🚫 Бан"
            duration_text = ""
            if r["type"] == "mute" and r["duration_minutes"]:
                duration_text = " на {} мин".format(r["duration_minutes"])
            reason = r["reason"] or "Не указана"
            msg_ref = ""
            if r["message_id"]:
                msg_ref = "\n   📎 Ответом на сообщение #{}".format(r["message_id"])
            lines.append("#{}. {} {} | {}{}".format(idx, ptype, duration_text, dt, msg_ref))
            lines.append("   👤 Выдал: {}".format(issuer))
            lines.append("   📝 Причина: {}".format(reason))
            lines.append("")
        send_msg(peer, "\n".join(lines))

    elif cmd == "голоса":
        try:
            if not admin:
                send_msg(peer, "⛔ Только администраторы могут смотреть голоса.")
                return
            is_yesterday = args and args[0].lower() == "вчера"
            if is_yesterday:
                target_date = (get_msk_now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                day_name = "вчера"
            else:
                target_date = get_msk_now().strftime("%Y-%m-%d")
                day_name = "сегодня"
            yesterday_str = (get_msk_now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            with DB_LOCK:
                CONN.execute("DELETE FROM poll_votes WHERE date < ?", (yesterday_str,))
                rows = CONN.execute("""
                    SELECT user_id, COUNT(*) as count FROM poll_votes
                    WHERE peer_id=? AND date=? GROUP BY user_id ORDER BY count DESC
                """, (peer, target_date)).fetchall()
            if not rows:
                send_msg(peer, "🗳 {} ({}) никто не голосовал.".format(day_name.capitalize(), target_date))
                return
            lines = ["🗳 Голоса за {} ({}):\n".format(day_name, target_date)]
            now_ts = int(time.time())
            for r in rows:
                count = r['count']
                cooldown_text = ""
                if target_date == get_msk_now().strftime("%Y-%m-%d"):
                    mem_row = CONN.execute("SELECT last_vote_time FROM members WHERE user_id=? AND peer_id=?", (r['user_id'], peer)).fetchone()
                    if mem_row and mem_row['last_vote_time']:
                        elapsed = now_ts - mem_row['last_vote_time']
                        if elapsed < 3600:
                            remaining_mins = (3600 - elapsed) // 60
                            cooldown_text = " (КД: {}м)".format(remaining_mins)
                lines.append("• {} — {} раз(а){}".format(mention(r['user_id']), count, cooldown_text))
            send_msg(peer, "\n".join(lines))
        except Exception as e:
            print("Error in голоса command: {}".format(e))
            send_msg(peer, "❌ Ошибка при выполнении команды: {}".format(e))

    elif cmd in ["парк", "прем", "чат"]:
        block_names = {"парк": "park", "прем": "prem", "чат": "chat"}
        key = block_names[cmd]
        reply = msg_obj.get("reply_message", {})
        if reply and isinstance(reply, dict) and reply.get("text"):
            if not admin:
                send_msg(peer, "⛔ Только администраторы могут изменять этот блок.")
                return
            with DB_LOCK:
                CONN.execute("INSERT OR REPLACE INTO info_blocks(peer_id, key, text) VALUES(?,?,?)", (peer, key, reply["text"].strip()))
                CONN.commit()
            send_msg(peer, "✅ Информация '{}' обновлена.".format(cmd))
        else:
            with DB_LOCK:
                row = CONN.execute("SELECT text FROM info_blocks WHERE peer_id=? AND key=?", (peer, key)).fetchone()
            if row and row["text"]:
                send_msg(peer, "📌 Информация ({}):\n\n{}".format(cmd.capitalize(), row['text']))
            else:
                send_msg(peer, "ℹ️ Информация '{}' пока не установлена.".format(cmd))

    elif cmd == "пред":
        if not moderator:
            send_msg(peer, "⛔ Только модератор и выше могут выдавать предупреждения.")
            return
        duration_days = int(get_setting(peer, "default_warn_days", "7") or "7")
        reason_parts = []
        for arg in args:
            if arg.isdigit() and not re.match(r"^\d{5,}$", arg):
                duration_days = int(arg)
            elif arg.lower() == "навсегда":
                duration_days = 9999
            elif not re.match(r"^\[id\d+\|", arg) and not re.match(r"^@id\d+", arg) and not re.match(r"^\d{5,}$", arg):
                reason_parts.append(arg)
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите пользователя: `Мд пред @игрок причина`")
            return
        reason = " ".join(reason_parts).strip()
        if not reason and not has_reply:
            send_msg(peer, "❌ Укажите причину: `Мд пред @игрок причина` (или ответь на сообщение нарушителя)")
            return
        if not reason:
            reason = "Ответом на сообщение нарушителя"
        max_warns = int(get_setting(peer, "max_warns", "3") or "3")
        now = time.time()
        expiry = now + (duration_days * 86400) if duration_days < 9999 else now + (36500 * 86400)
        for t_id in targets:
            if t_id == CREATOR_ID or t_id == get_chat_owner(peer):
                continue
            days_str = "∞" if duration_days >= 9999 else str(duration_days)
            with DB_LOCK:
                row = CONN.execute("SELECT warnings, warn_durations, warn_reasons FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                if row:
                    current_warns = (row["warnings"] or 0) + 1
                    old_durations = row["warn_durations"] or ""
                    old_reasons = row["warn_reasons"] or ""
                    new_durations = "{}|{}".format(old_durations, days_str) if old_durations else days_str
                    new_reasons = "{}|{}".format(old_reasons, reason) if old_reasons else reason
                    CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=?, warn_reasons=? WHERE user_id=? AND peer_id=?",
                                 (current_warns, new_durations, expiry, new_reasons, t_id, peer))
                else:
                    current_warns = 1
                    new_durations = days_str
                    new_reasons = reason
                    CONN.execute("INSERT INTO members(user_id, peer_id, warnings, warn_durations, warn_expiry, warn_reasons) VALUES(?,?,?,?,?,?)",
                                 (t_id, peer, current_warns, new_durations, expiry, new_reasons))
                CONN.commit()
            add_punishment(peer, t_id, "warn", reason, reply_msg_id, sender, duration_days * 1440)
            send_msg(peer, "⚠️ {} получает предупреждение ({}/{}) ({} дн.). Причина: {}".format(mention(t_id), current_warns, max_warns, new_durations, reason))
            if current_warns >= max_warns:
                try:
                    chat_id = peer - 2000000000
                    with DB_LOCK:
                        nick_row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                    nick = nick_row["nickname"] if nick_row and nick_row["nickname"] else mention(t_id)
                    VK.messages.removeChatUser(chat_id=chat_id, member_id=t_id)
                    add_punishment(peer, t_id, "ban", "Автокик за {} предупреждений".format(max_warns), 0, sender, 0)
                    with DB_LOCK:
                        CONN.execute("UPDATE members SET warnings=0, warn_durations='', warn_expiry=0, warn_reasons='' WHERE user_id=? AND peer_id=?", (t_id, peer))
                        CONN.commit()
                    admin_chat_raw = get_setting(peer, "admin_report_chat", "")
                    admin_chat_clean = "".join(filter(str.isdigit, str(admin_chat_raw)))
                    if len(admin_chat_clean) >= 9:
                        report_peer = int(admin_chat_clean)
                        chat_name = "Неизвестная беседа"
                        try:
                            conv = VK.messages.getConversationsById(peer_ids=peer)
                            if conv.get("items"):
                                chat_name = conv["items"][0].get("chat_settings", {}).get("title", "Неизвестная беседа")
                        except: pass
                        report_text = (
                            "🚨 **ПРИВЕТСТВУЮ, АДМИНИСТРАТОРЫ!** 😀\n\n"
                            "Игрок {} ({}) был исключен из беседы '{}'.\n"
                            "Прошу принять меры и исключить его из семьи в игре. 👊"
                        ).format(mention(t_id), nick, chat_name)
                        try:
                            send_msg(report_peer, report_text)
                        except Exception as e:
                            print("Ошибка отправки отчета в {}: {}".format(report_peer, e))
                except Exception as e:
                    print("Kick error:", e)
                    send_msg(peer, "❌ Не удалось исключить {}: {}".format(mention(t_id), e))

    elif cmd == "-пред":
        if not moderator:
            send_msg(peer, "⛔ Только модератор и выше могут снимать предупреждения.")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите пользователя: `Мд -пред @игрок`")
            return
        for t_id in targets:
            with DB_LOCK:
                row = CONN.execute("SELECT warnings, warn_durations, warn_reasons FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                if row and row["warnings"] > 0:
                    new_warns = row["warnings"] - 1
                    old_durations = row["warn_durations"] or ""
                    old_reasons = row["warn_reasons"] or ""
                    parts = old_durations.split("|")
                    if parts: parts.pop()
                    new_durations = "|".join(parts)
                    parts_r = old_reasons.split("|")
                    if parts_r: parts_r.pop()
                    new_reasons = "|".join(parts_r)
                    new_expiry = 0 if new_warns == 0 else row["warn_expiry"]
                    CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=?, warn_reasons=? WHERE user_id=? AND peer_id=?",
                                 (new_warns, new_durations, new_expiry, new_reasons, t_id, peer))
                    CONN.commit()
                    send_msg(peer, "✅ С {} снято предупреждение.".format(mention(t_id)))
                else:
                    send_msg(peer, "ℹ️ У {} нет предупреждений.".format(mention(t_id)))

    elif cmd == "бан":
        if not moderator:
            send_msg(peer, "⛔ Только модератор и выше могут банить.")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите пользователя: `Мд бан @игрок`")
            return
        chat_name = "Неизвестная беседа"
        try:
            conv = VK.messages.getConversationsById(peer_ids=peer)
            if conv.get("items"):
                chat_name = conv["items"][0].get("chat_settings", {}).get("title", "Неизвестная беседа")
        except: pass
        for t_id in targets:
            try:
                chat_id = peer - 2000000000
                with DB_LOCK:
                    nick_row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                nick = nick_row["nickname"] if nick_row and nick_row["nickname"] else mention(t_id)
                VK.messages.removeChatUser(chat_id=chat_id, member_id=t_id)
                add_punishment(peer, t_id, "ban", "Бан через команду", reply_msg_id, sender, 0)
                with DB_LOCK:
                    CONN.execute("UPDATE members SET warnings=0, warn_durations='', warn_expiry=0, warn_reasons='' WHERE user_id=? AND peer_id=?", (t_id, peer))
                    CONN.commit()
                admin_chat_raw = get_setting(peer, "admin_report_chat", "")
                admin_chat_clean = "".join(filter(str.isdigit, str(admin_chat_raw)))
                if len(admin_chat_clean) >= 9:
                    report_peer = int(admin_chat_clean)
                    report_text = (
                        "🚨 **ПРИВЕТСТВУЮ, АДМИНИСТРАТОРЫ!** 😀\n\n"
                        "Игрок {} ({}) был исключен из беседы '{}'.\n"
                        "Прошу принять меры и исключить его из семьи в игре. 👊"
                    ).format(mention(t_id), nick, chat_name)
                    try:
                        send_msg(report_peer, report_text)
                        send_msg(peer, "✅ Игрок {} забанен. Отчет отправлен в адм-чат.".format(mention(t_id)))
                    except Exception as e:
                        print("Ошибка отправки отчета в {}: {}".format(report_peer, e))
            except Exception as e:
                send_msg(peer, "❌ Не удалось забанить {}: {}".format(mention(t_id), e))

    elif cmd == "мут":
        if not moderator:
            send_msg(peer, "⛔ Только модератор и выше могут мутить.")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        minutes = None
        reason_parts = []
        for arg in args:
            if arg.isdigit() and not re.match(r"^\d{5,}$", arg):
                if minutes is None:
                    minutes = int(arg)
            elif not re.match(r"^\[id\d+\|", arg) and not re.match(r"^@id\d+", arg) and not re.match(r"^\d{5,}$", arg):
                reason_parts.append(arg)
        if not targets:
            send_msg(peer, "❌ Укажите пользователя: `Мд мут @игрок <минуты> причина`")
            return
        if minutes is None or minutes <= 0:
            send_msg(peer, "❌ Укажите время мута: `Мд мут @игрок <минуты> причина`")
            return
        reason = " ".join(reason_parts).strip()
        if not reason and not has_reply:
            send_msg(peer, "❌ Укажите причину: `Мд мут @игрок <минуты> причина` (или ответь на сообщение нарушителя)")
            return
        if not reason:
            reason = "Ответом на сообщение нарушителя"
        mute_until = int(time.time()) + minutes * 60
        for t in targets:
            if t == CREATOR_ID or t == get_chat_owner(peer):
                send_msg(peer, "❌ Нельзя мутить владельца/создателя.")
                continue
            with DB_LOCK:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (t, peer))
                CONN.execute("UPDATE members SET mute_until=?, mute_reason=? WHERE user_id=? AND peer_id=?", (mute_until, reason, t, peer))
                CONN.commit()
            add_punishment(peer, t, "mute", reason, reply_msg_id, sender, minutes)
            send_msg(peer, "🔇 {} получил мут на {} мин. Причина: {}".format(mention(t), minutes, reason))

    elif cmd == "-мут":
        if not moderator:
            send_msg(peer, "⛔ Только модератор и выше могут снимать мут.")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите пользователя: `Мд -мут @игрок`")
            return
        for t in targets:
            with DB_LOCK:
                CONN.execute("UPDATE members SET mute_until=0, mute_reason='' WHERE user_id=? AND peer_id=?", (t, peer))
                CONN.commit()
            send_msg(peer, "🔊 Мут снят с {}.".format(mention(t)))

    elif cmd == "мутлист":
        if not moderator:
            send_msg(peer, "⛔ Только модератор и выше.")
            return
        now = int(time.time())
        with DB_LOCK:
            rows = CONN.execute("SELECT user_id, mute_until, mute_reason FROM members WHERE peer_id=? AND mute_until>?", (peer, now)).fetchall()
        if not rows:
            send_msg(peer, "✅ Сейчас нет замученных пользователей.")
            return
        lines = ["🔇 Список замученных:\n"]
        for r in rows:
            remaining = r["mute_until"] - now
            days = remaining // 86400
            hours = (remaining % 86400) // 3600
            mins = (remaining % 3600) // 60
            secs = remaining % 60
            time_parts = []
            if days > 0: time_parts.append("{} дн".format(days))
            if hours > 0: time_parts.append("{} ч".format(hours))
            if mins > 0: time_parts.append("{} мин".format(mins))
            time_parts.append("{} сек".format(secs))
            time_str = " ".join(time_parts)
            reason = r["mute_reason"] or "Не указана"
            lines.append("• {} — осталось: {} | Причина: {}".format(mention(r["user_id"]), time_str, reason))
        send_msg(peer, "\n".join(lines))

    elif cmd == "предлист":
        if not moderator:
            send_msg(peer, "⛔ Только модератор и выше.")
            return
        page = int(args[0]) if args and args[0].isdigit() else 1
        per_page = 20
        with DB_LOCK:
            total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND warnings>0", (peer,)).fetchone()[0]
            rows = CONN.execute("SELECT user_id, nickname, warnings, warn_durations, warn_reasons FROM members WHERE peer_id=? AND warnings>0 ORDER BY warnings DESC LIMIT ? OFFSET ?", (peer, per_page, (page - 1) * per_page)).fetchall()
        if not rows:
            send_msg(peer, "✅ Ни у кого нет предупреждений.")
            return
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        lines = ["⚠️ Список предупреждений (страница {} из {}):\n".format(page, total_pages)]
        max_warns = int(get_setting(peer, "max_warns", "3") or "3")
        for idx, r in enumerate(rows, (page - 1) * per_page + 1):
            name = get_user_name(r["user_id"])
            nick = r["nickname"] or "Не установлен"
            warns = r["warnings"] or 0
            durations = r["warn_durations"] or "0"
            reasons = r["warn_reasons"] or "Не указана"
            lines.append("{}. {} - \"{}\" ({}/{}) ({} дн.)\n   Причина: {}".format(idx, name, nick, warns, max_warns, durations, reasons))
        send_msg(peer, "\n".join(lines))

    elif cmd == "статусы":
        text, keyboard_json, total_pages = build_status_page(peer, 1)
        if text is None:
            send_msg(peer, "ℹ️ Статусов пока нет.")
            return
        VK.messages.send(peer_id=peer, message=text, keyboard=keyboard_json, random_id=random.getrandbits(31))

    elif cmd == "статус":
        if not main_admin:
            send_msg(peer, "⛔ Только главный админ и выше.")
            return
        if not args:
            send_msg(peer, "❌ Формат:\n`Мд статус @игрок <номер>` — назначить\n`Мд статус создать <название>` — создать\n`Мд статус удалить <номер>` — удалить\n`Мд статус редактировать <номер> <новое название>` — переименовать\n`Мд статус снять @игрок` — снять")
            return
        subcmd = args[0].lower()
        if subcmd == "создать":
            name = " ".join(args[1:])
            if not name:
                send_msg(peer, "❌ Формат: `Мд статус создать <название>`")
                return
            with DB_LOCK:
                try:
                    CONN.execute("INSERT INTO statuses(peer_id, name) VALUES(?,?)", (peer, name))
                    CONN.commit()
                    send_msg(peer, "✅ Статус «{}» создан.".format(name))
                except sqlite3.IntegrityError:
                    send_msg(peer, "❌ Статус «{}» уже существует.".format(name))
        elif subcmd == "удалить":
            if len(args) < 2 or not args[1].isdigit():
                send_msg(peer, "❌ Формат: `Мд статус удалить <номер статуса>`")
                return
            status_num = int(args[1])
            with DB_LOCK:
                rows = CONN.execute("SELECT id FROM statuses WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if status_num < 1 or status_num > len(rows):
                    send_msg(peer, "❌ Статус с номером {} не найден.".format(status_num))
                    return
                status_id = rows[status_num - 1]["id"]
                CONN.execute("DELETE FROM statuses WHERE id=?", (status_id,))
                CONN.execute("DELETE FROM user_statuses WHERE status_id=?", (status_id,))
                CONN.commit()
            send_msg(peer, "✅ Статус удалён.")
        elif subcmd == "редактировать":
            if len(args) < 3 or not args[1].isdigit():
                send_msg(peer, "❌ Формат: `Мд статус редактировать <номер статуса> <новое название>`")
                return
            status_num = int(args[1])
            new_name = " ".join(args[2:])
            with DB_LOCK:
                rows = CONN.execute("SELECT id FROM statuses WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if status_num < 1 or status_num > len(rows):
                    send_msg(peer, "❌ Статус с номером {} не найден.".format(status_num))
                    return
                status_id = rows[status_num - 1]["id"]
                CONN.execute("UPDATE statuses SET name=? WHERE id=?", (new_name, status_id))
                CONN.commit()
            send_msg(peer, "✅ Статус переименован в «{}».".format(new_name))
        elif subcmd == "снять":
            targets = extract_targets(" ".join(args[1:]), msg_obj.get("reply_message", {}).get("from_id", 0))
            if not targets:
                send_msg(peer, "❌ Укажите пользователя: `Мд статус снять @игрок`")
                return
            for t in targets:
                with DB_LOCK:
                    CONN.execute("DELETE FROM user_statuses WHERE user_id=? AND peer_id=?", (t, peer))
                    CONN.commit()
                send_msg(peer, "✅ Статус снят с {}.".format(mention(t)))
        else:
            try:
                status_num = int(args[-1])
            except:
                send_msg(peer, "❌ Формат: `Мд статус @игрок <номер статуса>`")
                return
            targets = extract_targets(" ".join(args[:-1]), msg_obj.get("reply_message", {}).get("from_id", 0))
            if not targets:
                send_msg(peer, "❌ Укажите пользователя: `Мд статус @игрок <номер статуса>`")
                return
            with DB_LOCK:
                rows = CONN.execute("SELECT id, name FROM statuses WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if status_num < 1 or status_num > len(rows):
                    send_msg(peer, "❌ Статус с номером {} не найден.".format(status_num))
                    return
                status_id = rows[status_num - 1]["id"]
                status_name = rows[status_num - 1]["name"]
            for t in targets:
                with DB_LOCK:
                    CONN.execute("INSERT OR REPLACE INTO user_statuses(user_id, peer_id, status_id) VALUES(?,?,?)", (t, peer, status_id))
                    CONN.commit()
                send_msg(peer, "✅ {} назначен на статус «{}».".format(mention(t), status_name))

    elif cmd in ["адмчат", "admg"]:
        if not owner:
            send_msg(peer, "⛔ Только владелец или создатель может менять чат для отчетов.")
            return
        if args and args[0].lower() == "удалить":
            with DB_LOCK:
                CONN.execute("DELETE FROM settings WHERE peer_id=? AND key='admin_report_chat'", (peer,))
                CONN.commit()
            send_msg(peer, "✅ Привязка адм-чата удалена.")
            return
        if not args or not args[0].isdigit():
            current = get_setting(peer, "admin_report_chat", "Не установлена")
            send_msg(peer, "📌 Текущий чат для отчетов: `{}`\n\n`Мд адмчат <id>` — установить\n`Мд адмчат удалить` — отключить".format(current))
            return
        target_chat = int(args[0])
        set_setting(peer, "admin_report_chat", str(target_chat))
        test_text = "✅ Отчеты о банах из чата {} теперь будут отправляться сюда.".format(peer)
        try:
            send_msg(target_chat, test_text)
            send_msg(peer, "✅ Репорты будут отправляться в чат {}.".format(target_chat))
        except Exception as e:
            send_msg(peer, "⚠️ Настройка сохранена, но не удалось отправить тест в чат {}.".format(target_chat))

    elif cmd == "номер_чата":
        if not admin:
            send_msg(peer, "⛔ Только администраторы.")
            return
        chat_owner_id = get_chat_owner(peer)
        owner_name = mention(chat_owner_id) if chat_owner_id else "Не определён"
        send_msg(peer, "📌 Номер чата: {}\nСоздатель: {}".format(peer, owner_name))

    elif cmd == "лимит_предов":
        if not owner:
            send_msg(peer, "⛔ Только владелец/создатель.")
            return
        if not args or not args[0].isdigit():
            send_msg(peer, "❌ Формат: `Мд лимит предов <число>`")
            return
        set_setting(peer, "max_warns", args[0])
        send_msg(peer, "✅ Макс. количество предупреждений: {}".format(args[0]))

    elif cmd == "кд_предов":
        if not owner:
            send_msg(peer, "⛔ Только владелец/создатель.")
            return
        if not args or not args[0].isdigit():
            send_msg(peer, "❌ Формат: `Мд кд предов <дней>`")
            return
        set_setting(peer, "default_warn_days", args[0])
        send_msg(peer, "✅ Срок предупреждения по умолчанию: {} дн.".format(args[0]))

    elif cmd == "старт_контроль":
        if not owner:
            send_msg(peer, "⛔ Только владелец/создатель.")
            return
        set_setting(peer, "control_active", "1")
        send_msg(peer, "✅ Система контроля активности включена.")

    elif cmd == "стоп_контроль":
        if not owner:
            send_msg(peer, "⛔ Только владелец/создатель.")
            return
        set_setting(peer, "control_active", "0")
        send_msg(peer, "❌ Система контроля активности выключена.")

    elif cmd == "время_опросов":
        if not owner:
            send_msg(peer, "⛔ Только владелец/создатель.")
            return
        if len(args) >= 2:
            try:
                start_h, start_m = map(int, args[0].split(":"))
                end_h, end_m = map(int, args[1].split(":"))
                if start_m != end_m:
                    send_msg(peer, "❌ Минуты начала и конца должны совпадать (например, 10:20 23:20).")
                    return
                set_setting(peer, "poll_start", str(start_h))
                set_setting(peer, "poll_end", str(end_h))
                set_setting(peer, "poll_minute", str(start_m))
                send_msg(peer, "✅ Время опросов: каждый час в {} мин, с {}:00 до {}:00".format(start_m, start_h, end_h))
            except ValueError:
                send_msg(peer, "❌ Формат: `Мд время опросов ЧЧ:ММ ЧЧ:ММ`")
        else:
            send_msg(peer, "❌ Формат: `Мд время опросов ЧЧ:ММ ЧЧ:ММ`")

    elif cmd == "защита":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            with DB_LOCK:
                protected = [int(r["user_id"]) for r in CONN.execute("SELECT user_id FROM members WHERE peer_id=? AND poll_protected=1", (peer,)).fetchall()]
            if protected:
                send_msg(peer, "🛡 Защищенные от опросов: " + ", ".join(mention(x) for x in protected))
            else:
                send_msg(peer, "🛡 Защищенных участников нет.")
            return
        for t_id in targets:
            with DB_LOCK:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (t_id, peer))
                CONN.execute("UPDATE members SET poll_protected=1 WHERE user_id=? AND peer_id=?", (t_id, peer))
                CONN.commit()
            send_msg(peer, "🛡 {} добавлен в защиту от опросов.".format(mention(t_id)))

    elif cmd == "-защита":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите пользователя: `Мд -защита @игрок`")
            return
        for t_id in targets:
            with DB_LOCK:
                CONN.execute("UPDATE members SET poll_protected=0 WHERE user_id=? AND peer_id=?", (t_id, peer))
                CONN.commit()
            send_msg(peer, "✅ {} удален из защиты от опросов.".format(mention(t_id)))

    elif cmd == "текст_др":
        if not owner:
            send_msg(peer, "⛔ Только владелец/создатель.")
            return
        reply = msg_obj.get("reply_message", {})
        if not isinstance(reply, dict) or not reply.get("text"):
            current = get_setting(peer, "birthday_text", "")
            if current:
                send_msg(peer, "📝 Текущий текст:\n\n{}\n\n---\n(в конце добавится @именинника)".format(current))
            else:
                send_msg(peer, "📝 Текст не установлен. Используется стандартный.")
            return
        set_setting(peer, "birthday_text", reply["text"].strip())
        send_msg(peer, "✅ Текст поздравления сохранён.")

    elif cmd == "создать":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        reply = msg_obj.get("reply_message", {})
        if not isinstance(reply, dict) or (not reply.get("text") and not reply.get("attachments")):
            send_msg(peer, "❌ Ответьте на сообщение и введите: `Мд создать <название> <минуты> [кол-во]`")
            return
        if len(args) < 2:
            send_msg(peer, "❌ Формат: `Мд создать <название> <минуты> [кол-во]`")
            return
        try:
            repeat_count = 1
            if len(args) >= 3 and args[-1].isdigit():
                repeat_count = int(args[-1])
                minutes = int(args[-2])
                name = " ".join(args[:-2])
            else:
                minutes = int(args[-1])
                name = " ".join(args[:-1])
        except ValueError:
            send_msg(peer, "❌ Минуты и количество должны быть числами.")
            return
        source_msg_id = int(reply.get("conversation_message_id", 0) or reply.get("id", 0) or 0)
        attach_str = parse_reply_attachments(reply)
        with DB_LOCK:
            try:
                CONN.execute("""INSERT INTO reminders(peer_id, name, text, attachments, source_message_id, interval_minutes, repeat_count, next_trigger) VALUES(?,?,?,?,?,?,?,?)""",
                             (peer, name, reply.get("text", ""), attach_str, source_msg_id, minutes, repeat_count, time.time() + minutes * 60))
                CONN.commit()
                extra = ", повтор: {} раз".format(repeat_count) if repeat_count > 1 else ""
                send_msg(peer, "✅ Напоминание «{}» создано. Интервал: {} мин{}".format(name, minutes, extra))
            except sqlite3.IntegrityError:
                send_msg(peer, "❌ Напоминание «{}» уже существует.".format(name))

    elif cmd == "список":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        with DB_LOCK:
            rows = CONN.execute("SELECT id, name, interval_minutes, repeat_count, next_trigger, enabled, attachments, source_message_id FROM reminders WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
        if not rows:
            send_msg(peer, "📭 Список напоминаний пуст.")
            return
        msg = "📋 Список напоминаний:\n\n"
        now = time.time()
        for idx, r in enumerate(rows, 1):
            remaining = max(0, r["next_trigger"] - now)
            mins, secs = int(remaining // 60), int(remaining % 60)
            status = "🟢 ВКЛ" if r["enabled"] else "🔴 ВЫКЛ"
            attach_info = " 📎" if r["source_message_id"] else ""
            msg += "#{} {}{}\n   {} | {} мин | Через: {}м {}с\n".format(idx, r['name'], attach_info, status, r['interval_minutes'], mins, secs)
        send_msg(peer, msg)

    elif cmd == "удалить":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        if not args: return send_msg(peer, "❌ Формат: `Мд удалить <номер или название>`")
        arg = " ".join(args)
        with DB_LOCK:
            if arg.isdigit():
                row = CONN.execute("SELECT name FROM reminders WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if 1 <= int(arg) <= len(row):
                    name = row[int(arg)-1]["name"]
                    CONN.execute("DELETE FROM reminders WHERE peer_id=? AND name=?", (peer, name))
                    CONN.commit()
                    send_msg(peer, "✅ Напоминание «{}» удалено.".format(name))
                    return
            else:
                res = CONN.execute("DELETE FROM reminders WHERE peer_id=? AND name=?", (peer, arg))
                if res.rowcount > 0:
                    CONN.commit()
                    send_msg(peer, "✅ Напоминание «{}» удалено.".format(arg))
                    return
        send_msg(peer, "❌ Напоминание «{}» не найдено.".format(arg))

    elif cmd == "редактировать":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        if len(args) < 2: return send_msg(peer, "❌ Формат: `Мд редактировать <название/номер> <минуты>`")
        try:
            minutes = int(args[-1])
            arg = " ".join(args[:-1])
        except: return send_msg(peer, "❌ Минуты должны быть числом.")
        with DB_LOCK:
            if arg.isdigit():
                row = CONN.execute("SELECT name FROM reminders WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if 1 <= int(arg) <= len(row): arg = row[int(arg)-1]["name"]
            res = CONN.execute("UPDATE reminders SET interval_minutes=?, next_trigger=? WHERE peer_id=? AND name=?", (minutes, time.time() + minutes * 60, peer, arg))
            CONN.commit()
            if res.rowcount > 0:
                send_msg(peer, "✅ Напоминание «{}» обновлено. Интервал: {} мин.".format(arg, minutes))
            else:
                send_msg(peer, "❌ Напоминание «{}» не найдено.".format(arg))

    elif cmd == "включить":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        arg = " ".join(args) if args else None
        with DB_LOCK:
            if arg:
                CONN.execute("UPDATE reminders SET enabled=1, next_trigger=? WHERE peer_id=? AND name=?", (time.time() + 60, peer, arg))
            else:
                CONN.execute("UPDATE reminders SET enabled=1 WHERE peer_id=?", (peer,))
            CONN.commit()
        label = "«{}»".format(arg) if arg else "все"
        send_msg(peer, "✅ Напоминание {} включено.".format(label))

    elif cmd == "отключить":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        arg = " ".join(args) if args else None
        with DB_LOCK:
            if arg:
                CONN.execute("UPDATE reminders SET enabled=0 WHERE peer_id=? AND name=?", (peer, arg))
            else:
                CONN.execute("UPDATE reminders SET enabled=0 WHERE peer_id=?", (peer,))
            CONN.commit()
        label = "«{}»".format(arg) if arg else "все"
        send_msg(peer, "✅ Напоминание {} отключено.".format(label))

    elif cmd == "развернуть":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        if not args: return send_msg(peer, "❌ Формат: `Мд развернуть <название или номер>`")
        arg = " ".join(args)
        with DB_LOCK:
            if arg.isdigit():
                row = CONN.execute("SELECT name FROM reminders WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if 1 <= int(arg) <= len(row): arg = row[int(arg)-1]["name"]
            row = CONN.execute("SELECT text FROM reminders WHERE peer_id=? AND name=?", (peer, arg)).fetchone()
        if row:
            send_msg(peer, "📝 {}:\n\n{}".format(arg, row['text']))
        else:
            send_msg(peer, "❌ Не найдено.")

    elif cmd == "назначить":
        if sender_role < 2:
            send_msg(peer, "⛔ Только админ и выше могут назначать роли.")
            return
        if not args:
            send_msg(peer, "❌ Формат: `Мд назначить @игрок <номер ранга>`\nРанги: 1 - Модератор, 2 - Админ, 3 - Главный Админ")
            return
        try:
            target_role = int(args[-1])
        except:
            send_msg(peer, "❌ Укажите номер ранга: `Мд назначить @игрок <номер ранга>`")
            return
        if target_role not in [1, 2, 3]:
            send_msg(peer, "❌ Неверный ранг. Доступно: 1, 2, 3")
            return
        if sender_role == 2 and target_role > 1:
            send_msg(peer, "⛔ Админ может назначить только модератора (ранг 1).")
            return
        if sender_role == 3 and target_role > 2:
            send_msg(peer, "⛔ Главный Админ может назначить только админа(2) или модератора(1).")
            return
        targets = extract_targets(" ".join(args[:-1]), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите игрока: `Мд назначить @игрок <номер ранга>`")
            return
        for t in targets:
            if t == CREATOR_ID or t == get_chat_owner(peer):
                send_msg(peer, "❌ Нельзя менять роль владельца/создателя.")
                continue
            old_role = get_user_role(peer, t)
            set_user_role(peer, t, target_role)
            if old_role > target_role:
                send_msg(peer, "⬇️ {} понижен до {}.".format(mention(t), ROLE_NAMES[target_role]))
            elif old_role < target_role:
                send_msg(peer, "⬆️ {} повышен до {}.".format(mention(t), ROLE_NAMES[target_role]))
            else:
                send_msg(peer, "ℹ️ {} уже имеет роль {}.".format(mention(t), ROLE_NAMES[target_role]))

    elif cmd == "снять":
        if sender_role < 2:
            send_msg(peer, "⛔ Только админ и выше могут снимать роли.")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите игрока: `Мд снять @игрок`")
            return
        for t in targets:
            if t == CREATOR_ID or t == get_chat_owner(peer):
                send_msg(peer, "❌ Нельзя снять роль владельца/создателя.")
                continue
            old_role = get_user_role(peer, t)
            if old_role == 0:
                send_msg(peer, "ℹ️ {} уже является участником.".format(mention(t)))
                continue
            if old_role >= sender_role and not is_owner(sender, peer):
                send_msg(peer, "⛔ Нельзя снять роль выше или равную вашей.")
                continue
            set_user_role(peer, t, 0)
            send_msg(peer, "✅ Роль снята, {} теперь участник.".format(mention(t)))

    elif cmd == "тишина":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        set_setting(peer, "silence_mode", "1")
        send_msg(peer, "🔇 Режим тишины включен.")

    elif cmd == "тишина_офф":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        set_setting(peer, "silence_mode", "0")
        send_msg(peer, "🔊 Режим тишины выключен.")

    elif cmd == "проверка_опроса":
        if not owner:
            send_msg(peer, "⛔ Только владелец/создатель.")
            return
        if len(args) >= 1:
            try:
                time_parts = args[0].split(":")
                check_h = int(time_parts[0])
                check_m = int(time_parts[1]) if len(time_parts) > 1 else 0
                if 0 <= check_h <= 23 and 0 <= check_m <= 59:
                    set_setting(peer, "check_hour", str(check_h))
                    set_setting(peer, "check_minute", str(check_m))
                    set_setting(peer, "last_23_check", "")
                    send_msg(peer, "✅ Время проверки опроса: {:02d}:{:02d}. Флаг сброшен.".format(check_h, check_m))
                else:
                    send_msg(peer, "❌ Некорректное время.")
            except (ValueError, IndexError):
                send_msg(peer, "❌ Формат: `Мд проверка опроса ЧЧ:ММ`")
        else:
            check_h = int(get_setting(peer, "check_hour", "23"))
            check_m = int(get_setting(peer, "check_minute", "0"))
            send_msg(peer, "📌 Текущее время проверки: {:02d}:{:02d}".format(check_h, check_m))

    elif cmd == "бр":
        try:
            page = int(args[0]) if args and args[0].isdigit() else 1
            text, keyboard_json, total_pages = build_br_page(page)
            if text is None:
                send_msg(peer, "❌ Не удалось получить данные о серверах BlackRussia.")
                return
            VK.messages.send(peer_id=peer, message=text, keyboard=keyboard_json, random_id=random.getrandbits(31))
        except Exception as e:
            print("бр error:", e)
            send_msg(peer, "❌ Ошибка при выполнении команды: {}".format(e))


def timer_loop():
    while True:
        try:
            time.sleep(10)
            if VK is None: continue
            now_msk = get_msk_now()
            today_str = now_msk.strftime("%Y-%m-%d")
            with DB_LOCK:
                peers = CONN.execute("SELECT DISTINCT peer_id FROM reminders").fetchall()
                bday_peers = CONN.execute("SELECT DISTINCT peer_id FROM birthdays").fetchall()
                control_peers = CONN.execute("SELECT DISTINCT peer_id FROM settings WHERE key='control_active' AND value='1'").fetchall()

            for p in peers:
                peer = p["peer_id"]
                now = time.time()
                with DB_LOCK:
                    due = CONN.execute("SELECT id, name, text, attachments, source_message_id, interval_minutes, repeat_count, enabled FROM reminders WHERE peer_id=? AND next_trigger<=?", (peer, now)).fetchall()
                for rem in due:
                    if rem["enabled"] == 1:
                        repeat_count = rem["repeat_count"] or 1
                        for _ in range(repeat_count):
                            if rem["source_message_id"]:
                                success = False
                                try:
                                    forward_json = json.dumps({"peer_id": peer, "conversation_message_ids": [rem["source_message_id"]]})
                                    VK.messages.send(peer_id=peer, message="🔔 Напоминание: {}\n\n@all".format(rem['name']), forward=forward_json, random_id=random.getrandbits(31))
                                    success = True
                                except: pass
                                if not success:
                                    send_msg(peer, "🔔 Напоминание: {}\n\n{}\n\n@all".format(rem['name'], rem['text']), attachments=rem["attachments"] or None)
                            else:
                                send_msg(peer, "🔔 Напоминание: {}\n\n{}\n\n@all".format(rem['name'], rem['text']), attachments=rem["attachments"] or None)
                            time.sleep(0.5)
                        with DB_LOCK:
                            CONN.execute("UPDATE reminders SET next_trigger=? WHERE id=?", (now + rem["interval_minutes"] * 60, rem["id"]))
                            CONN.commit()
                last_poll_msg_id = get_setting(peer, "last_poll_msg_id", "")
                last_poll_time_str = get_setting(peer, "last_poll_time", "0")
                last_poll_time = int(last_poll_time_str) if last_poll_time_str.isdigit() else 0
                if last_poll_msg_id and last_poll_msg_id.isdigit() and (time.time() - last_poll_time) > 600:
                    try:
                        VK.messages.delete(peer_id=peer, message_ids=[int(last_poll_msg_id)], delete_for_all=1)
                    except Exception as e:
                        print("Не удалось удалить опрос: {}".format(e))
                    set_setting(peer, "last_poll_msg_id", "")
                    set_setting(peer, "last_poll_time", "0")

            if now_msk.hour == 0 and now_msk.minute == 0:
                for p in bday_peers:
                    check_birthdays(p["peer_id"])

            if now_msk.minute == 0:
                peers_to_sync = list(set([p["peer_id"] for p in control_peers] + [p["peer_id"] for p in bday_peers]))
                threading.Thread(target=sync_all_peers, args=(peers_to_sync,), daemon=True).start()

            for p in control_peers:
                peer = p["peer_id"]
                start_hour = int(get_setting(peer, "poll_start", "10"))
                end_hour = int(get_setting(peer, "poll_end", "22"))
                poll_minute = int(get_setting(peer, "poll_minute", "25"))
                current_hour = now_msk.hour
                is_active = False
                if start_hour <= end_hour:
                    is_active = start_hour <= current_hour <= end_hour
                else:
                    is_active = current_hour >= start_hour or current_hour <= end_hour
                if now_msk.minute == poll_minute and is_active:
                    last_poll_key = "last_poll_{}_{}".format(current_hour, poll_minute)
                    if get_setting(peer, last_poll_key, "0") != "1":
                        poll_creation_time = int(time.time())
                        keyboard_json = json.dumps({
                            "inline": True,
                            "buttons": [[{"action": {"type": "callback", "label": "✅ Проголосовать: Я", "payload": json.dumps({"cmd": "poll_vote", "time": poll_creation_time})}, "color": "positive"}]]
                        })
                        try:
                            msg_id = VK.messages.send(
                                peer_id=peer,
                                message="📊 Опрос: Кто заходит на этот кд? @all",
                                keyboard=keyboard_json,
                                random_id=random.getrandbits(31)
                            )
                            set_setting(peer, last_poll_key, "1")
                            set_setting(peer, "last_poll_msg_id", str(msg_id))
                            set_setting(peer, "last_poll_time", str(poll_creation_time))
                        except Exception as e:
                            print("Ошибка отправки опроса: {}".format(e))
                check_hour = int(get_setting(peer, "check_hour", "23"))
                check_minute = int(get_setting(peer, "check_minute", "0"))
                check_time = now_msk.replace(hour=check_hour, minute=check_minute, second=0, microsecond=0)
                if now_msk >= check_time:
                    last_23_check = get_setting(peer, "last_23_check", "")
                    if last_23_check != today_str:
                        admins = set(get_users_with_min_role(peer, 2))
                        admins.add(CREATOR_ID)
                        chat_owner = get_chat_owner(peer)
                        if chat_owner: admins.add(chat_owner)
                        with DB_LOCK:
                            members = CONN.execute("SELECT user_id FROM members WHERE peer_id=? AND poll_protected=0", (peer,)).fetchall()
                            voted = set(r["user_id"] for r in CONN.execute("SELECT user_id FROM poll_votes WHERE peer_id=? AND date=?", (peer, today_str)).fetchall())
                            max_warns = int(get_setting(peer, "max_warns", "3") or "3")
                            default_days = int(get_setting(peer, "default_warn_days", "7") or "7")
                            expiry = time.time() + (default_days * 86400)
                            inactive = [m["user_id"] for m in members if m["user_id"] not in voted and m["user_id"] not in admins]
                        if inactive:
                            lines = ["⚠️ Данные игроки не проявили актива за день и получают по 1 предупреждению:\n"]
                            for u_id in inactive:
                                with DB_LOCK:
                                    row = CONN.execute("SELECT warnings, warn_durations FROM members WHERE user_id=? AND peer_id=?", (u_id, peer)).fetchone()
                                    current_warns = (row["warnings"] or 0) + 1 if row else 1
                                    old_durations = row["warn_durations"] if row and row["warn_durations"] else ""
                                    days_str = "∞" if default_days >= 9999 else str(default_days)
                                    new_durations = "{}|{}".format(old_durations, days_str) if old_durations else days_str
                                    CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=? WHERE user_id=? AND peer_id=?",
                                                 (current_warns, new_durations, expiry, u_id, peer))
                                    CONN.commit()
                                lines.append("{} ({}/{}) ({} дн.)".format(mention(u_id), current_warns, max_warns, new_durations))
                                if current_warns >= max_warns:
                                    try:
                                        chat_id = peer - 2000000000
                                        with DB_LOCK:
                                            nick_row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (u_id, peer)).fetchone()
                                        nick = nick_row["nickname"] if nick_row and nick_row["nickname"] else mention(u_id)
                                        VK.messages.removeChatUser(chat_id=chat_id, member_id=u_id)
                                        add_punishment(peer, u_id, "ban", "Автокик за {} предупреждений (неактив)".format(max_warns), 0, 0, 0)
                                        with DB_LOCK:
                                            CONN.execute("UPDATE members SET warnings=0, warn_durations='', warn_expiry=0 WHERE user_id=? AND peer_id=?", (u_id, peer))
                                            CONN.commit()
                                        admin_chat_raw = get_setting(peer, "admin_report_chat", "")
                                        admin_chat_clean = "".join(filter(str.isdigit, str(admin_chat_raw)))
                                        if len(admin_chat_clean) >= 9:
                                            report_peer = int(admin_chat_clean)
                                            chat_name = "Неизвестная беседа"
                                            try:
                                                conv = VK.messages.getConversationsById(peer_ids=peer)
                                                if conv.get("items"):
                                                    chat_name = conv["items"][0].get("chat_settings", {}).get("title", "Неизвестная беседа")
                                            except: pass
                                            report_text = (
                                                "🚨 **ПРИВЕТСТВУЮ, АДМИНИСТРАТОРЫ!** 😀\n\n"
                                                "Игрок {} ({}) был исключен из беседы '{}'.\n"
                                                "Прошу принять меры и исключить его из семьи в игре. 👊"
                                            ).format(mention(u_id), nick, chat_name)
                                            try:
                                                send_msg(report_peer, report_text)
                                            except Exception as e:
                                                print("Error sending auto-kick report to {}: {}".format(report_peer, e))
                                    except Exception as e:
                                        print("Auto-kick error:", e)
                            send_msg(peer, "\n".join(lines))
                        set_setting(peer, "last_23_check", today_str)
                if now_msk.minute == 0:
                    with DB_LOCK:
                        no_nicks = CONN.execute("SELECT user_id, join_time FROM members WHERE peer_id=? AND (nickname='' OR nickname IS NULL)", (peer,)).fetchall()
                        for u in no_nicks:
                            last_reminder = int(get_setting(peer, "nick_reminder_{}".format(u['user_id']), "0"))
                            if time.time() - last_reminder > 3600:
                                send_msg(peer, "🔔 {}, пожалуйста, установи свой ник с помощью команды `Мд ник <твой_ник>`!".format(mention(u['user_id'])))
                                set_setting(peer, "nick_reminder_{}".format(u['user_id']), str(int(time.time())))
        except Exception as e:
            print("timer error:", e)
            time.sleep(10)


def main():
    global VK
    print("=== MD BOT starting ===")
    init_db()
    threading.Thread(target=timer_loop, daemon=True).start()
    if not VK_TOKEN:
        print("ERROR: не задана переменная окружения VK_TOKEN!")
        while not VK_TOKEN:
            time.sleep(60)
    while True:
        try:
            session = vk_api.VkApi(token=VK_TOKEN)
            VK = session.get_api()
            group_id = VK.groups.getById()[0]["id"]
            longpoll = VkBotLongPoll(session, group_id)
            print("MD BOT started, group id:", group_id)
            for event in longpoll.listen():
                if event.type == VkBotEventType.MESSAGE_EVENT:
                    handle_event(event)
                    continue
                if event.type != VkBotEventType.MESSAGE_NEW:
                    continue
                try:
                    obj = event.obj
                    msg = obj.get("message", obj) if isinstance(obj, dict) else {}
                    peer = int(msg.get("peer_id", 0) or 0)
                    sender = int(msg.get("from_id", 0) or 0)
                    txt = (msg.get("text") or "").strip()
                    if peer > 0 and sender > 0:
                        handle_message(peer, sender, txt, msg)
                except Exception as e:
                    print("message error:", e)
        except Exception as e:
            print("longpoll error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
