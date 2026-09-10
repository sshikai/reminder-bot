import os
import re
import time
import random
import sqlite3
import threading
import json
import datetime
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
DB_LOCK = threading.Lock()
VK = None
NAME_CACHE = {}
OWNER_CACHE = {}

LEADER_BDAY_TEXT = (
    "Дорогой лидер Million Dollars🎉\n"
    "От лица всего состава поздравляю тебя с днем рождения!\n\n"
    "Спасибо за твой огромный вклад в развитие Million Dollars и за то, что собрал под одним крылом таких крутых ребят.\n\n"
    "Желаем тебе железобетонного терпения, преданных замов, огромного онлайна и чтобы никто не портил тебе настроение. "
    "Пусть наша семья гремит по всему серверу! 💰\n\n{mention}"
)
DEFAULT_BDAY_TEXT = "Поздравляем {mention}. У него сегодня день рождения!🎂"

# ИСПРАВЛЕНО: добавлены "назначить" и "снять"
VALID_COMMANDS = [
    "помощь", "админы", "участник", "ники", "ник", "парк", "прем", "чат",
    "пред", "-пред", "лимит_предов", "кд_предов", "старт_контроль", "стоп_контроль",
    "время_опросов", "защита", "-защита", "бан", "адмчат", "admg",
    "текст_др", "создать", "список", "удалить", "редактировать", "включить", "отключить", "развернуть",
    "назначить", "снять"
]

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
            warn_expiry INTEGER DEFAULT 0, last_active TEXT DEFAULT '', streak INTEGER DEFAULT 0,
            poll_protected INTEGER DEFAULT 0, join_time INTEGER DEFAULT 0, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS poll_votes (user_id INTEGER, peer_id INTEGER, date TEXT, PRIMARY KEY(user_id, peer_id, date))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS info_blocks (peer_id INTEGER, key TEXT, text TEXT, PRIMARY KEY(peer_id, key))""")
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

# ИСПРАВЛЕНО: вернул два способа получения владельца
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

def is_admin(sender, peer):
    return sender > 0 and (sender == CREATOR_ID or sender == get_chat_owner(peer) or sender in get_extra_admins(peer))

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
        if r: name = f"{r[0].get('first_name', '')} {r[0].get('last_name', '')}".strip() or "Пользователь"
    except: pass
    NAME_CACHE[user_id] = name
    return name

def mention(user_id): return f"[id{user_id}|{get_user_name(user_id)}]"

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
            if ph.get("owner_id") and ph.get("id"): parts.append(f"photo{ph['owner_id']}_{ph['id']}")
    return ",".join(parts)

# ИСПРАВЛЕНО: синхронизация участников при первом вызове
def sync_members(peer):
    """Добавляет всех участников беседы в таблицу members, если их там нет"""
    try:
        members_resp = VK.messages.getConversationMembers(peer_id=peer)
        profiles = members_resp.get("profiles", [])
        now = get_msk_now().strftime("%Y-%m-%d")
        with DB_LOCK:
            for profile in profiles:
                user_id = int(profile.get("id", 0))
                if user_id <= 0: continue
                CONN.execute("""INSERT OR IGNORE INTO members(user_id, peer_id, last_active, streak) 
                                VALUES(?,?,?,?)""", (user_id, peer, now, 0))
            CONN.commit()
    except Exception as e:
        print("sync_members error:", e)

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
    if streak >= 50: return "👑"
    if streak >= 40: return ""
    if streak >= 30: return "😈"
    if streak >= 20: return "🤠"
    if streak >= 10: return "😇"
    if streak >= 5: return "😎"
    return "🤓"

def check_birthdays(peer):
    now_msk = get_msk_now()
    today_str = now_msk.strftime("%Y-%m-%d")
    current_year = now_msk.year
    last_check = get_setting(peer, "last_bday_check_date", "")
    if last_check == today_str:
        return
    with DB_LOCK:
        rows = [dict(r) for r in CONN.execute("SELECT user_id, bdate FROM birthdays WHERE peer_id=? AND bdate IS NOT NULL", (peer,)).fetchall()]
    for r in rows:
        user_id, bdate = r["user_id"], r["bdate"]
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

# ИСПРАВЛЕНО: надёжная обработка событий
def handle_event(event):
    try:
        # В vk_api данные могут быть в event.object или event.obj
        obj = event.object if hasattr(event, 'object') else event.obj
        if not isinstance(obj, dict):
            return

        event_id = obj.get("event_id")
        user_id = int(obj.get("user_id", 0))
        peer_id = int(obj.get("peer_id", 0))
        
        # Надёжный парсинг payload
        payload = obj.get("payload", "{}")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except:
                payload = {}
        
        cmd = payload.get("cmd", "")

        if cmd == "poll_vote":
            try:
                today_str = get_msk_now().strftime("%Y-%m-%d")
                with DB_LOCK:
                    CONN.execute("INSERT OR IGNORE INTO poll_votes(user_id, peer_id, date) VALUES(?,?,?)", (user_id, peer_id, today_str))
                    CONN.commit()
                
                answer_data = json.dumps({"type": "show_snackbar", "text": "✅ Ты отметился!"})
                VK.messages.sendMessageEventAnswer(
                    event_id=event_id,
                    user_id=user_id,
                    peer_id=peer_id,
                    event_data=answer_data
                )
            except Exception as db_err:
                print("DB error in poll_vote:", db_err)
                VK.messages.sendMessageEventAnswer(
                    event_id=event_id,
                    user_id=user_id,
                    peer_id=peer_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "❌ Ошибка при голосовании"})
                )
            return

        if cmd in ["niki_prev", "niki_next"]:
            if not is_admin(user_id, peer_id):
                VK.messages.sendMessageEventAnswer(event_id=event_id, user_id=user_id, peer_id=peer_id, event_data=json.dumps({"type": "show_snackbar", "text": "🚫 Только для админов"}))
                return
            
            page = int(payload.get("page", 1))
            with DB_LOCK:
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=?", (peer_id,)).fetchone()[0]
                rows = CONN.execute("SELECT user_id, nickname, warnings, warn_expiry FROM members WHERE peer_id=? ORDER BY user_id LIMIT 40 OFFSET ?", (peer_id, (page - 1) * 40)).fetchall()
            
            per_page = 40
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = max(1, min(page, total_pages))
            
            lines = [f" **Ники пользователей чата** (страница {page} из {total_pages}):\n"]
            max_warns = int(get_setting(peer_id, "max_warns", "3"))
            
            for idx, r in enumerate(rows, (page - 1) * per_page + 1):
                name = get_user_name(r["user_id"])
                nick = r["nickname"] or "Не установлен"
                warns = r["warnings"]
                days_str = "∞" if r["warn_expiry"] > time.time() + (365 * 86400) else str(max(0, int((r["warn_expiry"] - time.time()) // 86400))) if r["warn_expiry"] > 0 else "0"
                warn_icon = "️" if warns > 0 else "✅"
                lines.append(f"{idx}. {name} - \"{nick}\" ({warns}/{max_warns}) ({days_str} дн.) {warn_icon}")
            
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "niki_prev", "page": page - 1})}, "color": "secondary"})
            buttons.append({"action": {"type": "text", "label": f"{page}/{total_pages}", "payload": "{}"}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "niki_next", "page": page + 1})}, "color": "secondary"})
            
            keyboard = {"inline": True, "buttons": [buttons]}
            global_msg_id = 0
            try:
                r = VK.messages.getByConversationMessageId(peer_id=peer_id, conversation_message_ids=str(obj.get("conversation_message_id", 0)))
                if r.get("items"): global_msg_id = int(r["items"][0].get("id", 0))
            except: pass
            
            success = False
            if global_msg_id > 0:
                try:
                    VK.messages.edit(peer_id=peer_id, message_id=global_msg_id, message="\n".join(lines), keyboard=keyboard)
                    success = True
                except Exception as e:
                    print("Edit error:", e)
            
            if not success:
                try:
                    VK.messages.send(peer_id=peer_id, message="\n".join(lines) + "\n\n(Не удалось обновить, отправлено новое)", keyboard=keyboard, random_id=random.getrandbits(31))
                except Exception as e:
                    print("Send fallback error:", e)
            
            VK.messages.sendMessageEventAnswer(event_id=event_id, user_id=user_id, peer_id=peer_id, event_data=json.dumps({"type": "show_snackbar", "text": f"📄 Страница {page}"}))
            
    except Exception as e:
        print("event error:", e)


def handle_message(peer, sender, text, msg_obj):
    if text.strip() == "!!Чаты" and sender == CREATOR_ID:
        with DB_LOCK:
            peers = [row["peer_id"] for row in CONN.execute("SELECT DISTINCT peer_id FROM members").fetchall()]
        if not peers:
            send_msg(CREATOR_ID, "📭 Бот пока не зафиксировал ни одной беседы в базе.")
        else:
            lines = ["📊 **Список бесед с ботом:**\n"]
            for i in range(0, len(peers), 100):
                chunk = peers[i:i+100]
                try:
                    convos = VK.messages.getConversationsById(peer_ids=chunk)
                    for item in convos.get("items", []):
                        p_id = item.get("peer", {}).get("id", 0)
                        title = item.get("chat_settings", {}).get("title", "Личные сообщения или недоступно")
                        owner = item.get("chat_settings", {}).get("owner_id", 0)
                        owner_name = get_user_name(owner) if owner > 0 else "Нет/ЛС"
                        lines.append(f"• ID: {p_id} | Название: {title} | Владелец: {owner_name} ({owner})")
                except Exception as e:
                    lines.append(f"• Ошибка получения данных для части чатов: {e}")
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
        if get_setting(peer, "control_active") == "1":
            send_msg(peer, f"Добро пожаловать, {mention(user_id)}! 🎉\nПожалуйста, установи свой ник с помощью команды:\n`Мд ник <твой_ник>`")
            with DB_LOCK:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id, join_time) VALUES(?,?,?)", (user_id, peer, int(time.time())))
                CONN.commit()
        return

    update_member_activity(peer, sender)

    first = norm(text.split("\n")[0])
    if not first.startswith("мд "):
        return

    parts = first[3:].strip().split()
    if not parts:
        send_msg(peer, "Меня кто то звал?🧐 «Мд помощь» список команд.")
        return

    found_cmd = None
    found_args = []
    for i in range(len(parts), 0, -1):
        candidate = "_".join(parts[:i]).lower()
        if candidate in VALID_COMMANDS:
            found_cmd = candidate
            found_args = parts[i:]
            break

    if not found_cmd:
        found_cmd = parts[0].lower()
        found_args = parts[1:]

    cmd = found_cmd
    args = found_args

    if cmd not in VALID_COMMANDS:
        send_msg(peer, "Меня кто то звал?🧐 «Мд помощь» список команд.")
        return

    owner = is_owner(sender, peer)
    admin = is_admin(sender, peer)

    if cmd == "помощь":
        help_text = (
            "📖 **Команды MD BOT**\n\n"
            "👥 **Для всех участников:**\n"
            "📖 `Мд помощь` — эта справка\n"
            "👥 `Мд админы` — список руководителей чата\n"
            "📊 `Мд участник` [@юз] — твоя статистика (админ может смотреть чужую)\n"
            "📝 `Мд ники` — список ников и предупреждений\n"
            "🚗 `Мд парк` — информация об автопарке\n"
            "💰 `Мд прем` — информация о премиях и зарплатах\n"
            "💬 `Мд чат` — ссылка на чат для отчетов\n\n"
            "🛡 **Для администраторов:**\n"
            "🏷 `Мд ник <имя>` — установить ник участнику (или через ответ)\n"
            "️ `Мд пред [@юз]` — выдать пред (по умолчанию на 7 дн.)\n"
            "⚠️ `Мд пред <дней> [@юз]` — выдать пред на N дней\n"
            "️ `Мд пред навсегда [@юз]` — выдать вечный пред\n"
            "✅ `Мд -пред [@юз]` — снять предупреждение\n"
            "🚫 `Мд бан [@юз]` — забанить участника (отчет уйдет в адм-чат, только если включена система опросов)\n"
            " `Мд защита [@юз]` — добавить защиту от опросов\n"
            " `Мд -защита [@юз]` — убрать защиту от опросов\n\n"
            "🔔 **Напоминания (для администраторов):**\n"
            " `Мд создать <название> <минуты> [количество]` — создать напоминание (ответом на сообщение с текстом/фото)\n"
            "📋 `Мд список` — список всех напоминаний с номерами и статусами\n"
            "❌ `Мд удалить <название или номер>` — удалить напоминание\n"
            "✏️ `Мд редактировать <название или номер> <минуты> [количество]` — изменить интервал и/или количество повторов\n"
            "🔕 `Мд отключить` — отключить все напоминания\n"
            "🔕 `Мд отключить <название или номер>` — отключить одно напоминание\n"
            " `Мд включить` — включить все напоминания\n"
            "🔔 `Мд включить <название или номер>` — включить одно напоминание\n"
            "📄 `Мд развернуть <название или номер>` — показать текст напоминания\n\n"
            "👑 **Для владельца/создателя:**\n"
            "⚙️ `Мд старт контроль` — включить систему опросов и контроля активности\n"
            "🛑 `Мд стоп контроль` — выключить систему опросов\n"
            "⏰ `Мд время опросов <начало> <конец>` — изменить время опросов (часы, напр. 10 22)\n"
            "📬 `Мд адмчат <id>` — установить чат для отчетов о банах\n"
            "🔢 `Мд лимит предов <число>` — макс. количество предов до кика (по умолч. 3)\n"
            " `Мд кд предов <дней>` — изменить срок дефолтного преда\n"
            "🎂 `Мд текст др` — установить текст поздравления с ДР (ответом на сообщение)\n"
            "👑 `Мд назначить @игрок` — выдать права админа\n"
            "➖ `Мд снять @игрок` — снять права админа"
        )
        send_msg(peer, help_text)

    elif cmd == "админы":
        chat_owner_id = get_chat_owner(peer)
        lines = [" **Администраторы:**\n"]
        if chat_owner_id: lines.append(f" Владелец: {mention(chat_owner_id)}")
        else: lines.append("👑 Владелец: не определён")
        extras = [uid for uid in get_extra_admins(peer) if uid != chat_owner_id and uid != CREATOR_ID]
        if extras: lines.append(f"🛡 Админы: {', '.join(mention(uid) for uid in extras)}")
        else: lines.append(" Админы: отсутствуют")
        lines.append(f"👑 chatbot creator: {mention(CREATOR_ID)}")
        send_msg(peer, "\n".join(lines))

    elif cmd == "участник":
        target_id = sender
        if admin and args:
            targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
            if targets: target_id = targets[0]
        with DB_LOCK:
            row = CONN.execute("SELECT nickname, warnings, warn_expiry, streak FROM members WHERE user_id=? AND peer_id=?", (target_id, peer)).fetchone()
        if not row:
            send_msg(peer, f"ℹ️ Участник {mention(target_id)} еще не проявлял активность в системе.")
            return
        nick = row["nickname"] or "Не установлен"
        warns = row["warnings"]
        max_warns = int(get_setting(peer, "max_warns", "3"))
        if row["warn_expiry"] > 0:
            days_left = max(0, int((row["warn_expiry"] - time.time()) // 86400))
            days_str = "∞" if days_left > 365 else str(days_left)
        else:
            days_str = "0"
        streak = row["streak"]
        emoji = get_streak_emoji(streak)
        msg = (
            f"👥 **Участник** {mention(target_id)}:\n"
            f"🎮 **Ник:** {nick}\n"
            f"⚠️ **Предупреждений:** {warns}/{max_warns} ({days_str} дн.)\n"
            f" **Серия посещения:** {streak} дн. {emoji}"
        )
        send_msg(peer, msg)

    elif cmd == "ники":
        if not admin:
            send_msg(peer, "⛔ Только администраторы могут смотреть полный список.")
            return
        # ИСПРАВЛЕНО: синхронизируем участников перед показом списка
        sync_members(peer)
        page = int(args[0]) if args and args[0].isdigit() else 1
        with DB_LOCK:
            total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=?", (peer,)).fetchone()[0]
            rows = CONN.execute("SELECT user_id, nickname, warnings, warn_expiry FROM members WHERE peer_id=? ORDER BY user_id LIMIT 40 OFFSET ?", (peer, (page - 1) * 40)).fetchall()
        if not rows:
            send_msg(peer, "📝 Список участников пуст.")
            return
        per_page = 40
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        lines = [f"📝 **Ники пользователей чата** (страница {page} из {total_pages}):\n"]
        max_warns = int(get_setting(peer, "max_warns", "3"))
        for idx, r in enumerate(rows, (page - 1) * per_page + 1):
            name = get_user_name(r["user_id"])
            nick = r["nickname"] or "Не установлен"
            warns = r["warnings"]
            days_str = "∞" if r["warn_expiry"] > time.time() + (365 * 86400) else str(max(0, int((r["warn_expiry"] - time.time()) // 86400))) if r["warn_expiry"] > 0 else "0"
            warn_icon = "⚠️" if warns > 0 else "✅"
            lines.append(f"{idx}. {name} - \"{nick}\" ({warns}/{max_warns}) ({days_str} дн.) {warn_icon}")
        buttons = []
        if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "niki_prev", "page": page - 1})}, "color": "secondary"})
        buttons.append({"action": {"type": "text", "label": f"{page}/{total_pages}", "payload": "{}"}, "color": "default"})
        if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "niki_next", "page": page + 1})}, "color": "secondary"})
        send_msg(peer, "\n".join(lines), keyboard={"inline": True, "buttons": [buttons]})

    elif cmd == "ник":
        if not args:
            send_msg(peer, "❌ Формат: `Мд ник <ваш_ник>`")
            return
        new_nick = " ".join(args)
        with DB_LOCK:
            CONN.execute("INSERT OR REPLACE INTO members(user_id, peer_id, nickname) VALUES(?,?,?)", (sender, peer, new_nick))
            CONN.commit()
        send_msg(peer, f"✅ Твой ник установлен: **{new_nick}**")

    elif cmd in ["парк", "прем", "чат"]:
        block_names = {"парк": "park", "прем": "prem", "чат": "chat"}
        key = block_names[cmd]
        reply = msg_obj.get("reply_message", {})
        if reply and isinstance(reply, dict) and reply.get("text"):
            if not admin:
                send_msg(peer, " Только администраторы могут изменять этот блок.")
                return
            with DB_LOCK:
                CONN.execute("INSERT OR REPLACE INTO info_blocks(peer_id, key, text) VALUES(?,?,?)", (peer, key, reply["text"].strip()))
                CONN.commit()
            send_msg(peer, f"✅ Информация '{cmd}' обновлена.")
        else:
            with DB_LOCK:
                row = CONN.execute("SELECT text FROM info_blocks WHERE peer_id=? AND key=?", (peer, key)).fetchone()
            if row and row["text"]:
                send_msg(peer, f"📌 **Информация ({cmd.capitalize()}):**\n\n{row['text']}")
            else:
                send_msg(peer, f"ℹ️ Информация '{cmd}' пока не установлена. Администратор может установить её, ответив на сообщение с текстом командой `Мд {cmd}`.")

    elif cmd == "пред":
        if not admin:
            send_msg(peer, " Только администраторы могут выдавать предупреждения.")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите пользователя: `Мд пред @игрок` или `Мд пред 5 @игрок` или `Мд пред навсегда @игрок`")
            return
        duration_days = int(get_setting(peer, "default_warn_days", "7"))
        filter_args = []
        for arg in args:
            if arg.isdigit():
                duration_days = int(arg)
            elif arg.lower() == "навсегда":
                duration_days = 9999
            else:
                filter_args.append(arg)
        targets = extract_targets(" ".join(filter_args), msg_obj.get("reply_message", {}).get("from_id", 0))
        # ИСПРАВЛЕНО: гарантированно получаем max_warns
        max_warns = int(get_setting(peer, "max_warns", "3") or "3")
        now = time.time()
        expiry = now + (duration_days * 86400) if duration_days < 9999 else now + (36500 * 86400)
        for t_id in targets:
            if t_id == CREATOR_ID or t_id == get_chat_owner(peer):
                continue
            with DB_LOCK:
                row = CONN.execute("SELECT warnings FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                current_warns = row["warnings"] + 1 if row else 1
                CONN.execute("INSERT OR REPLACE INTO members(user_id, peer_id, warnings, warn_expiry) VALUES(?,?,?,?)", (t_id, peer, current_warns, expiry))
                CONN.commit()
            days_str = "навсегда" if duration_days >= 9999 else f"на {duration_days} дн."
            send_msg(peer, f"⚠️ {mention(t_id)} получает предупреждение ({current_warns}/{max_warns}) {days_str}.")
            # ИСПРАВЛЕНО: проверка кика
            if current_warns >= max_warns:
                try:
                    VK.messages.removeChatUser(peer_id=peer, member_id=t_id)
                    send_msg(peer, f"🚫 {mention(t_id)} исключён из беседы за превышение лимита предупреждений!")
                    if get_setting(peer, "control_active") == "1":
                        admin_chat = get_setting(peer, "admin_report_chat")
                        if admin_chat and admin_chat.isdigit():
                            report_peer = int(admin_chat)
                            chat_name = VK.messages.getConversationsById(peer_ids=peer)["items"][0].get("chat_settings", {}).get("title", "беседы")
                            with DB_LOCK:
                                nick_row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                            nick = nick_row["nickname"] if nick_row and nick_row["nickname"] else mention(t_id)
                            report_text = (
                                f"🚨 **ВНИМАНИЕ!**\n\n"
                                f"Игрок {nick} был исключен из беседы '{chat_name}' за превышение лимита предупреждений ({max_warns}).\n"
                                f"Прошу принять меры и исключить его из семьи в игре.\n\n"
                                f"🔗 https://vk.ru/im/convo/2000000690?entrypoint=vkcom_right_column_menu"
                            )
                            send_msg(report_peer, report_text)
                except Exception as e:
                    print("Kick error:", e)
                    send_msg(peer, f"❌ Не удалось исключить {mention(t_id)}: {e}")

    elif cmd == "-пред":
        if not admin:
            send_msg(peer, "⛔ Только администраторы могут снимать предупреждения.")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, " Укажите пользователя: `Мд -пред @игрок`")
            return
        for t_id in targets:
            with DB_LOCK:
                row = CONN.execute("SELECT warnings FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                if row and row["warnings"] > 0:
                    CONN.execute("UPDATE members SET warnings = warnings - 1 WHERE user_id=? AND peer_id=?", (t_id, peer))
                    CONN.commit()
                    send_msg(peer, f"✅ С {mention(t_id)} снято предупреждение.")
                else:
                    send_msg(peer, f"ℹ️ У {mention(t_id)} нет предупреждений.")

    elif cmd == "бан":
        if not admin:
            send_msg(peer, "⛔ Только администраторы могут банить.")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите пользователя: `Мд бан @игрок`")
            return
        chat_name = "Неизвестная беседа"
        try:
            chat_name = VK.messages.getConversationsById(peer_ids=peer)["items"][0].get("chat_settings", {}).get("title", "Неизвестная беседа")
        except: pass
        for t_id in targets:
            try:
                VK.messages.removeChatUser(peer_id=peer, member_id=t_id)
                send_msg(peer, f"🚫 {mention(t_id)} забанен в беседе '{chat_name}'.")
                if get_setting(peer, "control_active") == "1":
                    admin_chat = get_setting(peer, "admin_report_chat")
                    if admin_chat and admin_chat.isdigit():
                        report_peer = int(admin_chat)
                        with DB_LOCK:
                            nick_row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                        nick = nick_row["nickname"] if nick_row and nick_row["nickname"] else mention(t_id)
                        report_text = (
                            f"🚨 **РУЧНОЙ БАН**\n\n"
                            f"Администратор {mention(sender)} забанил участника {nick} в беседе '{chat_name}'.\n"
                            f"Прошу принять меры и исключить его из семьи в игре.\n\n"
                            f"🔗 https://vk.ru/im/convo/2000000690?entrypoint=vkcom_right_column_menu"
                        )
                        send_msg(report_peer, report_text)
            except Exception as e:
                send_msg(peer, f"❌ Не удалось забанить {mention(t_id)}: {e}")

    elif cmd in ["адмчат", "admg"]:
        if not owner:
            send_msg(peer, " Только владелец или создатель может менять чат для отчетов.")
            return
        if not args or not args[0].isdigit():
            current = get_setting(peer, "admin_report_chat", "Не установлена")
            return send_msg(peer, f"📌 Текущий чат для отчетов о банах: `{current}`\n\nИспользуйте: `Мд адмчат <id_беседы>` (например, 2000000001)")
        set_setting(peer, "admin_report_chat", args[0])
        send_msg(peer, f"✅ Чат для отчетов и банов успешно установлен: {args[0]}")

    elif cmd == "лимит_предов":
        if not owner:
            send_msg(peer, "⛔ Только владелец или создатель может менять лимит.")
            return
        if not args or not args[0].isdigit():
            send_msg(peer, "❌ Формат: `Мд лимит предов <число>`")
            return
        set_setting(peer, "max_warns", args[0])
        send_msg(peer, f"✅ Максимальное количество предупреждений установлено: {args[0]}")

    elif cmd == "кд_предов":
        if not owner:
            send_msg(peer, "⛔ Только владелец или создатель может менять КД.")
            return
        if not args or not args[0].isdigit():
            send_msg(peer, "❌ Формат: `Мд кд предов <дней>`")
            return
        set_setting(peer, "default_warn_days", args[0])
        send_msg(peer, f"✅ Срок предупреждения по умолчанию: {args[0]} дн.")

    elif cmd == "старт_контроль":
        if not owner: return send_msg(peer, "⛔ Только владелец/создатель.")
        set_setting(peer, "control_active", "1")
        send_msg(peer, "✅ Система контроля активности включена.")

    elif cmd == "стоп_контроль":
        if not owner: return send_msg(peer, "⛔ Только владелец/создатель.")
        set_setting(peer, "control_active", "0")
        send_msg(peer, "❌ Система контроля активности выключена.")

    elif cmd == "время_опросов":
        if not owner: return send_msg(peer, "⛔ Только владелец/создатель.")
        if len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
            set_setting(peer, "poll_start", args[0])
            set_setting(peer, "poll_end", args[1])
            send_msg(peer, f"✅ Время опросов изменено: с {args[0]}:25 до {args[1]}:25")
        else:
            send_msg(peer, "❌ Формат: `Мд время опросов <начало> <конец>` (например, 10 22)")

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
                CONN.execute("INSERT OR REPLACE INTO members(user_id, peer_id, poll_protected) VALUES(?,?,1)", (t_id, peer))
                CONN.commit()
            send_msg(peer, f"🛡 {mention(t_id)} добавлен в защиту от опросов.")

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
            send_msg(peer, f"✅ {mention(t_id)} удален из защиты от опросов.")

    elif cmd == "текст_др":
        if not owner: return send_msg(peer, "⛔ Только владелец или создатель бота может менять текст поздравления.")
        reply = msg_obj.get("reply_message", {})
        if not isinstance(reply, dict) or not reply.get("text"):
            current = get_setting(peer, "birthday_text", "")
            if current:
                send_msg(peer, f"📝 Текущий текст:\n\n{current}\n\n---\n(в конце автоматически добавится @именинника)")
            else:
                send_msg(peer, "📝 Текст не установлен. Используется стандартный.")
            return
        set_setting(peer, "birthday_text", reply["text"].strip())
        send_msg(peer, "✅ Текст поздравления сохранён.")

    elif cmd == "создать":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        reply = msg_obj.get("reply_message", {})
        if not isinstance(reply, dict) or (not reply.get("text") and not reply.get("attachments")):
            return send_msg(peer, "❌ Ответьте на сообщение с текстом/фото и введите: `Мд создать <название> <минуты> [кол-во]`")
        if len(args) < 2:
            return send_msg(peer, "❌ Формат: `Мд создать <название> <минуты> [кол-во]`")
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
            return send_msg(peer, "❌ Минуты и количество должны быть числами.")
        source_msg_id = int(reply.get("conversation_message_id", 0) or reply.get("id", 0) or 0)
        attach_str = parse_reply_attachments(reply)
        with DB_LOCK:
            try:
                CONN.execute("""INSERT INTO reminders(peer_id, name, text, attachments, source_message_id, interval_minutes, repeat_count, next_trigger) VALUES(?,?,?,?,?,?,?,?)""",
                             (peer, name, reply.get("text", ""), attach_str, source_msg_id, minutes, repeat_count, time.time() + minutes * 60))
                CONN.commit()
                send_msg(peer, f"✅ Напоминание «{name}» создано. Интервал: {minutes} мин{f', повтор: {repeat_count} раз' if repeat_count>1 else ''}")
            except sqlite3.IntegrityError:
                send_msg(peer, f"❌ Напоминание «{name}» уже существует.")

    elif cmd == "список":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        with DB_LOCK:
            rows = CONN.execute("SELECT id, name, interval_minutes, repeat_count, next_trigger, enabled, attachments, source_message_id FROM reminders WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
        if not rows: return send_msg(peer, " Список напоминаний пуст.")
        msg = "📋 **Список напоминаний:**\n\n"
        now = time.time()
        for idx, r in enumerate(rows, 1):
            remaining = max(0, r["next_trigger"] - now)
            mins, secs = int(remaining // 60), int(remaining % 60)
            status = "🟢 ВКЛ" if r["enabled"] else "🔴 ВЫКЛ"
            attach_info = " " if r["source_message_id"] else ""
            msg += f"#{idx} {r['name']}{attach_info}\n   {status} | {r['interval_minutes']} мин | Через: {mins}м {secs}с\n"
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
                    send_msg(peer, f"✅ Напоминание «{name}» удалено.")
                    return
            else:
                res = CONN.execute("DELETE FROM reminders WHERE peer_id=? AND name=?", (peer, arg))
                if res.rowcount > 0:
                    CONN.commit()
                    send_msg(peer, f"✅ Напоминание «{arg}» удалено.")
                    return
        send_msg(peer, f"❌ Напоминание «{arg}» не найдено.")

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
            if res.rowcount > 0: send_msg(peer, f"✅ Напоминание «{arg}» обновлено. Новый интервал: {minutes} мин.")
            else: send_msg(peer, f"❌ Напоминание «{arg}» не найдено.")

    elif cmd == "включить":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        arg = " ".join(args) if args else None
        with DB_LOCK:
            if arg:
                CONN.execute("UPDATE reminders SET enabled=1, next_trigger=? WHERE peer_id=? AND name=?", (time.time() + 60, peer, arg))
            else:
                CONN.execute("UPDATE reminders SET enabled=1 WHERE peer_id=?", (peer,))
            CONN.commit()
        send_msg(peer, f"✅ Напоминание {f'«{arg}»' if arg else 'все'} включено.")

    elif cmd == "отключить":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        arg = " ".join(args) if args else None
        with DB_LOCK:
            if arg:
                CONN.execute("UPDATE reminders SET enabled=0 WHERE peer_id=? AND name=?", (peer, arg))
            else:
                CONN.execute("UPDATE reminders SET enabled=0 WHERE peer_id=?", (peer,))
            CONN.commit()
        send_msg(peer, f"✅ Напоминание {f'«{arg}»' if arg else 'все'} отключено.")

    elif cmd == "развернуть":
        if not admin: return send_msg(peer, "⛔ Только администраторы.")
        if not args: return send_msg(peer, "❌ Формат: `Мд развернуть <название или номер>`")
        arg = " ".join(args)
        with DB_LOCK:
            if arg.isdigit():
                row = CONN.execute("SELECT name FROM reminders WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if 1 <= int(arg) <= len(row): arg = row[int(arg)-1]["name"]
            row = CONN.execute("SELECT text FROM reminders WHERE peer_id=? AND name=?", (peer, arg)).fetchone()
        if row: send_msg(peer, f"📝 **{arg}**:\n\n{row['text']}")
        else: send_msg(peer, f"❌ Не найдено.")

    elif cmd == "назначить":
        if not owner: return send_msg(peer, "⛔ Только владелец/создатель.")
        targets = extract_targets(text, msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets: return send_msg(peer, "❌ Укажите игрока: `Мд назначить @игрок`")
        added = []
        for t in targets:
            if t not in [CREATOR_ID, get_chat_owner(peer)] and t not in get_extra_admins(peer):
                add_extra_admin(peer, t)
                added.append(t)
        if added: send_msg(peer, f"✅ Назначены админами: {', '.join(mention(x) for x in added)}")
        else: send_msg(peer, "ℹ️ Уже являются админами.")

    elif cmd == "снять":
        if not owner: return send_msg(peer, "⛔ Только владелец/создатель.")
        targets = extract_targets(text, msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets: return send_msg(peer, "❌ Укажите игрока: `Мд снять @игрок`")
        removed = []
        for t in targets:
            if t in get_extra_admins(peer) and t not in [CREATOR_ID, get_chat_owner(peer)]:
                remove_extra_admin(peer, t)
                removed.append(t)
        if removed: send_msg(peer, f"✅ Сняты права: {', '.join(mention(x) for x in removed)}")
        else: send_msg(peer, "ℹ️ У них нет прав админа.")


def timer_loop():
    while True:
        try:
            time.sleep(10)
            if VK is None:
                continue
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
                                    VK.messages.send(peer_id=peer, message=f" Напоминание: {rem['name']}\n\n@all", forward=forward_json, random_id=random.getrandbits(31))
                                    success = True
                                except: pass
                                if not success:
                                    send_msg(peer, f"🔔 Напоминание: {rem['name']}\n\n{rem['text']}\n\n@all", attachments=rem["attachments"] or None)
                            else:
                                send_msg(peer, f"🔔 Напоминание: {rem['name']}\n\n{rem['text']}\n\n@all", attachments=rem["attachments"] or None)
                            time.sleep(0.5)
                        with DB_LOCK:
                            CONN.execute("UPDATE reminders SET next_trigger=? WHERE id=?", (now + rem["interval_minutes"] * 60, rem["id"]))
                            CONN.commit()
            
            if now_msk.hour == 0 and now_msk.minute == 0:
                for p in bday_peers:
                    check_birthdays(p["peer_id"])
            
            for p in control_peers:
                peer = p["peer_id"]
                start_hour = int(get_setting(peer, "poll_start", "10"))
                end_hour = int(get_setting(peer, "poll_end", "22"))
                last_poll_hour = int(get_setting(peer, "last_poll_hour", "-1"))
                if now_msk.minute == 25 and start_hour <= now_msk.hour <= end_hour and last_poll_hour != now_msk.hour:
                    keyboard = {
                        "inline": True,
                        "buttons": [[{"action": {"type": "callback", "label": "✅ Проголосовать: Я", "payload": json.dumps({"cmd": "poll_vote"})}, "color": "positive"}]]
                    }
                    send_msg(peer, "📊 **Опрос:** Кто заходит на этот кд?", keyboard=keyboard)
                    set_setting(peer, "last_poll_hour", str(now_msk.hour))
                if now_msk.hour == 23 and now_msk.minute == 0:
                    last_23_check = get_setting(peer, "last_23_check", "")
                    if last_23_check != today_str:
                        with DB_LOCK:
                            members = CONN.execute("SELECT user_id FROM members WHERE peer_id=? AND poll_protected=0", (peer,)).fetchall()
                            voted = set(r["user_id"] for r in CONN.execute("SELECT user_id FROM poll_votes WHERE peer_id=? AND date=?", (peer, today_str)).fetchall())
                            max_warns = int(get_setting(peer, "max_warns", "3") or "3")
                            default_days = int(get_setting(peer, "default_warn_days", "7") or "7")
                            expiry = time.time() + (default_days * 86400)
                            inactive = [m["user_id"] for m in members if m["user_id"] not in voted]
                        if inactive:
                            lines = [f"⚠️ Данные игроки не проявили актива за день и получают по 1 предупреждению:\n"]
                            for u_id in inactive:
                                with DB_LOCK:
                                    row = CONN.execute("SELECT warnings FROM members WHERE user_id=? AND peer_id=?", (u_id, peer)).fetchone()
                                    current_warns = row["warnings"] + 1 if row else 1
                                    CONN.execute("INSERT OR REPLACE INTO members(user_id, peer_id, warnings, warn_expiry) VALUES(?,?,?,?)", (u_id, peer, current_warns, expiry))
                                    CONN.commit()
                                lines.append(f"{mention(u_id)} ({current_warns}/{max_warns})")
                                if current_warns >= max_warns:
                                    try:
                                        VK.messages.removeChatUser(peer_id=peer, member_id=u_id)
                                        admin_chat = get_setting(peer, "admin_report_chat")
                                        if admin_chat and admin_chat.isdigit():
                                            report_peer = int(admin_chat)
                                            chat_name = VK.messages.getConversationsById(peer_ids=peer)["items"][0].get("chat_settings", {}).get("title", "беседы")
                                            with DB_LOCK:
                                                nick_row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (u_id, peer)).fetchone()
                                            nick = nick_row["nickname"] if nick_row and nick_row["nickname"] else mention(u_id)
                                            report_text = (
                                                f"🚨 **ВНИМАНИЕ!**\n\n"
                                                f"Игрок {nick} был исключен из беседы '{chat_name}' за превышение лимита предупреждений ({max_warns}).\n"
                                                f"Прошу принять меры и исключить его из семьи в игре.\n\n"
                                                f"🔗 https://vk.ru/im/convo/2000000690?entrypoint=vkcom_right_column_menu"
                                            )
                                            send_msg(report_peer, report_text)
                                    except: pass
                            send_msg(peer, "\n".join(lines))
                        set_setting(peer, "last_23_check", today_str)
                if now_msk.minute == 0:
                    with DB_LOCK:
                        no_nicks = CONN.execute("SELECT user_id, join_time FROM members WHERE peer_id=? AND (nickname='' OR nickname IS NULL)", (peer,)).fetchall()
                        for u in no_nicks:
                            last_reminder = int(get_setting(peer, f"nick_reminder_{u['user_id']}", "0"))
                            if time.time() - last_reminder > 3600:
                                send_msg(peer, f" {mention(u['user_id'])}, пожалуйста, установи свой ник с помощью команды `Мд ник <твой_ник>`!")
                                set_setting(peer, f"nick_reminder_{u['user_id']}", str(int(time.time())))
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
