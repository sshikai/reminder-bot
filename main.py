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

DATA_DIR = "/app/data" if os.path.isdir("/app/data") else os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DATA_DIR, "bot.db")
CONN = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
CONN.row_factory = sqlite3.Row
DB_LOCK = threading.Lock()
VK = None
NAME_CACHE = {}
OWNER_CACHE = {}
MEMBER_CACHE = {}
LAST_MEMBER_UPDATE = {}

DEFAULT_BIRTHDAY_TEXT = "Поздравляем {mention}. У него сегодня день рождения!🎂"

def init_db():
    with DB_LOCK:
        CONN.execute("""CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peer_id INTEGER,
            name TEXT,
            text TEXT,
            attachments TEXT,
            source_message_id INTEGER DEFAULT 0,
            interval_minutes INTEGER,
            repeat_count INTEGER DEFAULT 1,
            next_trigger REAL,
            enabled INTEGER DEFAULT 1,
            UNIQUE(peer_id, name))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS extra_admins (
            peer_id INTEGER,
            user_id INTEGER,
            UNIQUE(peer_id, user_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS settings (
            peer_id INTEGER,
            key TEXT,
            value TEXT,
            UNIQUE(peer_id, key))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS birthdays (
            user_id INTEGER,
            peer_id INTEGER,
            bdate TEXT,
            updated_at INTEGER,
            PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS birthday_congratulated (
            user_id INTEGER,
            peer_id INTEGER,
            year INTEGER,
            congratulated_at INTEGER,
            PRIMARY KEY(user_id, peer_id, year))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS birthday_text (
            peer_id INTEGER PRIMARY KEY,
            text TEXT)""")
        
        try:
            cols = [row[1] for row in CONN.execute("PRAGMA table_info(reminders)").fetchall()]
            if "attachments" not in cols:
                CONN.execute("ALTER TABLE reminders ADD COLUMN attachments TEXT")
            if "source_message_id" not in cols:
                CONN.execute("ALTER TABLE reminders ADD COLUMN source_message_id INTEGER DEFAULT 0")
            if "repeat_count" not in cols:
                CONN.execute("ALTER TABLE reminders ADD COLUMN repeat_count INTEGER DEFAULT 1")
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
        rows = CONN.execute("SELECT user_id FROM extra_admins WHERE peer_id=?", (peer,)).fetchall()
        return [int(r["user_id"]) for r in rows]

def add_extra_admin(peer, user_id):
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO extra_admins(peer_id, user_id) VALUES(?,?)", (peer, user_id))
        CONN.commit()

def remove_extra_admin(peer, user_id):
    with DB_LOCK:
        CONN.execute("DELETE FROM extra_admins WHERE peer_id=? AND user_id=?", (peer, user_id))
        CONN.commit()

def get_chat_owner(peer, force_refresh=False):
    if VK is None:
        return 0
    if not force_refresh and peer in OWNER_CACHE:
        return OWNER_CACHE[peer]
    
    oid = 0
    try:
        result = VK.messages.getConversationsById(peer_ids=peer)
        items = result.get("items", [])
        if items:
            conv = items[0].get("conversation", {})
            oid = conv.get("owner_id", 0)
            if not oid:
                chat_settings = conv.get("chat_settings", {})
                oid = chat_settings.get("owner_id", 0)
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
    
    if oid > 0:
        OWNER_CACHE[peer] = oid
    return oid

def is_admin(sender, peer):
    if sender <= 0:
        return False
    if sender == CREATOR_ID:
        return True
    owner = get_chat_owner(peer)
    if sender == owner:
        return True
    if sender in get_extra_admins(peer):
        return True
    return False

def is_owner(sender, peer):
    if sender <= 0:
        return False
    if sender == CREATOR_ID:
        return True
    return get_chat_owner(peer) == sender

def send_msg(peer, text, attachments=None, keyboard=None):
    if VK is None or not peer:
        return
    try:
        params = {
            'peer_id': peer,
            'message': text,
            'random_id': random.getrandbits(31)
        }
        if attachments:
            params['attachment'] = attachments
        if keyboard:
            params['keyboard'] = json.dumps(keyboard)
        VK.messages.send(**params)
    except Exception as e:
        print("send error:", e)

def forward_msg(peer, text, source_message_id):
    if VK is None or not peer or not source_message_id:
        return False
    try:
        forward_json = json.dumps({
            "peer_id": peer,
            "conversation_message_ids": [source_message_id]
        })
        VK.messages.send(
            peer_id=peer,
            message=text,
            forward=forward_json,
            random_id=random.getrandbits(31)
        )
        return True
    except Exception as e:
        print("forward error:", e)
        return False

def get_user_name(user_id):
    if user_id in NAME_CACHE:
        return NAME_CACHE[user_id]
    name = "Пользователь"
    try:
        r = VK.users.get(user_ids=user_id)
        if r:
            name = f"{r[0].get('first_name', '')} {r[0].get('last_name', '')}".strip() or "Пользователь"
    except Exception:
        pass
    NAME_CACHE[user_id] = name
    return name

def mention(user_id):
    return f"[id{user_id}|{get_user_name(user_id)}]"

def extract_targets(text, reply_from):
    ids = []
    for m in re.finditer(r"\[id(\d+)\|", text, re.I):
        ids.append(int(m.group(1)))
    for m in re.finditer(r"[@\*]id(\d+)", text, re.I):
        ids.append(int(m.group(1)))
    for m in re.finditer(r"\b(\d{5,})\b", text):
        ids.append(int(m.group(1)))
    seen, result = set(), []
    for v in ids:
        if v not in seen:
            seen.add(v)
            result.append(v)
    if not result and reply_from and reply_from > 0:
        result = [reply_from]
    return result

def norm(s):
    s = s.strip().lower()
    s = s.rstrip(".,;:!?")
    return re.sub(r"\s+", " ", s).strip()

def find_reminder(peer, arg):
    if not arg:
        return None
    arg = arg.strip()
    with DB_LOCK:
        if arg.isdigit():
            num = int(arg)
            rows = CONN.execute(
                "SELECT * FROM reminders WHERE peer_id=? ORDER BY id",
                (peer,)
            ).fetchall()
            if 1 <= num <= len(rows):
                return rows[num - 1]
            return None
        row = CONN.execute(
            "SELECT * FROM reminders WHERE peer_id=? AND name=?",
            (peer, arg)
        ).fetchone()
        return row

def parse_reply_attachments(reply_obj):
    if not reply_obj or not isinstance(reply_obj, dict):
        return ""
    attachments = reply_obj.get("attachments", []) or []
    parts = []
    for att in attachments:
        try:
            att_type = att.get("type", "")
            if att_type == "photo":
                ph = att.get("photo", {})
                owner_id = ph.get("owner_id", 0)
                photo_id = ph.get("id", 0)
                if owner_id and photo_id:
                    parts.append(f"photo{owner_id}_{photo_id}")
        except Exception as e:
            print("attach parse error:", e)
    return ",".join(parts)

# ===== ДНИ РОЖДЕНИЯ (СУПЕР-ОПТИМИЗИРОВАНО) =====
def update_birthdays(peer):
    now = int(time.time())
    
    if peer in MEMBER_CACHE and (now - LAST_MEMBER_UPDATE.get(peer, 0)) < 300:
        profiles = MEMBER_CACHE[peer]
    else:
        try:
            members_resp = VK.messages.getConversationMembers(peer_id=peer)
            profiles = members_resp.get("profiles", [])
            MEMBER_CACHE[peer] = profiles
            LAST_MEMBER_UPDATE[peer] = now
        except Exception as e:
            print(f"ERROR getting members for {peer}: {e}")
            return

    with DB_LOCK:
        existing = {row["user_id"]: row["updated_at"] for row in CONN.execute(
            "SELECT user_id, updated_at FROM birthdays WHERE peer_id=?", (peer,)
        ).fetchall()}

    users_to_check = []
    for profile in profiles:
        user_id = int(profile.get("id", 0))
        if user_id <= 0:
            continue
        last_update = existing.get(user_id, 0)
        if (now - last_update) >= 7 * 24 * 3600:
            users_to_check.append(user_id)

    if not users_to_check:
        return

    try:
        for i in range(0, len(users_to_check), 500):
            chunk = users_to_check[i:i+500]
            r = VK.users.get(user_ids=",".join(map(str, chunk)), fields="bdate")
            if r:
                with DB_LOCK:
                    for user_data in r:
                        uid = user_data.get("id")
                        bdate = user_data.get("bdate", "")
                        if bdate:
                            CONN.execute(
                                "INSERT OR REPLACE INTO birthdays(user_id, peer_id, bdate, updated_at) VALUES(?,?,?,?)",
                                (uid, peer, bdate, now)
                            )
                    CONN.commit()
    except Exception as e:
        print(f"ERROR fetching birthdays in batch: {e}")

def trigger_background_update(peer):
    threading.Thread(target=update_birthdays, args=(peer,), daemon=True).start()

def parse_bdate(bdate_str):
    parts = bdate_str.split(".")
    if len(parts) == 3:
        return int(parts[0]), int(parts[1]), int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]), int(parts[1]), None
    return None

def days_until_birthday(bdate_str):
    parsed = parse_bdate(bdate_str)
    if not parsed:
        return None
    
    day, month = parsed[0], parsed[1]
    today = time.localtime()
    current_year = today.tm_year
    
    try:
        bday_this_year = datetime.date(current_year, month, day)
        today_date = datetime.date(current_year, today.tm_mon, today.tm_mday)
        
        if bday_this_year >= today_date:
            return (bday_this_year - today_date).days
        else:
            bday_next_year = datetime.date(current_year + 1, month, day)
            return (bday_next_year - today_date).days
    except:
        return None

def is_birthday_today(bdate_str):
    parsed = parse_bdate(bdate_str)
    if not parsed:
        return False
    today = time.localtime()
    return today.tm_mday == parsed[0] and today.tm_mon == parsed[1]

def build_birthday_page(peer, page=1):
    with DB_LOCK:
        rows = [dict(r) for r in CONN.execute(
            "SELECT user_id, bdate FROM birthdays WHERE peer_id=? AND bdate IS NOT NULL",
            (peer,)).fetchall()]
    
    if not rows:
        return "🎂 Дни рождения не найдены (бот обновляет данные в фоне, попробуйте через минуту).", []
    
    birthday_list = []
    for r in rows:
        days = days_until_birthday(r["bdate"])
        if days is not None:
            birthday_list.append((r["user_id"], days))
    
    if not birthday_list:
        return "🎂 Дни рождения не найдены.", []
    
    birthday_list.sort(key=lambda x: x[1])
    
    per_page = 20
    total_pages = max(1, (len(birthday_list) + per_page - 1) // per_page)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    
    start = (page - 1) * per_page
    end = start + per_page
    page_items = birthday_list[start:end]
    
    lines = [f"🎂 Дни рождения участников (стр. {page}/{total_pages}):\n"]
    for user_id, days in page_items:
        name = get_user_name(user_id)
        if days == 0:
            days_str = "сегодня! 🎉"
        elif days == 1:
            days_str = "завтра"
        else:
            days_str = f"осталось {days} дн."
        lines.append(f"{name} — {days_str}")
    
    text = "\n".join(lines)
    
    buttons = []
    if page > 1:
        buttons.append({
            "action": {
                "type": "callback",
                "label": "⬅️Назад",
                "payload": json.dumps({"cmd": "bday_prev", "page": page - 1})
            },
            "color": "secondary"
        })
    if page < total_pages:
        buttons.append({
            "action": {
                "type": "callback",
                "label": "Вперёд➡️",
                "payload": json.dumps({"cmd": "bday_next", "page": page + 1})
            },
            "color": "secondary"
        })
    
    return text, buttons

def handle_birthday_button(event):
    """Мгновенная обработка кнопок с надежным fallback"""
    try:
        obj = event.obj
        if not isinstance(obj, dict):
            return
        
        peer_id = int(obj.get("peer_id", 0))
        user_id = int(obj.get("user_id", 0))
        conversation_message_id = int(obj.get("conversation_message_id", 0))
        
        event_data = obj.get("event_data", {})
        if isinstance(event_data, str):
            event_data = json.loads(event_data)
        
        payload = event_data.get("payload", {})
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        cmd = payload.get("cmd", "")
        if cmd not in ("bday_next", "bday_prev"):
            return
        
        if not is_admin(user_id, peer_id):
            VK.messages.sendMessageEventAnswer(
                event_id=obj.get("event_id"),
                user_id=user_id,
                peer_id=peer_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "🚫 Только для админов"})
            )
            return
        
        page = int(payload.get("page", 1))
        
        # Мгновенное чтение из БД (без API запросов!)
        with DB_LOCK:
            rows = [dict(r) for r in CONN.execute(
                "SELECT user_id, bdate FROM birthdays WHERE peer_id=? AND bdate IS NOT NULL",
                (peer_id,)).fetchall()]
        
        if not rows:
            text = "🎂 Дни рождения не найдены."
            buttons = []
        else:
            birthday_list = []
            for r in rows:
                days = days_until_birthday(r["bdate"])
                if days is not None:
                    birthday_list.append((r["user_id"], days))
            
            birthday_list.sort(key=lambda x: x[1])
            per_page = 20
            total_pages = max(1, (len(birthday_list) + per_page - 1) // per_page)
            if page < 1: page = 1
            if page > total_pages: page = total_pages
            
            start = (page - 1) * per_page
            end = start + per_page
            page_items = birthday_list[start:end]
            
            lines = [f"🎂 Дни рождения участников (стр. {page}/{total_pages}):\n"]
            for uid, days in page_items:
                name = get_user_name(uid)
                if days == 0: days_str = "сегодня! 🎉"
                elif days == 1: days_str = "завтра"
                else: days_str = f"осталось {days} дн."
                lines.append(f"{name} — {days_str}")
            
            text = "\n".join(lines)
            
            buttons = []
            if page > 1:
                buttons.append({"action": {"type": "callback", "label": "⬅️Назад", "payload": json.dumps({"cmd": "bday_prev", "page": page - 1})}, "color": "secondary"})
            if page < total_pages:
                buttons.append({"action": {"type": "callback", "label": "Вперёд➡️", "payload": json.dumps({"cmd": "bday_next", "page": page + 1})}, "color": "secondary"})
        
        keyboard = {"inline": True, "buttons": [buttons]} if buttons else {"inline": True, "buttons": []}
        
        # ИСПРАВЛЕНО: Правильный метод для получения ID сообщения
        global_msg_id = 0
        try:
            r = VK.messages.getByConversationMessageId(
                peer_id=peer_id,
                conversation_message_ids=str(conversation_message_id)
            )
            items = r.get("items", [])
            if items:
                global_msg_id = int(items[0].get("id", 0))
        except Exception as e:
            print("getByConvMsgId error:", e)
        
        success = False
        if global_msg_id > 0:
            try:
                VK.messages.edit(
                    peer_id=peer_id,
                    message_id=global_msg_id,
                    message=text,
                    keyboard=json.dumps(keyboard)
                )
                success = True
            except Exception as e:
                print("edit error:", e)
        
        # FALLBACK: Если редактирование не удалось, отправляем новое сообщение
        if not success:
            try:
                VK.messages.send(
                    peer_id=peer_id,
                    message=text + "\n\n(Не удалось обновить сообщение, отправлено новое)",
                    keyboard=json.dumps(keyboard),
                    random_id=random.getrandbits(31)
                )
            except Exception as e:
                print("send fallback error:", e)
        
        # Снимаем анимацию загрузки с кнопки в ЛЮБОМ случае
        VK.messages.sendMessageEventAnswer(
            event_id=obj.get("event_id"),
            user_id=user_id,
            peer_id=peer_id,
            event_data=json.dumps({"type": "show_snackbar", "text": f"📄 Страница {page}"})
        )
            
    except Exception as e:
        print("button handler error:", e)

def get_birthday_text(peer):
    with DB_LOCK:
        row = CONN.execute("SELECT text FROM birthday_text WHERE peer_id=?", (peer,)).fetchone()
        return row["text"] if row else None

def set_birthday_text(peer, text):
    with DB_LOCK:
        CONN.execute("INSERT OR REPLACE INTO birthday_text(peer_id, text) VALUES(?,?)", (peer, text))
        CONN.commit()

def build_birthday_congrats(peer, user_id):
    mention_str = mention(user_id)
    custom = get_birthday_text(peer)
    if custom:
        return custom.rstrip() + "\n\n" + mention_str
    else:
        return DEFAULT_BIRTHDAY_TEXT.format(mention=mention_str)

def check_birthdays(peer):
    today = time.localtime()
    current_year = today.tm_year
    
    with DB_LOCK:
        rows = [dict(r) for r in CONN.execute(
            "SELECT user_id, bdate FROM birthdays WHERE peer_id=? AND bdate IS NOT NULL",
            (peer,)).fetchall()]
    
    for r in rows:
        user_id = r["user_id"]
        bdate = r["bdate"]
        
        if not is_birthday_today(bdate):
            continue
        
        with DB_LOCK:
            row = CONN.execute(
                "SELECT congratulated_at FROM birthday_congratulated WHERE user_id=? AND peer_id=? AND year=?",
                (user_id, peer, current_year)).fetchone()
            if row:
                continue
        
        text = build_birthday_congrats(peer, user_id)
        send_msg(peer, text)
        
        with DB_LOCK:
            CONN.execute(
                "INSERT OR REPLACE INTO birthday_congratulated(user_id, peer_id, year, congratulated_at) VALUES(?,?,?,?)",
                (user_id, peer, current_year, int(time.time())))
            CONN.commit()

def handle_message(peer, sender, text, msg_obj):
    if peer < 2000000000:
        return

    first = norm(text.split("\n")[0])
    if not first or not first.startswith("!"):
        return

    cmd = first.split(" ", 1)[0]
    args_str = first[len(cmd):].strip()
    args = args_str.split() if args_str else []

    if not is_admin(sender, peer):
        send_msg(peer, "⛔ Эта команда доступна только администраторам.")
        return

    owner = is_owner(sender, peer)

    if cmd == "!создать":
        try:
            reply = msg_obj.get("reply_message") or {}
            if not isinstance(reply, dict):
                reply = {}
            reply_text = (reply.get("text") or "").strip()
            reply_attachments_str = parse_reply_attachments(reply)
            source_message_id = int(reply.get("conversation_message_id", 0) or reply.get("id", 0) or 0)
            
            if not reply_text and not reply_attachments_str and not source_message_id:
                send_msg(peer, "❌ Ответьте на сообщение с текстом или фото и введите !создать <название> <минуты> [количество]")
                return
            if len(args) < 2:
                send_msg(peer, "❌ Формат: !создать <название> <минуты> [количество]")
                return
            
            repeat_count = 1
            try:
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
            
            with DB_LOCK:
                try:
                    CONN.execute("""INSERT INTO reminders(peer_id, name, text, attachments, source_message_id, interval_minutes, repeat_count, next_trigger) 
                                    VALUES(?,?,?,?,?,?,?,?)""",
                                 (peer, name, reply_text, reply_attachments_str, source_message_id, minutes, repeat_count, time.time() + minutes * 60))
                    CONN.commit()
                    repeat_info = f", повтор: {repeat_count} раз" if repeat_count > 1 else ""
                    if source_message_id:
                        send_msg(peer, f"✅ Напоминание «{name}» создано. Интервал: {minutes} мин{repeat_info} (будет пересылать сообщение)")
                    else:
                        attach_info = " + вложения" if reply_attachments_str else ""
                        send_msg(peer, f"✅ Напоминание «{name}» создано. Интервал: {minutes} мин{repeat_info}{attach_info}")
                except sqlite3.IntegrityError:
                    send_msg(peer, f"❌ Напоминание «{name}» уже существует.")
        except Exception as e:
            print("create error:", e)
            send_msg(peer, f"❌ Ошибка при создании напоминания: {e}")

    elif cmd == "!список":
        with DB_LOCK:
            rows = CONN.execute(
                "SELECT id, name, interval_minutes, repeat_count, next_trigger, enabled, attachments, source_message_id FROM reminders WHERE peer_id=? ORDER BY id",
                (peer,)
            ).fetchall()
        if not rows:
            send_msg(peer, "📭 Список напоминаний пуст.")
            return
        msg = "📋 Список напоминаний:\n\n"
        now = time.time()
        for idx, r in enumerate(rows, 1):
            remaining = max(0, r["next_trigger"] - now)
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            status = "🟢 ВКЛЮЧЕНО" if r["enabled"] else "🔴 ОТКЛЮЧЕНО"
            if r["source_message_id"]:
                attach_info = " 📎 пересылка"
            else:
                attach_count = len(r["attachments"].split(",")) if r["attachments"] else 0
                attach_info = f" + {attach_count} влож." if attach_count else ""
            repeat_info = f", повтор: {r['repeat_count']} раз" if r["repeat_count"] > 1 else ""
            msg += f"#{idx} {r['name']}{attach_info}{repeat_info}\n"
            msg += f"   {status}\n"
            msg += f"   Интервал: {r['interval_minutes']} мин.\n"
            msg += f"   Через: {mins} мин {secs} сек\n\n"
        send_msg(peer, msg)

    elif cmd == "!удалить":
        if not args:
            send_msg(peer, "❌ Формат: !удалить <название или номер>")
            return
        arg = " ".join(args)
        rem = find_reminder(peer, arg)
        if not rem:
            send_msg(peer, f"❌ Напоминание «{arg}» не найдено.")
            return
        with DB_LOCK:
            CONN.execute("DELETE FROM reminders WHERE id=?", (rem["id"],))
            CONN.commit()
        send_msg(peer, f"✅ Напоминание «{rem['name']}» удалено.")

    elif cmd == "!редактировать":
        if len(args) < 2:
            send_msg(peer, "❌ Формат: !редактировать <название или номер> <минуты> [количество]")
            return
        try:
            repeat_count = None
            if len(args) >= 3 and args[-1].isdigit():
                repeat_count = int(args[-1])
                minutes = int(args[-2])
                arg = " ".join(args[:-2])
            else:
                minutes = int(args[-1])
                arg = " ".join(args[:-1])
        except ValueError:
            send_msg(peer, "❌ Минуты и количество должны быть числами.")
            return
        rem = find_reminder(peer, arg)
        if not rem:
            send_msg(peer, f"❌ Напоминание «{arg}» не найдено.")
            return
        with DB_LOCK:
            if repeat_count is not None:
                CONN.execute("""UPDATE reminders SET interval_minutes=?, repeat_count=?, next_trigger=? WHERE id=?""",
                             (minutes, repeat_count, time.time() + minutes * 60, rem["id"]))
            else:
                CONN.execute("""UPDATE reminders SET interval_minutes=?, next_trigger=? WHERE id=?""",
                             (minutes, time.time() + minutes * 60, rem["id"]))
            CONN.commit()
        repeat_info = f", повтор: {repeat_count} раз" if repeat_count else ""
        send_msg(peer, f"✅ Напоминание «{rem['name']}» обновлено. Новый интервал: {minutes} мин{repeat_info}.")

    elif cmd == "!отключить":
        if not args:
            with DB_LOCK:
                CONN.execute("UPDATE reminders SET enabled=0 WHERE peer_id=?", (peer,))
                CONN.commit()
            send_msg(peer, "🔕 Все напоминания отключены.")
        else:
            arg = " ".join(args)
            rem = find_reminder(peer, arg)
            if not rem:
                send_msg(peer, f"❌ Напоминание «{arg}» не найдено.")
                return
            with DB_LOCK:
                CONN.execute("UPDATE reminders SET enabled=0 WHERE id=?", (rem["id"],))
                CONN.commit()
            send_msg(peer, f"🔕 Напоминание «{rem['name']}» отключено.")

    elif cmd == "!включить":
        if not args:
            now = time.time()
            with DB_LOCK:
                rows = CONN.execute("SELECT id, interval_minutes, next_trigger FROM reminders WHERE peer_id=?", (peer,)).fetchall()
                for r in rows:
                    if r["next_trigger"] < now:
                        new_trigger = now + r["interval_minutes"] * 60
                        CONN.execute("UPDATE reminders SET next_trigger=? WHERE id=?", (new_trigger, r["id"]))
                CONN.execute("UPDATE reminders SET enabled=1 WHERE peer_id=?", (peer,))
                CONN.commit()
            send_msg(peer, "🔔 Все напоминания включены.")
        else:
            arg = " ".join(args)
            rem = find_reminder(peer, arg)
            if not rem:
                send_msg(peer, f"❌ Напоминание «{arg}» не найдено.")
                return
            now = time.time()
            new_trigger = now + rem["interval_minutes"] * 60
            with DB_LOCK:
                CONN.execute("UPDATE reminders SET enabled=1, next_trigger=? WHERE id=?", (new_trigger, rem["id"]))
                CONN.commit()
            send_msg(peer, f"🔔 Напоминание «{rem['name']}» включено.")

    elif cmd == "!развернуть":
        if not args:
            send_msg(peer, "❌ Формат: !развернуть <название или номер>")
            return
        arg = " ".join(args)
        rem = find_reminder(peer, arg)
        if not rem:
            send_msg(peer, f"❌ Напоминание «{arg}» не найдено.")
            return
        if rem["source_message_id"]:
            success = forward_msg(peer, f"📝 Текст напоминания «{rem['name']}»:", rem["source_message_id"])
            if not success:
                send_msg(peer, f"📝 Текст напоминания «{rem['name']}»:\n\n{rem['text']}")
        else:
            send_msg(peer, f"📝 Текст напоминания «{rem['name']}»:\n\n{rem['text']}")

    elif cmd == "!помощь":
        help_text = (
            "📖 Команды MD BOT:\n\n"
            "!создать <название> <минуты> [количество] — создать напоминание (ответом на сообщение)\n"
            "!список — список всех напоминаний с номерами и статусами\n"
            "!удалить <название или номер> — удалить напоминание\n"
            "!редактировать <название или номер> <минуты> [количество] — изменить интервал\n"
            "!отключить — отключить все напоминания\n"
            "!отключить <название или номер> — отключить одно напоминание\n"
            "!включить — включить все напоминания\n"
            "!включить <название или номер> — включить одно напоминание\n"
            "!развернуть <название или номер> — показать текст напоминания\n"
            "!др — дни рождения участников (кнопки листают страницы)\n"
            "!админы — список руководителей чата\n"
            "!обновить_владельца — обновить информацию о владельце чата\n"
            "!помощь — эта справка\n\n"
            "🛡 Команды владельца/создателя:\n"
            "!назначить @игрок — выдать права админа\n"
            "!снять @игрок — снять права админа\n"
            "!текст_др — установить/посмотреть текст поздравления с ДР\n\n"
            "💡 Во всех командах вместо названия можно указывать номер из !список.\n"
            "📎 Бот пересылает оригинальное сообщение (сохраняет фото и вложения)!\n"
            "🔁 Параметр 'количество' указывает, сколько раз отправить напоминание за раз.\n"
            "⚠️ Все команды доступны только администраторам."
        )
        send_msg(peer, help_text)

    elif cmd == "!др":
        trigger_background_update(peer)
        page = 1
        if args and args[0].isdigit():
            page = int(args[0])
        try:
            text, buttons = build_birthday_page(peer, page)
            if buttons:
                keyboard = {"inline": True, "buttons": [buttons]}
                VK.messages.send(
                    peer_id=peer,
                    message=text,
                    keyboard=json.dumps(keyboard),
                    random_id=random.getrandbits(31)
                )
            else:
                send_msg(peer, text)
        except Exception as e:
            print("birthday error:", e)
            send_msg(peer, f"❌ Ошибка при показе дней рождения: {e}")

    elif cmd == "!текст_др":
        reply = msg_obj.get("reply_message") or {}
        if not isinstance(reply, dict):
            reply = {}
        reply_text = (reply.get("text") or "").strip()
        
        if not reply_text:
            current = get_birthday_text(peer)
            if current:
                send_msg(peer, f"📝 Текущий текст поздравления в этой беседе:\n\n{current}\n\n---\n(в конце автоматически добавится @именинника)")
            else:
                send_msg(peer, "📝 Текст поздравления не установлен. Используется стандартный:\n\nПоздравляем @именинника. У него сегодня день рождения!🎂\n\n💡 Чтобы установить свой текст — напиши его в чат, ответь на него и напиши !текст_др")
            return
        
        set_birthday_text(peer, reply_text)
        send_msg(peer, f"✅ Текст поздравления сохранён для этой беседы.\n\nПример того, как будет выглядеть:\n\n{reply_text}\n\n[Имя Фамилия именинника]\n\n💡 Чтобы изменить — ответь на новый текст и снова напиши !текст_др")

    elif cmd == "!назначить":
        if not owner:
            send_msg(peer, "⛔ Эту команду может использовать только создатель бота или владелец чата.")
            return
        targets = extract_targets(text, None)
        if not targets:
            send_msg(peer, "❌ Укажите игрока: !назначить @игрок")
            return
        chat_owner_id = get_chat_owner(peer)
        added = []
        for t in targets:
            if t == CREATOR_ID or t == chat_owner_id or t in get_extra_admins(peer):
                continue
            add_extra_admin(peer, t)
            added.append(t)
        if added:
            names = ", ".join(mention(x) for x in added)
            send_msg(peer, f"✅ Назначены админами: {names}")
        else:
            send_msg(peer, "ℹ️ Эти игроки уже являются администраторами.")

    elif cmd == "!снять":
        if not owner:
            send_msg(peer, "⛔ Эту команду может использовать только создатель бота или владелец чата.")
            return
        targets = extract_targets(text, None)
        if not targets:
            send_msg(peer, "❌ Укажите игрока: !снять @игрок")
            return
        chat_owner_id = get_chat_owner(peer)
        removed = []
        protected = 0
        for t in targets:
            if t == CREATOR_ID or t == chat_owner_id:
                protected += 1
                continue
            if t in get_extra_admins(peer):
                remove_extra_admin(peer, t)
                removed.append(t)
        parts = []
        if removed:
            parts.append(f"✅ Сняты права админа: {', '.join(mention(x) for x in removed)}")
        if protected:
            parts.append("⚠️ Нельзя снять права с создателя или владельца чата.")
        if not parts:
            parts.append("ℹ️ У этих игроков нет прав админа.")
        send_msg(peer, "\n".join(parts))

    elif cmd == "!админы":
        chat_owner_id = get_chat_owner(peer, force_refresh=True)
        lines = ["👥 Администраторы:\n"]
        if chat_owner_id:
            lines.append(f"👑 Владелец: {mention(chat_owner_id)}")
        else:
            lines.append("👑 Владелец: не определён")
        extras = [uid for uid in get_extra_admins(peer) if uid != chat_owner_id and uid != CREATOR_ID]
        if extras:
            lines.append("🛡 Админы: " + ", ".join(mention(uid) for uid in extras))
        else:
            lines.append("🛡 Админы: отсутствуют")
        lines.append(f"👑 chatbot creator: {mention(CREATOR_ID)}")
        send_msg(peer, "\n".join(lines))

    elif cmd == "!обновить_владельца":
        if peer in OWNER_CACHE:
            del OWNER_CACHE[peer]
        chat_owner_id = get_chat_owner(peer, force_refresh=True)
        if chat_owner_id:
            send_msg(peer, f"✅ Владелец чата обновлён: {mention(chat_owner_id)}")
        else:
            send_msg(peer, "❌ Не удалось определить владельца чата. Убедитесь, что бот — администратор беседы.")


def timer_loop():
    while True:
        try:
            time.sleep(10)
            if VK is None:
                continue
            
            with DB_LOCK:
                peers = CONN.execute("SELECT DISTINCT peer_id FROM reminders").fetchall()
                bday_peers = CONN.execute("SELECT DISTINCT peer_id FROM birthdays").fetchall()
            
            for p in peers:
                peer = p["peer_id"]
                now = time.time()
                
                with DB_LOCK:
                    due = CONN.execute(
                        "SELECT id, name, text, attachments, source_message_id, interval_minutes, repeat_count, enabled FROM reminders WHERE peer_id=? AND next_trigger<=?",
                        (peer, now)
                    ).fetchall()
                
                for rem in due:
                    if rem["enabled"] == 1:
                        repeat_count = rem["repeat_count"] or 1
                        for _ in range(repeat_count):
                            if rem["source_message_id"]:
                                success = forward_msg(peer, f"🔔 Напоминание: {rem['name']}\n\n@all", rem["source_message_id"])
                                if not success:
                                    msg = f"🔔 Напоминание: {rem['name']}\n\n{rem['text']}\n\n@all"
                                    send_msg(peer, msg, attachments=rem["attachments"] or None)
                            else:
                                msg = f"🔔 Напоминание: {rem['name']}\n\n{rem['text']}\n\n@all"
                                send_msg(peer, msg, attachments=rem["attachments"] or None)
                            time.sleep(0.5)
                    
                    new_trigger = now + rem["interval_minutes"] * 60
                    with DB_LOCK:
                        CONN.execute("UPDATE reminders SET next_trigger=? WHERE id=?", (new_trigger, rem["id"]))
                        CONN.commit()
            
            for p in bday_peers:
                peer = p["peer_id"]
                last_bday_check = int(get_setting(peer, "last_birthday_check", "0") or 0)
                now = time.time()
                if now - last_bday_check >= 3600:
                    check_birthdays(peer)
                    set_setting(peer, "last_birthday_check", str(int(now)))
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
                    handle_birthday_button(event)
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
