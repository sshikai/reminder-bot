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

# ИСПРАВЛЕНО: Заменено на RLock (Reentrant Lock), чтобы избежать deadlock 
# при вызове get_setting() внутри блока with DB_LOCK:
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
    "помощь", "админы", "участник", "ники", "ник", "парк", "прем", "чат",
    "пред", "-пред", "лимит_предов", "кд_предов", "старт_контроль", "стоп_контроль",
    "время_опросов", "защита", "-защита", "бан", "адмчат", "admg", "номер_чата",
    "текст_др", "создать", "список", "удалить", "редактировать", "включить", "отключить", "развернуть",
    "назначить", "снять", "голоса", "тишина", "тишина_офф"
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
            warn_durations TEXT DEFAULT '', warn_expiry INTEGER DEFAULT 0, last_active TEXT DEFAULT '', 
            streak INTEGER DEFAULT 0, poll_protected INTEGER DEFAULT 0, join_time INTEGER DEFAULT 0, 
            last_vote_time INTEGER DEFAULT 0, last_vote_warn_time INTEGER DEFAULT 0, PRIMARY KEY(user_id, peer_id))""")
        
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
            "ALTER TABLE members ADD COLUMN last_vote_warn_time INTEGER DEFAULT 0"
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

# ИСПРАВЛЕНО: sync_members теперь удаляет из базы тех, кого больше нет в чате
def sync_members(peer):
    now = time.time()
    if peer in MEMBER_SYNC_CACHE and (now - MEMBER_SYNC_CACHE[peer]) < 300:
        return
    try:
        members_resp = VK.messages.getConversationMembers(peer_id=peer)
        profiles = members_resp.get("profiles", [])
        today = get_msk_now().strftime("%Y-%m-%d")
        
        # Собираем ID всех текущих участников чата
        current_members = set()
        for profile in profiles:
            user_id = int(profile.get("id", 0))
            if user_id > 0:
                current_members.add(user_id)
        
        with DB_LOCK:
            # Добавляем новых участников
            for user_id in current_members:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id, last_active, streak) VALUES(?,?,?,?)", 
                             (user_id, peer, today, 0))
            
            # Удаляем из базы тех, кого больше нет в чате
            all_db_members = CONN.execute("SELECT user_id FROM members WHERE peer_id=?", (peer,)).fetchall()
            for row in all_db_members:
                if row["user_id"] not in current_members:
                    CONN.execute("DELETE FROM members WHERE user_id=? AND peer_id=?", (row["user_id"], peer))
            
            CONN.commit()
        MEMBER_SYNC_CACHE[peer] = now
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
    if streak >= 40: return "🤑"
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

def handle_event(event):
    try:
        obj = event.object if hasattr(event, 'object') else event.obj
        if not isinstance(obj, dict):
            return
        event_id = obj.get("event_id")
        user_id = int(obj.get("user_id", 0))
        peer_id = int(obj.get("peer_id", 0))
        payload = obj.get("payload", "{}")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except:
                payload = {}
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
                    existing_vote = CONN.execute(
                        "SELECT 1 FROM poll_votes WHERE user_id=? AND peer_id=? AND poll_time=?", 
                        (user_id, peer_id, payload_time)
                    ).fetchone()
                    
                    if existing_vote:
                        snackbar_text = "⚠️ Вы уже голосовали в этом опросе!"
                        VK.messages.sendMessageEventAnswer(
                            event_id=event_id, user_id=user_id, peer_id=peer_id,
                            event_data=json.dumps({"type": "show_snackbar", "text": snackbar_text})
                        )
                    else:
                        mem_row = CONN.execute("SELECT last_vote_time FROM members WHERE user_id=? AND peer_id=?", (user_id, peer_id)).fetchone()
                        last_vote = mem_row["last_vote_time"] if mem_row and mem_row["last_vote_time"] else 0
                        
                        if (now_ts - last_vote) < 3600:
                            remaining_mins = (3600 - (now_ts - last_vote)) // 60
                            snackbar_text = f"⏳ КД на голосование: осталось {remaining_mins}м"
                            VK.messages.sendMessageEventAnswer(
                                event_id=event_id, user_id=user_id, peer_id=peer_id,
                                event_data=json.dumps({"type": "show_snackbar", "text": snackbar_text})
                            )
                        else:
                            CONN.execute("INSERT INTO poll_votes(user_id, peer_id, poll_time, date) VALUES(?,?,?,?)", (user_id, peer_id, payload_time, today_str))
                            CONN.execute("UPDATE members SET last_vote_time=? WHERE user_id=? AND peer_id=?", (now_ts, user_id, peer_id))
                            CONN.commit()
                            
                            send_msg(peer_id, f"✅ {mention(user_id)} Зайдет на этот кд!")
                            
                            VK.messages.sendMessageEventAnswer(
                                event_id=event_id, user_id=user_id, peer_id=peer_id,
                                event_data=json.dumps({"type": "show_snackbar", "text": "✅ Ты отметился!"})
                            )
            except Exception as e:
                print(f"DB error in poll_vote: {e}")
                VK.messages.sendMessageEventAnswer(
                    event_id=event_id, user_id=user_id, peer_id=peer_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "❌ Ошибка базы данных!"})
                )
            return

        if cmd == "page_info":
            page = payload.get("page", 1)
            total = payload.get("total", 1)
            VK.messages.sendMessageEventAnswer(
                event_id=event_id, user_id=user_id, peer_id=peer_id,
                event_data=json.dumps({"type": "show_snackbar", "text": f"📄 Страница {page} из {total}"})
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
                    NAME_CACHE[u["id"]] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or "Пользователь"
            except Exception as e:
                print("Batch name fetch error:", e)
            
            lines = [f"📝 Ники пользователей чата (страница {page} из {total_pages}):\n"]
            max_warns = int(get_setting(peer_id, "max_warns", "3") or "3")
            for idx, r in enumerate(rows, (page - 1) * per_page + 1):
                name = get_user_name(r["user_id"])
                nick = r["nickname"] or "Не установлен"
                warns = r["warnings"] or 0
                durations = r["warn_durations"] or "0"
                warn_icon = "⚠️" if warns > 0 else "✅"
                lines.append(f"{idx}. {name} - \"{nick}\" ({warns}/{max_warns}) ({durations} дн.) {warn_icon}")
            
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "niki_prev", "page": page - 1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": f"{page}/{total_pages}", "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "niki_next", "page": page + 1})}, "color": "secondary"})
            
            keyboard_json = json.dumps({"inline": True, "buttons": [buttons]})
            
            conversation_message_id = obj.get("conversation_message_id")
            
            if conversation_message_id:
                try:
                    VK.messages.edit(
                        peer_id=peer_id,
                        conversation_message_id=conversation_message_id,
                        message="\n".join(lines),
                        keyboard=keyboard_json
                    )
                except Exception as e:
                    print(f"Edit error: {e}")
                    VK.messages.send(
                        peer_id=peer_id, 
                        message="\n".join(lines) + "\n\n(Не удалось обновить сообщение, отправлено новое)", 
                        keyboard=keyboard_json, 
                        random_id=random.getrandbits(31)
                    )
            else:
                VK.messages.send(
                    peer_id=peer_id, 
                    message="\n".join(lines), 
                    keyboard=keyboard_json, 
                    random_id=random.getrandbits(31)
                )
            
            try:
                VK.messages.sendMessageEventAnswer(
                    event_id=event_id, user_id=user_id, peer_id=peer_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": f"📄 Страница {page}"})
                )
            except Exception as e:
                print("Event answer error:", e)
    except Exception as e:
        print("event error:", e)


def handle_message(peer, sender, text, msg_obj):
    clean_text = text.strip()
    
    if clean_text.lower() in ["!!чаты", "!!тест"]:
        if int(sender) != CREATOR_ID:
            return 
        
        send_msg(CREATOR_ID, "⏳ Загрузка списка бесед...")
        with DB_LOCK:
            peers_members = [row["peer_id"] for row in CONN.execute("SELECT DISTINCT peer_id FROM members").fetchall()]
            peers_reminders = [row["peer_id"] for row in CONN.execute("SELECT DISTINCT peer_id FROM reminders").fetchall()]
            peers = list(set(peers_members + peers_reminders))
        
        if not peers:
            send_msg(CREATOR_ID, "📭 Бот пока не зафиксировал ни одной беседы в базе (таблицы пусты).")
        else:
            lines = ["📊 Список бесед с ботом:\n"]
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
        if not user_id: return
        
        with DB_LOCK:
            row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
            if row:
                CONN.execute("""UPDATE members SET join_time=?, warnings=0, warn_durations='', warn_expiry=0 
                                WHERE user_id=? AND peer_id=?""", (int(time.time()), user_id, peer))
            else:
                CONN.execute("""INSERT INTO members(user_id, peer_id, join_time, warnings, warn_durations, warn_expiry) 
                                VALUES(?,?,?,0,'',0)""", (user_id, peer, int(time.time())))
            CONN.commit()
        
        if get_setting(peer, "control_active") == "1":
            send_msg(peer, f"Добро пожаловать, {mention(user_id)}! 🎉\nПожалуйста, установи свой ник с помощью команды:\n`Мд ник <твой_ник>`")
        return

    # ИСПРАВЛЕНО: Обработка события кика/выхода из чата вручную
    if action.get("type") == "chat_kick_user":
        user_id = action.get("member_id")
        if user_id:
            with DB_LOCK:
                CONN.execute("DELETE FROM members WHERE user_id=? AND peer_id=?", (user_id, peer))
                CONN.commit()
            print(f"User {user_id} kicked from peer {peer}, removed from DB")
            return

    # ПРОВЕРКА РЕЖИМА ТИШИНЫ
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
            "📖 Команды MD BOT\n\n"
            "👥 Для всех участников:\n"
            "`Мд помощь` — эта справка\n"
            "`Мд админы` — список руководителей чата\n"
            "`Мд участник` [@юз] — твоя статистика (админ может смотреть чужую)\n"
            "`Мд ники` — список ников и предупреждений\n"
            "`Мд парк` — информация об автопарке\n"
            "`Мд прем` — информация о премиях и зарплатах\n"
            "`Мд чат` — ссылка на чат для отчетов\n\n"
            "🛡 Для администраторов:\n"
            "`Мд ник` <имя> — установить ник участнику (или через ответ)\n"
            "`Мд ник` @юзер <имя> — установить ник другому участнику\n"
            "`Мд номер чата` — узнать ID текущего чата и создателя\n"
            "`Мд пред` [@юз] — выдать пред (по умолчанию на 7 дн.)\n"
            "`Мд пред` <дней> [@юз] — выдать пред на N дней\n"
            "`Мд пред` навсегда [@юз] — выдать вечный пред\n"
            "`Мд -пред` [@юз] — снять предупреждение\n"
            "`Мд бан` [@юз] — забанить участника (отчет уйдет в адм-чат)\n"
            "`Мд голоса` — посмотреть, кто проголосовал сегодня\n"
            "`Мд голоса вчера` — посмотреть голоса за вчера\n"
            "`Мд защита` [@юз] — добавить защиту от опросов\n"
            "`Мд -защита` [@юз] — убрать защиту от опросов\n\n"
            "🔔 Напоминания (для администраторов):\n"
            "`Мд создать` <название> <минуты> [количество] — создать напоминание (ответом на сообщение)\n"
            "`Мд список` — список всех напоминаний с номерами и статусами\n"
            "`Мд удалить` <название или номер> — удалить напоминание\n"
            "`Мд редактировать` <название или номер> <минуты> [кол-во] — изменить интервал\n"
            "`Мд отключить` — отключить все напоминания\n"
            "`Мд отключить` <название или номер> — отключить одно напоминание\n"
            "`Мд включить` — включить все напоминания\n"
            "`Мд включить` <название или номер> — включить одно напоминание\n"
            "`Мд развернуть` <название или номер> — показать текст напоминания\n\n"
            "👑 Для владельца/создателя:\n"
            "`Мд старт контроль` — включить систему опросов и контроля\n"
            "`Мд стоп контроль` — выключить систему опросов\n"
            "`Мд время опросов` <ЧЧ:ММ> <ЧЧ:ММ> — время опросов (напр. 10:20 23:20)\n"
            "`Мд адмчат` <id> — установить чат для отчетов о банах\n"
            "`Мд лимит предов` <число> — макс. количество предов до кика (по умолч. 3)\n"
            "`Мд кд предов` <дней> — изменить срок дефолтного преда\n"
            "`Мд текст др` — установить текст поздравления с ДР\n"
            "`Мд назначить` @игрок — выдать права админа\n"
            "`Мд снять` @игрок — снять права админа\n"
            "`Мд тишина` — запретить писать всем, кроме админов\n"
            "`Мд тишина офф` — разрешить писать всем"
        )
        send_msg(peer, help_text)

    elif cmd == "админы":
        chat_owner_id = get_chat_owner(peer)
        lines = ["👥 Администраторы:\n"]
        if chat_owner_id: lines.append(f"👑 Владелец: {mention(chat_owner_id)}")
        else: lines.append("👑 Владелец: не определён")
        extras = [uid for uid in get_extra_admins(peer) if uid != chat_owner_id and uid != CREATOR_ID]
        if extras: lines.append(f"🛡 Админы: {', '.join(mention(uid) for uid in extras)}")
        else: lines.append("🛡 Админы: отсутствуют")
        lines.append(f"👑 chatbot creator: {mention(CREATOR_ID)}")
        send_msg(peer, "\n".join(lines))

    elif cmd == "участник":
        target_id = sender
        if admin and args:
            targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
            if targets: target_id = targets[0]
        with DB_LOCK:
            row = CONN.execute("SELECT nickname, warnings, warn_durations, warn_expiry, streak FROM members WHERE user_id=? AND peer_id=?", (target_id, peer)).fetchone()
        if not row:
            send_msg(peer, f"ℹ️ Участник {mention(target_id)} еще не проявлял активность в системе.")
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
        msg = (
            f"👥 Участник {mention(target_id)}:\n"
            f"🎮 Ник: {nick}\n"
            f"⚠️ Предупреждений: {warns}/{max_warns} ({durations} дн.)\n"
            f"🔥 Серия посещения: {streak} дн. {emoji}"
        )
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
                    NAME_CACHE[u["id"]] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or "Пользователь"
            except Exception as e:
                print("Batch name fetch error:", e)
                
            per_page = 40
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = max(1, min(page, total_pages))
            lines = [f"📝 Ники пользователей чата (страница {page} из {total_pages}):\n"]
            max_warns = int(get_setting(peer, "max_warns", "3") or "3")
            for idx, r in enumerate(rows, (page - 1) * per_page + 1):
                name = get_user_name(r["user_id"])
                nick = r["nickname"] or "Не установлен"
                warns = r["warnings"] or 0
                durations = r["warn_durations"] or "0"
                warn_icon = "⚠️" if warns > 0 else "✅"
                lines.append(f"{idx}. {name} - \"{nick}\" ({warns}/{max_warns}) ({durations} дн.) {warn_icon}")
            
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "niki_prev", "page": page - 1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": f"{page}/{total_pages}", "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "niki_next", "page": page + 1})}, "color": "secondary"})
            
            keyboard_json = json.dumps({"inline": True, "buttons": [buttons]})
            
            VK.messages.send(
                peer_id=peer, 
                message="\n".join(lines), 
                keyboard=keyboard_json, 
                random_id=random.getrandbits(31)
            )
        except Exception as e:
            print("НИКИ ERROR:", e)
            send_msg(peer, f"❌ Произошла ошибка при выполнении команды 'Мд ники': {e}")

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
                CONN.execute("INSERT OR REPLACE INTO members(user_id, peer_id, nickname) VALUES(?,?,?)", (target_id, peer, new_nick))
                CONN.commit()
            send_msg(peer, f"✅ Ник {mention(target_id)} установлен: **{new_nick}**")
        else:
            new_nick = " ".join(args)
            with DB_LOCK:
                CONN.execute("INSERT OR REPLACE INTO members(user_id, peer_id, nickname) VALUES(?,?,?)", (sender, peer, new_nick))
                CONN.commit()
            send_msg(peer, f"✅ Твой ник установлен: **{new_nick}**")

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
                    SELECT user_id, COUNT(*) as count 
                    FROM poll_votes 
                    WHERE peer_id=? AND date=? 
                    GROUP BY user_id 
                    ORDER BY count DESC
                """, (peer, target_date)).fetchall()
            
            if not rows:
                send_msg(peer, f"🗳 {day_name.capitalize()} ({target_date}) никто не голосовал.")
                return
            
            lines = [f"🗳 Голоса за {day_name} ({target_date}):\n"]
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
                            cooldown_text = f" (КД: {remaining_mins}м)"
                
                lines.append(f"• {mention(r['user_id'])} — {count} раз(а){cooldown_text}")
            send_msg(peer, "\n".join(lines))
        except Exception as e:
            print(f"Error in голоса command: {e}")
            send_msg(peer, f"❌ Ошибка при выполнении команды: {e}")

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
            send_msg(peer, f"✅ Информация '{cmd}' обновлена.")
        else:
            with DB_LOCK:
                row = CONN.execute("SELECT text FROM info_blocks WHERE peer_id=? AND key=?", (peer, key)).fetchone()
            if row and row["text"]:
                send_msg(peer, f"📌 Информация ({cmd.capitalize()}):\n\n{row['text']}")
            else:
                send_msg(peer, f"ℹ️ Информация '{cmd}' пока не установлена. Администратор может установить её, ответив на сообщение с текстом командой `Мд {cmd}`.")

    elif cmd == "пред":
        if not admin:
            send_msg(peer, "⛔ Только администраторы могут выдавать предупреждения.")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите пользователя: `Мд пред @игрок` или `Мд пред 5 @игрок` или `Мд пред навсегда @игрок`")
            return
        duration_days = int(get_setting(peer, "default_warn_days", "7") or "7")
        filter_args = []
        for arg in args:
            if arg.isdigit():
                duration_days = int(arg)
            elif arg.lower() == "навсегда":
                duration_days = 9999
            else:
                filter_args.append(arg)
        targets = extract_targets(" ".join(filter_args), msg_obj.get("reply_message", {}).get("from_id", 0))
        max_warns = int(get_setting(peer, "max_warns", "3") or "3")
        now = time.time()
        expiry = now + (duration_days * 86400) if duration_days < 9999 else now + (36500 * 86400)
        
        for t_id in targets:
            if t_id == CREATOR_ID or t_id == get_chat_owner(peer):
                continue
            
            days_str = "∞" if duration_days >= 9999 else str(duration_days)
            with DB_LOCK:
                row = CONN.execute("SELECT warnings, warn_durations FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                if row:
                    current_warns = (row["warnings"] or 0) + 1
                    old_durations = row["warn_durations"] or ""
                    new_durations = f"{old_durations}|{days_str}" if old_durations else days_str
                    CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=? WHERE user_id=? AND peer_id=?", 
                                 (current_warns, new_durations, expiry, t_id, peer))
                else:
                    current_warns = 1
                    new_durations = days_str
                    CONN.execute("INSERT INTO members(user_id, peer_id, warnings, warn_durations, warn_expiry) VALUES(?,?,?,?,?)",
                                 (t_id, peer, current_warns, new_durations, expiry))
            
            send_msg(peer, f"⚠️ {mention(t_id)} получает предупреждение ({current_warns}/{max_warns}) ({new_durations} дн.).")
            
            if current_warns >= max_warns:
                try:
                    chat_id = peer - 2000000000
                    
                    with DB_LOCK:
                        nick_row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                    nick = nick_row["nickname"] if nick_row and nick_row["nickname"] else mention(t_id)
                    
                    VK.messages.removeChatUser(chat_id=chat_id, member_id=t_id)
                    
                    with DB_LOCK:
                        CONN.execute("UPDATE members SET warnings=0, warn_durations='', warn_expiry=0 WHERE user_id=? AND peer_id=?", (t_id, peer))
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
                            f"🚨 **ПРИВЕТСТВУЮ, АДМИНИСТРАТОРЫ!** 😀\n\n"
                            f"Игрок {mention(t_id)} ({nick}) был исключен из беседы '{chat_name}'.\n"
                            f"Прошу принять меры и исключить его из семьи в игре. 👊"
                        )
                        try:
                            send_msg(report_peer, report_text)
                            print(f"Отчет о кике успешно отправлен в чат {report_peer}")
                            send_msg(peer, f"✅ Игрок {mention(t_id)} исключен. Отчет отправлен в адм-чат.")
                        except Exception as e:
                            print(f"Ошибка отправки отчета в {report_peer}: {e}")
                            send_msg(peer, f"⚠️ Игрок {mention(t_id)} исключен, но **не удалось** отправить отчет в адм-чат ({report_peer}). Ошибка: {e}")
                    else:
                        print(f"Адм-чат не настроен или некорректен: '{admin_chat_raw}'")
                        send_msg(peer, f"⚠️ Игрок {mention(t_id)} исключен, но **адм-чат не настроен** или ID некорректен ('{admin_chat_raw}'). Используйте `Мд адмчат <id>`")
                except Exception as e:
                    print("Kick error:", e)
                    send_msg(peer, f"❌ Не удалось исключить {mention(t_id)}: {e}")

    elif cmd == "-пред":
        if not admin:
            send_msg(peer, "⛔ Только администраторы могут снимать предупреждения.")
            return
        targets = extract_targets(" ".join(args), msg_obj.get("reply_message", {}).get("from_id", 0))
        if not targets:
            send_msg(peer, "❌ Укажите пользователя: `Мд -пред @игрок`")
            return
        for t_id in targets:
            with DB_LOCK:
                row = CONN.execute("SELECT warnings, warn_durations FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                if row and row["warnings"] > 0:
                    new_warns = row["warnings"] - 1
                    old_durations = row["warn_durations"] or ""
                    parts = old_durations.split("|")
                    if parts:
                        parts.pop()
                    new_durations = "|".join(parts)
                    new_expiry = 0 if new_warns == 0 else row["warn_expiry"]
                    
                    CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=? WHERE user_id=? AND peer_id=?",
                                 (new_warns, new_durations, new_expiry, t_id, peer))
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
                
                with DB_LOCK:
                    CONN.execute("UPDATE members SET warnings=0, warn_durations='', warn_expiry=0 WHERE user_id=? AND peer_id=?", (t_id, peer))
                    CONN.commit()
                
                admin_chat_raw = get_setting(peer, "admin_report_chat", "")
                admin_chat_clean = "".join(filter(str.isdigit, str(admin_chat_raw)))
                
                if len(admin_chat_clean) >= 9:
                    report_peer = int(admin_chat_clean)
                    report_text = (
                        f"🚨 **ПРИВЕТСТВУЮ, АДМИНИСТРАТОРЫ!** 😀\n\n"
                        f"Игрок {mention(t_id)} ({nick}) был исключен из беседы '{chat_name}'.\n"
                        f"Прошу принять меры и исключить его из семьи в игре. 👊"
                    )
                    try:
                        send_msg(report_peer, report_text)
                        print(f"Отчет о бане успешно отправлен в чат {report_peer}")
                        send_msg(peer, f"✅ Игрок {mention(t_id)} забанен. Отчет отправлен в адм-чат.")
                    except Exception as e:
                        print(f"Ошибка отправки отчета в {report_peer}: {e}")
                        send_msg(peer, f"⚠️ Игрок {mention(t_id)} забанен, но **не удалось** отправить отчет в адм-чат ({report_peer}). Ошибка: {e}")
                else:
                    print(f"Адм-чат не настроен или некорректен: '{admin_chat_raw}'")
                    send_msg(peer, f"⚠️ Игрок {mention(t_id)} забанен, но **адм-чат не настроен** или ID некорректен ('{admin_chat_raw}'). Используйте `Мд адмчат <id>`")
            except Exception as e:
                send_msg(peer, f"❌ Не удалось забанить {mention(t_id)}: {e}")

    elif cmd in ["адмчат", "admg"]:
        if not owner:
            send_msg(peer, "⛔ Только владелец или создатель может менять чат для отчетов.")
            return
        if not args or not args[0].isdigit():
            current = get_setting(peer, "admin_report_chat", "Не установлена")
            return send_msg(peer, f"📌 Текущий чат для отчетов: `{current}`\n\nИспользуйте: `Мд адмчат <id_беседы>`")
        
        target_chat = int(args[0])
        set_setting(peer, "admin_report_chat", str(target_chat))
        
        test_text = f"✅ Отчеты о банах из чата {peer} теперь будут отправляться сюда."
        try:
            send_msg(target_chat, test_text)
            send_msg(peer, f"✅ Репорты из чата {peer} будут отправляться в чат {target_chat}. (Тестовое сообщение отправлено)")
        except Exception as e:
            send_msg(peer, f"⚠️ Настройка сохранена, но не удалось отправить тестовое сообщение в чат {target_chat}. Проверьте, что бот там есть и имеет права. Ошибка: {e}")

    elif cmd == "номер_чата":
        if not admin:
            send_msg(peer, "⛔ Только администраторы могут использовать эту команду.")
            return
        chat_owner_id = get_chat_owner(peer)
        owner_name = mention(chat_owner_id) if chat_owner_id else "Не определён"
        send_msg(peer, f"📌 Номер чата: {peer}\nСоздатель: {owner_name}")

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
        if len(args) >= 2:
            try:
                start_h, start_m = map(int, args[0].split(":"))
                end_h, end_m = map(int, args[1].split(":"))
                if start_m != end_m:
                    return send_msg(peer, "❌ Минуты начала и конца опроса должны совпадать (например, 10:20 23:20).")
                set_setting(peer, "poll_start", str(start_h))
                set_setting(peer, "poll_end", str(end_h))
                set_setting(peer, "poll_minute", str(start_m))
                send_msg(peer, f"✅ Время опросов изменено: каждый час в {start_m} минут, с {start_h}:00 до {end_h}:00")
            except ValueError:
                send_msg(peer, "❌ Формат: `Мд время опросов ЧЧ:ММ ЧЧ:ММ` (например, 10:20 23:20)")
        else:
            send_msg(peer, "❌ Формат: `Мд время опросов ЧЧ:ММ ЧЧ:ММ` (например, 10:20 23:20)")

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
        if not rows: return send_msg(peer, "📭 Список напоминаний пуст.")
        msg = "📋 Список напоминаний:\n\n"
        now = time.time()
        for idx, r in enumerate(rows, 1):
            remaining = max(0, r["next_trigger"] - now)
            mins, secs = int(remaining // 60), int(remaining % 60)
            status = "🟢 ВКЛ" if r["enabled"] else "🔴 ВЫКЛ"
            attach_info = " 📎" if r["source_message_id"] else ""
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
        if row: send_msg(peer, f"📝 {arg}:\n\n{row['text']}")
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

    elif cmd == "тишина":
        if not owner: return send_msg(peer, "⛔ Только владелец/создатель.")
        set_setting(peer, "silence_mode", "1")
        send_msg(peer, "🔇 Режим тишины включен. Теперь писать могут только администраторы.")

    elif cmd == "тишина_офф":
        if not owner: return send_msg(peer, "⛔ Только владелец/создатель.")
        set_setting(peer, "silence_mode", "0")
        send_msg(peer, "🔊 Режим тишины выключен. Все могут писать.")


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
                                    VK.messages.send(peer_id=peer, message=f"🔔 Напоминание: {rem['name']}\n\n@all", forward=forward_json, random_id=random.getrandbits(31))
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
                
                last_poll_msg_id = get_setting(peer, "last_poll_msg_id", "")
                last_poll_time_str = get_setting(peer, "last_poll_time", "0")
                last_poll_time = int(last_poll_time_str) if last_poll_time_str.isdigit() else 0
                
                if last_poll_msg_id and last_poll_msg_id.isdigit() and (time.time() - last_poll_time) > 600:
                    try:
                        VK.messages.delete(peer_id=peer, message_ids=[int(last_poll_msg_id)], delete_for_all=1)
                    except Exception as e:
                        print(f"Не удалось удалить опрос: {e}")
                    set_setting(peer, "last_poll_msg_id", "")
                    set_setting(peer, "last_poll_time", "0")
            
            if now_msk.hour == 0 and now_msk.minute == 0:
                for p in bday_peers:
                    check_birthdays(p["peer_id"])
            
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
                    last_poll_key = f"last_poll_{current_hour}_{poll_minute}"
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
                            print(f"Ошибка отправки опроса: {e}")
                
                if now_msk.hour == 23 and now_msk.minute == 0:
                    last_23_check = get_setting(peer, "last_23_check", "")
                    if last_23_check != today_str:
                        admins = set(get_extra_admins(peer))
                        admins.add(CREATOR_ID)
                        chat_owner = get_chat_owner(peer)
                        if chat_owner:
                            admins.add(chat_owner)
                        
                        with DB_LOCK:
                            members = CONN.execute("SELECT user_id FROM members WHERE peer_id=? AND poll_protected=0", (peer,)).fetchall()
                            voted = set(r["user_id"] for r in CONN.execute("SELECT user_id FROM poll_votes WHERE peer_id=? AND date=?", (peer, today_str)).fetchall())
                            max_warns = int(get_setting(peer, "max_warns", "3") or "3")
                            default_days = int(get_setting(peer, "default_warn_days", "7") or "7")
                            expiry = time.time() + (default_days * 86400)
                            inactive = [m["user_id"] for m in members if m["user_id"] not in voted and m["user_id"] not in admins]
                        if inactive:
                            lines = [f"⚠️ Данные игроки не проявили актива за день и получают по 1 предупреждению:\n"]
                            for u_id in inactive:
                                with DB_LOCK:
                                    row = CONN.execute("SELECT warnings, warn_durations FROM members WHERE user_id=? AND peer_id=?", (u_id, peer)).fetchone()
                                    current_warns = (row["warnings"] or 0) + 1 if row else 1
                                    old_durations = row["warn_durations"] if row and row["warn_durations"] else ""
                                    days_str = "∞" if default_days >= 9999 else str(default_days)
                                    new_durations = f"{old_durations}|{days_str}" if old_durations else days_str
                                    
                                    CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=? WHERE user_id=? AND peer_id=?",
                                                 (current_warns, new_durations, expiry, u_id, peer))
                                    CONN.commit()
                                lines.append(f"{mention(u_id)} ({current_warns}/{max_warns}) ({new_durations} дн.)")
                                
                                if current_warns >= max_warns:
                                    try:
                                        chat_id = peer - 2000000000
                                        
                                        with DB_LOCK:
                                            nick_row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (u_id, peer)).fetchone()
                                        nick = nick_row["nickname"] if nick_row and nick_row["nickname"] else mention(u_id)
                                        
                                        VK.messages.removeChatUser(chat_id=chat_id, member_id=u_id)
                                        
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
                                                f"🚨 **ПРИВЕТСТВУЮ, АДМИНИСТРАТОРЫ!** 😀\n\n"
                                                f"Игрок {mention(u_id)} ({nick}) был исключен из беседы '{chat_name}'.\n"
                                                f"Прошу принять меры и исключить его из семьи в игре. 👊"
                                            )
                                            try:
                                                send_msg(report_peer, report_text)
                                            except Exception as e:
                                                print(f"Error sending auto-kick report to {report_peer}: {e}")
                                    except Exception as e:
                                        print("Auto-kick error:", e)
                            send_msg(peer, "\n".join(lines))
                        set_setting(peer, "last_23_check", today_str)
                if now_msk.minute == 0:
                    with DB_LOCK:
                        no_nicks = CONN.execute("SELECT user_id, join_time FROM members WHERE peer_id=? AND (nickname='' OR nickname IS NULL)", (peer,)).fetchall()
                        for u in no_nicks:
                            last_reminder = int(get_setting(peer, f"nick_reminder_{u['user_id']}", "0"))
                            if time.time() - last_reminder > 3600:
                                send_msg(peer, f"🔔 {mention(u['user_id'])}, пожалуйста, установи свой ник с помощью команды `Мд ник <твой_ник>`!")
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
