import os
import re
import time
import random
import sqlite3
import threading
import json
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

def init_db():
    with DB_LOCK:
        CONN.execute("""CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peer_id INTEGER,
            name TEXT,
            text TEXT,
            attachments TEXT,
            interval_minutes INTEGER,
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

def get_chat_owner(peer):
    if VK is None:
        return 0
    if peer in OWNER_CACHE:
        return OWNER_CACHE[peer]
    oid = 0
    try:
        r = VK.messages.getConversationsById(peer_ids=peer)
        items = r.get("items", [])
        if items:
            cs = items[0].get("conversation", {}).get("chat_settings", {})
            oid = int(cs.get("owner_id", 0) or 0)
    except Exception as e:
        print("owner error:", e)
    OWNER_CACHE[peer] = oid
    return oid

def is_admin(sender, peer):
    if sender <= 0:
        return False
    if sender == CREATOR_ID:
        return True
    if sender == get_chat_owner(peer):
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

def send_msg(peer, text, attachments=None):
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
        VK.messages.send(**params)
    except Exception as e:
        print("send error:", e)

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

def handle_message(peer, sender, text, reply_from, reply_text, reply_attachments):
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

    # ----- !создать -----
    if cmd == "!создать":
        if not reply_text and not reply_attachments:
            send_msg(peer, "❌ Ответьте на сообщение с текстом или вложением и введите !создать <название> <минуты>")
            return
        if len(args) < 2:
            send_msg(peer, "❌ Формат: !создать <название> <минуты>")
            return
        try:
            minutes = int(args[-1])
            name = " ".join(args[:-1])
        except ValueError:
            send_msg(peer, "❌ Минуты должны быть числом.")
            return
        
        # Сохраняем вложения как JSON
        attachments_json = json.dumps(reply_attachments) if reply_attachments else ""
        
        with DB_LOCK:
            try:
                CONN.execute("""INSERT INTO reminders(peer_id, name, text, attachments, interval_minutes, next_trigger) 
                                VALUES(?,?,?,?,?,?)""",
                             (peer, name, reply_text, attachments_json, minutes, time.time() + minutes * 60))
                CONN.commit()
                attach_info = f" + {len(reply_attachments)} влож." if reply_attachments else ""
                send_msg(peer, f"✅ Напоминание «{name}» создано. Интервал: {minutes} мин.{attach_info}")
            except sqlite3.IntegrityError:
                send_msg(peer, f"❌ Напоминание «{name}» уже существует.")

    # ----- !список -----
    elif cmd == "!список":
        with DB_LOCK:
            rows = CONN.execute(
                "SELECT id, name, interval_minutes, next_trigger, enabled, attachments FROM reminders WHERE peer_id=? ORDER BY id",
                (peer,)
            ).fetchall()
        if not rows:
            send_msg(peer, "📭 Список напоминаний пуст.")
            return
        msg = " Список напоминаний:\n\n"
        now = time.time()
        for r in rows:
            remaining = max(0, r["next_trigger"] - now)
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            status = " ВКЛЮЧЕНО" if r["enabled"] else "🔴 ОТКЛЮЧЕНО"
            attach_count = len(json.loads(r["attachments"])) if r["attachments"] else 0
            attach_info = f" + {attach_count} влож." if attach_count else ""
            msg += f"#{idx} {r['name']}{attach_info}\n"
            msg += f"   {status}\n"
            msg += f"   Интервал: {r['interval_minutes']} мин.\n"
            msg += f"   Через: {mins} мин {secs} сек\n\n"
        send_msg(peer, msg)

    # ----- !удалить -----
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

    # ----- !редактировать -----
    elif cmd == "!редактировать":
        if len(args) < 2:
            send_msg(peer, "❌ Формат: !редактировать <название или номер> <минуты>")
            return
        try:
            minutes = int(args[-1])
            arg = " ".join(args[:-1])
        except ValueError:
            send_msg(peer, "❌ Минуты должны быть числом.")
            return
        rem = find_reminder(peer, arg)
        if not rem:
            send_msg(peer, f"❌ Напоминание «{arg}» не найдено.")
            return
        with DB_LOCK:
            CONN.execute("""UPDATE reminders SET interval_minutes=?, next_trigger=? WHERE id=?""",
                         (minutes, time.time() + minutes * 60, rem["id"]))
            CONN.commit()
        send_msg(peer, f"✅ Напоминание «{rem['name']}» обновлено. Новый интервал: {minutes} мин.")

    # ----- !отключить -----
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

    # ----- !включить -----
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

    # ----- !развернуть -----
    elif cmd == "!развернуть":
        if not args:
            send_msg(peer, "❌ Формат: !развернуть <название или номер>")
            return
        arg = " ".join(args)
        rem = find_reminder(peer, arg)
        if not rem:
            send_msg(peer, f"❌ Напоминание «{arg}» не найдено.")
            return
        send_msg(peer, f" Текст напоминания «{rem['name']}»:\n\n{rem['text']}")

    # ----- !помощь -----
    elif cmd == "!помощь":
        help_text = (
            "📖 Команды MD BOT:\n\n"
            "!создать <название> <минуты> — создать напоминание (ответом на сообщение с текстом/фото)\n"
            "!список — список всех напоминаний с номерами и статусами\n"
            "!удалить <название или номер> — удалить напоминание\n"
            "!редактировать <название или номер> <минуты> — изменить интервал\n"
            "!отключить — отключить все напоминания\n"
            "!отключить <название или номер> — отключить одно напоминание\n"
            "!включить — включить все напоминания\n"
            "!включить <название или номер> — включить одно напоминание\n"
            "!развернуть <название или номер> — показать текст напоминания\n"
            "!админы — список руководителей чата\n"
            "!помощь — эта справка\n\n"
            "🛡 Команды владельца/создателя:\n"
            "!назначить @игрок — выдать права админа\n"
            "!снять @игрок — снять права админа\n\n"
            "💡 Во всех командах вместо названия можно указывать номер из !список.\n"
            " Бот сохраняет фото и другие вложения из сообщений!\n"
            "⚠️ Все команды доступны только администраторам."
        )
        send_msg(peer, help_text)

    # ----- !назначить -----
    elif cmd == "!назначить":
        if not owner:
            send_msg(peer, "⛔ Эту команду может использовать только создатель бота или владелец чата.")
            return
        targets = extract_targets(text, reply_from)
        if not targets:
            send_msg(peer, "❌ Укажите игрока: !назначить @игрок (или ответом на сообщение).")
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

    # ----- !снять -----
    elif cmd == "!снять":
        if not owner:
            send_msg(peer, " Эту команду может использовать только создатель бота или владелец чата.")
            return
        targets = extract_targets(text, reply_from)
        if not targets:
            send_msg(peer, " Укажите игрока: !снять @игрок (или ответом на сообщение).")
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
            parts.append("️ У этих игроков нет прав админа.")
        send_msg(peer, "\n".join(parts))

    # ----- !админы -----
    elif cmd == "!админы":
        chat_owner_id = get_chat_owner(peer)
        lines = [" Администраторы:\n"]
        if chat_owner_id:
            lines.append(f" Владелец чата: {mention(chat_owner_id)}")
        lines.append(f" Создатель: {mention(CREATOR_ID)}")
        extras = [uid for uid in get_extra_admins(peer) if uid != chat_owner_id and uid != CREATOR_ID]
        if extras:
            lines.append("🛡 Админы: " + ", ".join(mention(uid) for uid in extras))
        else:
            lines.append("🛡 Админы: отсутствуют")
        send_msg(peer, "\n".join(lines))


def timer_loop():
    while True:
        try:
            time.sleep(10)
            if VK is None:
                continue
            
            with DB_LOCK:
                peers = CONN.execute("SELECT DISTINCT peer_id FROM reminders").fetchall()
            
            for p in peers:
                peer = p["peer_id"]
                now = time.time()
                
                with DB_LOCK:
                    due = CONN.execute(
                        "SELECT id, name, text, attachments, interval_minutes, enabled FROM reminders WHERE peer_id=? AND next_trigger<=?",
                        (peer, now)
                    ).fetchall()
                
                for rem in due:
                    if rem["enabled"] == 1:
                        msg = f"🔔 Напоминание: {rem['name']}\n\n{rem['text']}\n\n@all"
                        
                        # Отправляем вложения если есть
                        attachments = rem["attachments"]
                        if attachments:
                            try:
                                attach_list = json.loads(attachments)
                                # Преобразуем вложения в формат VK API
                                attach_str = ",".join(f"{att['type']}{att['owner_id']}_{att['id']}" for att in attach_list)
                                send_msg(peer, msg, attachments=attach_str)
                            except Exception as e:
                                print("attachment error:", e)
                                send_msg(peer, msg)
                        else:
                            send_msg(peer, msg)
                    
                    new_trigger = now + rem["interval_minutes"] * 60
                    with DB_LOCK:
                        CONN.execute("UPDATE reminders SET next_trigger=? WHERE id=?", (new_trigger, rem["id"]))
                        CONN.commit()
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
                if event.type != VkBotEventType.MESSAGE_NEW:
                    continue
                try:
                    obj = event.obj
                    msg = obj.get("message", obj) if isinstance(obj, dict) else {}
                    peer = int(msg.get("peer_id", 0) or 0)
                    sender = int(msg.get("from_id", 0) or 0)
                    txt = (msg.get("text") or "").strip()
                    reply = msg.get("reply_message") or {}
                    reply_from = int(reply.get("from_id", 0) or 0) if isinstance(reply, dict) else 0
                    reply_text = (reply.get("text") or "").strip() if isinstance(reply, dict) else ""
                    reply_attachments = reply.get("attachments", []) if isinstance(reply, dict) else []
                    if peer > 0 and sender > 0:
                        handle_message(peer, sender, txt, reply_from, reply_text, reply_attachments)
                except Exception as e:
                    print("message error:", e)
        except Exception as e:
            print("longpoll error:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
