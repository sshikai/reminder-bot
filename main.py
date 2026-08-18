import os
import re
import time
import random
import sqlite3
import threading
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

# ===== НАСТРОЙКИ =====
VK_TOKEN = os.environ.get("VK_TOKEN", "").strip()
CREATOR_ID = 479753606  # ты — админ в любом чате, снять нельзя

# ===== БАЗА ДАННЫХ =====
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

def send_msg(peer, text):
    if VK is None or not peer:
        return
    try:
        VK.messages.send(peer_id=peer, message=text, random_id=random.getrandbits(31))
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

def handle_message(peer, sender, text, reply_from, reply_text):
    if peer < 2000000000:
        return

    first = norm(text.split("\n")[0])
    if not first or not first.startswith("!"):
        return

    cmd = first.split(" ", 1)[0]
    args = first.split(" ")[1:]

    if not is_admin(sender, peer):
        send_msg(peer, "⛔ Эта команда доступна только администраторам.")
        return

    owner = is_owner(sender, peer)

    # ----- !создать -----
    if cmd == "!создать":
        if not reply_text:
            send_msg(peer, "❌ Ответьте на сообщение с текстом напоминания и введите !создать <название> <минуты>")
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
        with DB_LOCK:
            try:
                CONN.execute("""INSERT INTO reminders(peer_id, name, text, interval_minutes, next_trigger) 
                                VALUES(?,?,?,?,?)""",
                             (peer, name, reply_text, minutes, time.time() + minutes * 60))
                CONN.commit()
                send_msg(peer, f"✅ Напоминание «{name}» создано. Интервал: {minutes} мин.")
            except sqlite3.IntegrityError:
                send_msg(peer, f"❌ Напоминание «{name}» уже существует.")

    # ----- !список -----
    elif cmd == "!список":
        with DB_LOCK:
            rows = CONN.execute("SELECT name, interval_minutes, next_trigger FROM reminders WHERE peer_id=?", (peer,)).fetchall()
        if not rows:
            send_msg(peer, "📭 Список напоминаний пуст.")
            return
        msg = "📋 Список напоминаний:\n\n"
        now = time.time()
        for r in rows:
            remaining = max(0, r["next_trigger"] - now)
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            msg += f"🔹 {r['name']}\n   Интервал: {r['interval_minutes']} мин.\n   Через: {mins} мин {secs} сек\n\n"
        send_msg(peer, msg)

    # ----- !удалить -----
    elif cmd == "!удалить":
        if not args:
            send_msg(peer, "❌ Формат: !удалить <название>")
            return
        name = " ".join(args)
        with DB_LOCK:
            cur = CONN.execute("DELETE FROM reminders WHERE peer_id=? AND name=?", (peer, name))
            CONN.commit()
        if cur.rowcount > 0:
            send_msg(peer, f"✅ Напоминание «{name}» удалено.")
        else:
            send_msg(peer, f"❌ Напоминание «{name}» не найдено.")

    # ----- !редактировать -----
    elif cmd == "!редактировать":
        if len(args) < 2:
            send_msg(peer, "❌ Формат: !редактировать <название> <минуты>")
            return
        try:
            minutes = int(args[-1])
            name = " ".join(args[:-1])
        except ValueError:
            send_msg(peer, "❌ Минуты должны быть числом.")
            return
        with DB_LOCK:
            cur = CONN.execute("""UPDATE reminders SET interval_minutes=?, next_trigger=? 
                                  WHERE peer_id=? AND name=?""",
                               (minutes, time.time() + minutes * 60, peer, name))
            CONN.commit()
        if cur.rowcount > 0:
            send_msg(peer, f"✅ Напоминание «{name}» обновлено. Новый интервал: {minutes} мин.")
        else:
            send_msg(peer, f"❌ Напоминание «{name}» не найдено.")

    # ----- !отключить -----
    elif cmd == "!отключить":
        set_setting(peer, "global_enabled", "0")
        send_msg(peer, "🔕 Все напоминания отключены.")

    # ----- !включить -----
    elif cmd == "!включить":
        set_setting(peer, "global_enabled", "1")
        now = time.time()
        with DB_LOCK:
            rows = CONN.execute("SELECT id, interval_minutes, next_trigger FROM reminders WHERE peer_id=?", (peer,)).fetchall()
            for r in rows:
                if r["next_trigger"] < now:
                    new_trigger = now + r["interval_minutes"] * 60
                    CONN.execute("UPDATE reminders SET next_trigger=? WHERE id=?", (new_trigger, r["id"]))
            CONN.commit()
        send_msg(peer, "🔔 Напоминания включены.")

    # ----- !развернуть -----
    elif cmd == "!развернуть":
        if not args:
            send_msg(peer, "❌ Формат: !развернуть <название>")
            return
        name = " ".join(args)
        with DB_LOCK:
            row = CONN.execute("SELECT text FROM reminders WHERE peer_id=? AND name=?", (peer, name)).fetchone()
        if row:
            send_msg(peer, f"📝 Текст напоминания «{name}»:\n\n{row['text']}")
        else:
            send_msg(peer, f"❌ Напоминание «{name}» не найдено.")

    # ----- !помощь -----
    elif cmd == "!помощь":
        help_text = (
            "📖 Команды бота Reminder:\n\n"
            "!создать <название> <минуты> — создать напоминание (ответом на сообщение)\n"
            "!список — список всех напоминаний и таймеров\n"
            "!удалить <название> — удалить напоминание\n"
            "!редактировать <название> <минуты> — изменить интервал\n"
            "!отключить — отключить все напоминания\n"
            "!включить — включить напоминания\n"
            "!развернуть <название> — показать текст напоминания\n"
            "!админы — список руководителей чата\n"
            "!помощь — эта справка\n\n"
            "🛡 Команды владельца/создателя:\n"
            "!назначить @игрок — выдать права админа\n"
            "!снять @игрок — снять права админа\n\n"
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
            send_msg(peer, "⛔ Эту команду может использовать только создатель бота или владелец чата.")
            return
        targets = extract_targets(text, reply_from)
        if not targets:
            send_msg(peer, "❌ Укажите игрока: !снять @игрок (или ответом на сообщение).")
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

    # ----- !админы -----
    elif cmd == "!админы":
        chat_owner_id = get_chat_owner(peer)
        lines = ["👥 Администраторы:\n"]
        if chat_owner_id:
            lines.append(f"👑 Владелец чата: {mention(chat_owner_id)}")
        lines.append(f"👑 Создатель: {mention(CREATOR_ID)}")
        extras = [uid for uid in get_extra_admins(peer) if uid != chat_owner_id and uid != CREATOR_ID]
        if extras:
            lines.append("🛡 Админы: " + ", ".join(mention(uid) for uid in extras))
        else:
            lines.append("🛡 Админы: отсутствуют")
        send_msg(peer, "\n".join(lines))


def timer_loop():
    while True:
        try:
            time.sleep(15)
            if VK is None:
                continue
            with DB_LOCK:
                peers = CONN.execute("SELECT DISTINCT peer_id FROM reminders").fetchall()
            for p in peers:
                peer = p["peer_id"]
                if get_setting(peer, "global_enabled", "1") != "1":
                    continue
                now = time.time()
                with DB_LOCK:
                    due = CONN.execute(
                        "SELECT id, name, text, interval_minutes FROM reminders WHERE peer_id=? AND enabled=1 AND next_trigger<=?",
                        (peer, now)
                    ).fetchall()
                for rem in due:
                    msg = f"🔔 Напоминание: {rem['name']}\n\n{rem['text']}\n\n@all"
                    send_msg(peer, msg)
                    new_trigger = now + rem["interval_minutes"] * 60
                    with DB_LOCK:
                        CONN.execute("UPDATE reminders SET next_trigger=? WHERE id=?", (new_trigger, rem["id"]))
                        CONN.commit()
        except Exception as e:
            print("timer error:", e)
            time.sleep(15)


def main():
    global VK
    print("=== Bot starting ===")
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
            print("Bot started, group id:", group_id)

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
                    if peer > 0 and sender > 0 and txt:
                        handle_message(peer, sender, txt, reply_from, reply_text)
                except Exception as e:
                    print("message error:", e)
        except Exception as e:
            print("longpoll error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
