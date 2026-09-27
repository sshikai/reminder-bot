import os
import re
import io
import glob
import time
import random
import sqlite3
import threading
import json
import datetime
import urllib.request
import requests
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except Exception:
    PIL_OK = False

VK_TOKEN = os.environ.get("VK_TOKEN", "").strip()
CREATOR_ID = 479753606
LEADER_ID = 639963159
MD_CHAT_PEER = 2000000004
MSK_TZ = datetime.timezone(datetime.timedelta(hours=3))
CLEAR_PENDING = {}

def get_msk_now():
    return datetime.datetime.now(MSK_TZ)

DATA_DIR = "/app/data" if os.path.isdir("/app/data") else os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DATA_DIR, "bot.db")
PHOTO_DIR = os.path.join(DATA_DIR, "card_photos")
AUCTION_PHOTO_DIR = os.path.join(DATA_DIR, "auction_photos")
CONN = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
CONN.row_factory = sqlite3.Row
DB_LOCK = threading.RLock()
VK = None
NAME_CACHE = {}
OWNER_CACHE = {}
MEMBER_SYNC_CACHE = {}
MD_MEMBERS_CACHE = {"time": 0.0, "members": set()}
LAST_ERR = {"msg": ""}

DICE_PHRASES = [
    "Фортуна повернулась к тебе самым неприличным местом. 🍑",
    "Твой максимум — это бросать кости собакам, к игральным тебе лучше не прикасаться. 🐕",
    "Удача сегодня посмотрела на тебя, посмеялась и ушла ко мне. 😏",
    "Кости любят смелых, а над наивными они просто ржут — прямо как я сейчас. 🦴",
    "Ты проиграл генератору случайных чисел, каково это — быть неудачником на генетическом уровне? 🧬",
    "Пискоструй ты где? Не забыл? Ты проебал в кости. 📢",
    "Эй чепуха, твой проёб не забыли. 🤡",
    "Ты проиграл, но ты держись там, хорошего настроения. 😔",
    "Ну что, допизделся, фартовый? Кости легли раком, сиди теперь и обтекай. 🦀",
    "Удача сегодня посмотрела на твою рожу, плюнула и ушла ко мне. 🤮",
    "Твоя удача осталась где-то далеко, так что иди спокойно погрусти в углу. 😢",
    "Твоя удача сегодня ушла к кому-то с нормальными руками. 🖐️",
    "У тебя руки из задницы растут, судя по результатам твоей игры. 🍑🌱",
    "Это не просто проигрыш, это историческое унижение. Можешь сворачивать свои пожитки. 🧳",
    "Смирись, ты сегодня официально признан главным неудачником Million Dollars. 🏆",
    "Эй инопланетянин, ты помнишь как ты сыграл? Нет? Хуево! 👽",
    "В мире есть три вещи которые не меняются: вращение земли, рассвет солнца и твои проёбы! 🌍️",
    "Прикинь как было бы хорошо если бы ты выиграл? Но нет.... 😭",
    "Я уверен что в параллельной вселенной ты бы смог выиграть, но ты проиграл. Поплачь. 🌌",
    "Я бот - ты человек, разница в том что я не умею проигрывать как ты! 🤖",
    "Ничего лишнего, просто напомню что ты проиграл! 📋",
    "Тебе говорили не играй в кости казино? Тут походу тоже не стоит! 🎰",
    "Прикинь, пересматривал код и увидел твой проёб, решил напомнить. 💻"
]

LEADER_BDAY_TEXT = (
    "Дорогой лидер Million Dollars🎉\n"
    "От лица всего состава поздравляю тебя с днем рождения!\n\n"
    "Спасибо за твой огромный вклад в развитие Million Dollars и за то, что собрал под одним крылом таких крутых ребят.\n\n"
    "Желаем тебе железобетонного терпения, преданных замов, огромного онлайна и чтобы никто не портил тебе настроение. "
    "Пусть наша семья гремит по всему серверу! 💰\n\n{mention}"
)
DEFAULT_BDAY_TEXT = "Поздравляем {mention}. У него сегодня день рождения!"

VALID_COMMANDS = [
    "команды", "админы", "участник", "участники", "ники", "ник", "парк", "прем", "чат",
    "пред", "снять_пред", "лимит_предов", "кд_предов", "старт_контроль", "стоп_контроль",
    "время_опросов", "защита", "-защита", "бан", "разбан", "баны", "адмчат", "admg", "номер_чата",
    "текст_др", "создать", "список", "удалить", "редактировать", "включить", "отключить", "развернуть",
    "назначить", "снять", "голоса", "тишина", "тишина_офф", "проверка_опроса", "бр",
    "мут", "снять_мут", "муты", "преды", "предлист", "статус", "статусы", "проверка", "кости",
    "объява", "обьява", "объявы", "обьвы", "объяв", "обьяв", "кд_объяв", "кд_обьяв",
    "топ", "браки", "брак", "развод", "онлайн", "др", "кто", "кто_я", "инфа", "монетка",
    "+правила", "-правила", "правила", "+приветствие", "-приветствие", "приветствие",
    "значок", "удалить_значок", "значки", "кнб", "чистка", "айди", "запретить_игры", "разрешить_игры",
    "очистить_топ", "карта", "карта_редактировать", "очистить_карту",
    "запретить_редактор", "разрешить_редактор"
]

ROLE_NAMES = {0: "Участник", 1: "👮‍️ Модератор", 2: "🛡 Админ", 3: "🥷 Главный Админ", 4: "👑 Владелец"}
RU_MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]

_EM_BASE = ("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF\u2600-\u26FF\u2700-\u27BF\u2B00-\u2BFF\u2190-\u21FF\u2300-\u23FF"
            "\U0001F1E6-\U0001F1FF\u24C2\u2702-\u27B0\U0001F004\U0001F0CF\U0001F170-\U0001F251]")
_EM_ONE = _EM_BASE + "[\U0001F3FB-\U0001F3FF]?\uFE0F?"
EM_CLUSTER = re.compile("^" + _EM_ONE + "(?:\u200D" + _EM_ONE + ")*$")

BUS_TYPES_ORDER = ["АЗС", "Амуниция", "Одежда", "Аксессуары", "24/7", "ТК", "СК", "ПВЗ",
                   "Ларек", "Закуска", "Мотосалон", "Выс. салон", "Сред. салон", "Низ. салон", "Лод. салон", "Такопарк",
                   "Шинка", "Стайлинг", "Тех. Центр"]
BUS_NO_NUM = {"Мотосалон", "Выс. салон", "Сред. салон", "Низ. салон", "Лод. салон", "Такопарк",
              "Шинка", "Стайлинг", "Тех. Центр"}
BUS_SLOT2 = ("ТК", "СК", "Такопарк")
BUS_TAKO = "Такопарк"
BUS_PAGES = 4
BUS_PER_PAGE = 6
CARD_FIELD_MAP = {"бизнесы": "businesses", "недвижимость": "realty", "имущество": "property_val",
                  "гараж": "garage", "телефон": "phone", "имя": "name"}
CARD_DATA_KEYS = set(CARD_FIELD_MAP.values())
PARAM_MAP = {"бизнесы": "businesses", "недвижимость": "realty", "имущество": "property_val",
             "гараж": "garage", "телефон": "phone", "имя": "name", "фото": "photo"}
FIELD_DEFAULT = {"businesses": "[]", "realty": "[]", "property_val": "", "garage": "", "phone": "", "name": ""}
PARAM_HINT = "бизнесы, недвижимость, имущество, гараж, телефон, фото, имя"

COLORS_ORDER = [
    ("red", "Красный"), ("red_full", "Полностью красный"),
    ("green", "Зеленый"), ("green_full", "Полностью зеленый"),
    ("blue", "Синий"), ("blue_full", "Полностью синий"),
    ("lblue", "Голубой"), ("lblue_full", "Полностью голубой"),
    ("yellow", "Желтый"), ("yellow_full", "Полностью желтый"),
    ("orange", "Оранжевый"), ("orange_full", "Полностью оранжевый"),
    ("pink", "Розовый"), ("pink_full", "Полностью розовый"),
    ("violet", "Фиолетовый"), ("violet_full", "Полностью фиолетовый"),
    ("gray", "Серый"),
]
ALL_COLOR_KEYS = set(k for k, _ in COLORS_ORDER)
DESIGN_PAGES = 3
DESIGN_PER_PAGE = 6
FRAME_BOX = (0.070, 0.190, 0.280, 0.605)
FRAME_BOXES_FILE = os.path.join(DATA_DIR, "frame_boxes.json")
_FRAME_BOXES_CACHE = {"data": None, "ts": 0.0}

WHO_ADJ = ("тайный безумный сонный хитрый гордый дерзкий мудрый лютый ленивый грустный честный добрый грозный "
    "дикий верный робкий нежный бойкий строгий упрямый мирный жуткий милый чудной скромный хмурый бодрый "
    "хладнокровный растерянный уставший вдохновленный хвастливый мнительный отчаянный наивный суровый ласковый "
    "скрытный ревнивый азартный космический призрачный огненный ледяной грозовой звездный теневой лунный солнечный "
    "ветреный болотный подземный небесный морской туманный радиоактивный токсичный квантовый магический мистический "
    "цифровой виртуальный неоновый пиксельный кибернетический древний вечный проклятый святой потусторонний железный "
    "золотой алмазный плюшевый деревянный каменный стеклянный бархатный шелковый ватный бумажный картонный пластиковый "
    "резиновый ржавый глянцевый матовый колючий пушистый гладкий липкий скользкий твердый мягкий хрупкий жидкий "
    "газообразный порошковый шершавый летучий гигантский крошечный круглый квадратный плоский кривой прямой бесконечный "
    "микроскопический массивный тонкий толстый узкий широкий вытянутый раздутый сжатый угловатый симметричный безразмерный "
    "кислый сладкий горький соленый острый пряный мятный шоколадный ванильный чесночный сырный карамельный лимонный "
    "имбирный медовый жареный вареный сырой копченый тушеный четкий хайповый кринжовый рофляный легендарный эпический "
    "дефолтный душный имбовый читерский забивной суетной пафосный блатной козырной фартовый люксовый бюджетный "
    "запрещенный заряженный базированный гигачадский мемный флексящий вайбовый чилловый попкорновый пельменный чебуречный "
    "красный синий зеленый желтый фиолетовый оранжевый розовый черный белый серый бордовый бирюзовый золотистый "
    "серебряный изумрудный яркий тусклый светящийся бледный разноцветный богатый бедный успешный потерянный сломанный "
    "починенный забытый популярный секретный опасный безопасный редкий обычный элитный финальный начальный главный "
    "запасной невидимый неуязвимый серверный региональный деловой бригадный гаражный трассовый премиальный дрифтовый").split()

WHO_NOUN = ("енот кот пес лис волк медведь лев тигр панда хомяк суслик выдра бобр заяц еж крот олень лось кабан слон "
    "жираф бегемот носорог обезьяна ленивец коала кенгуру утконос пингвин фламинго сова орел ворон попугай голубь "
    "лебедь акула дельфин кит краб кальмар осьминог креветка рак медуза ящерица змея хамелеон лягушка жаба дракон "
    "феникс единорог грифон пегас кентавр минотавр сфинкс гарпия сирена эльф гном орк гоблин тролль огр маг чародей "
    "шаман некромант ведьма колдун алхимик рыцарь паладин самурай ниндзя викинг пират призрак вампир оборотень зомби "
    "мумия демон ангел титан голем джинн леший шпион детектив хакер программист геймер стример блогер админ модератор "
    "босс директор шеф повар официант доктор хирург ученый профессор космонавт пилот капитан штурман водитель гонщик "
    "каскадер строитель инженер архитектор художник музыкант актер режиссер писатель поэт фотограф дизайнер модель "
    "стилист учитель тренер синяк крекер торетто стрипуха робот киборг андроид дрон процессор чип сервер ноут комп "
    "телефон плеер калькулятор лазер бластер ракета спутник телескоп микроскоп радар компас фонарик проектор экран "
    "монитор джойстик геймпад кабель провод переходник флешка пельмень чебурек хинкали блин вареник пирожок пончик "
    "круассан кекс торт пицца бургер хотдог суши ролл картофан огурец помидор баклажан кабачок арбуз дыня ананас банан "
    "яблоко груша лимон апельсин орех гриб суп борщ майонез кетчуп соус горчица сухарик чипс попкорн зефир кактус "
    "фикус баобаб дуб цветок роза лотос кристалл алмаз изумруд рубин янтарь метеорит астероид комета планета звезда "
    "галактика космос атом ларгус приора бустер мент бандит бизнесмен шахтер дрифтер регион бизнес").split()

WHO_GENDER_EXCEPTIONS = {"торетто": "m", "кофе": "m"}
_WHO_FEM_SOFT = {"модель", "ночь", "мышь", "тень", "дверь", "кровать", "площадь", "пыль", "соль",
                 "ткань", "кровь", "любовь", "морковь", "грязь", "шерсть", "смерть"}
_HARD_ENDINGS = set("гкхжчшщ")

def noun_gender(n):
    if n in WHO_GENDER_EXCEPTIONS: return WHO_GENDER_EXCEPTIONS[n]
    if n.endswith(("а", "я")): return "f"
    if n.endswith(("о", "е")): return "n"
    if n.endswith("ь"):
        return "f" if n in _WHO_FEM_SOFT else "m"
    return "m"

def adj_form(adj, gender):
    if gender == "m": return adj
    if adj.endswith("ой"):
        stem = adj[:-2]; fem, neu = stem + "ая", stem + "ое"
    elif adj.endswith("ый"):
        stem = adj[:-2]; fem, neu = stem + "ая", stem + "ое"
    elif adj.endswith("ий"):
        stem = adj[:-2]
        if stem and stem[-1] in _HARD_ENDINGS:
            fem, neu = stem + "ая", stem + "ое"
        else:
            fem, neu = stem + "яя", stem + "ее"
    else:
        return adj
    return fem if gender == "f" else neu

def fmt_join_date(ts):
    dt = datetime.datetime.fromtimestamp(ts, MSK_TZ)
    return "{} {} {}".format(dt.day, RU_MONTHS[dt.month - 1], dt.year)

def days_since(ts):
    return max(0, int((time.time() - ts) // 86400))

def get_zodiac(day, month):
    if (month == 3 and day >= 21) or (month == 4 and day <= 19): return "♈"
    if (month == 4 and day >= 20) or (month == 5 and day <= 20): return "♉"
    if (month == 5 and day >= 21) or (month == 6 and day <= 20): return "♊"
    if (month == 6 and day >= 21) or (month == 7 and day <= 22): return "♋"
    if (month == 7 and day >= 23) or (month == 8 and day <= 22): return "♌"
    if (month == 8 and day >= 23) or (month == 9 and day <= 22): return "♍"
    if (month == 9 and day >= 23) or (month == 10 and day <= 22): return "♎"
    if (month == 10 and day >= 23) or (month == 11 and day <= 21): return "♏"
    if (month == 11 and day >= 22) or (month == 12 and day <= 21): return "♐"
    if (month == 12 and day >= 22) or (month == 1 and day <= 19): return "♑"
    if (month == 1 and day >= 20) or (month == 2 and day <= 18): return "♒"
    return "♓"

def get_user_role(peer, user_id):
    if user_id == CREATOR_ID or user_id == LEADER_ID or user_id == get_chat_owner(peer):
        return 4
    with DB_LOCK:
        row = CONN.execute("SELECT role FROM roles WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
    return row["role"] if row else 0

def get_role_display(peer, user_id):
    if user_id == CREATOR_ID: return "🔹 Создатель бота"
    if user_id == LEADER_ID: return "🤴Лидер MD"
    return ROLE_NAMES.get(get_user_role(peer, user_id), "Участник")

def set_user_role(peer, user_id, role):
    with DB_LOCK:
        CONN.execute("INSERT OR REPLACE INTO roles(user_id, peer_id, role) VALUES(?,?,?)", (user_id, peer, role))
        CONN.commit()

def get_users_with_min_role(peer, min_role):
    with DB_LOCK:
        return [int(r["user_id"]) for r in CONN.execute("SELECT user_id FROM roles WHERE peer_id=? AND role>=?", (peer, min_role)).fetchall()]

def get_badge(user_id, peer_id):
    with DB_LOCK:
        row = CONN.execute("SELECT emoji FROM badges WHERE user_id=? AND peer_id=?", (user_id, peer_id)).fetchone()
    return row["emoji"] if row else ""

def silent_mention_badge(user_id, peer_id):
    badge = get_badge(user_id, peer_id)
    name = get_user_name(user_id)
    return "[https://vk.com/id{}|{}{}]".format(user_id, name, " " + badge if badge else "")

def can_punish(sender, target, peer):
    if sender == CREATOR_ID or sender == LEADER_ID: return True
    if target == CREATOR_ID or target == LEADER_ID: return False
    sender_role = get_user_role(peer, sender)
    target_role = get_user_role(peer, target)
    if sender == get_chat_owner(peer): return target_role < 4 or target != get_chat_owner(peer)
    if target == get_chat_owner(peer): return False
    return target_role < sender_role

def add_punishment(peer, user_id, p_type, reason, message_id, message_text, issued_by, duration_minutes=0):
    with DB_LOCK:
        CONN.execute("""INSERT INTO punishment_history
            (peer_id, user_id, type, reason, message_id, message_text, issued_by, issued_at, duration_minutes)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (peer, user_id, p_type, reason, message_id or 0, message_text or "", issued_by, int(time.time()), duration_minutes))
        CONN.commit()

def fmt_mute_duration(mins):
    try: mins = int(mins or 0)
    except: mins = 0
    if mins <= 0: return "—"
    if mins >= 1440:
        d = mins // 1440; h = (mins % 1440) // 60
        return "{} дн".format(d) if h == 0 else "{} дн {} ч".format(d, h)
    if mins >= 60:
        h = mins // 60; m = mins % 60
        return "{} ч".format(h) if m == 0 else "{} ч {} мин".format(h, m)
    return "{} мин".format(mins)

def fmt_warn_duration(mins):
    try: mins = int(mins or 0)
    except: mins = 0
    if mins <= 0: return "—"
    days = mins // 1440
    if days >= 9999: return "∞"
    return "{} дн".format(days)

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
                BR_CACHE["time"] = now; BR_CACHE["data"] = data
                return data
        return BR_CACHE["data"]
    except Exception as e:
        print("BR API error:", e)
        return BR_CACHE["data"]

def build_br_page(page):
    servers = fetch_br_servers()
    if not servers: return None, None, 1
    total = len(servers)
    total_pages = max(1, (total + BR_PER_PAGE - 1) // BR_PER_PAGE)
    try: page = int(page)
    except: page = 1
    page = max(1, min(page, total_pages))
    total_online = 0; total_record = 0
    for s in servers:
        try: total_online += int(s.get("online", 0) or 0)
        except: pass
        try: total_record += int(s.get("record", s.get("maxonline", 0)) or 0)
        except: pass
    chunk = servers[(page - 1) * BR_PER_PAGE: page * BR_PER_PAGE]
    lines = ["📱 Общий онлайн проекта BlackRussia: {}".format(total_online),
             "🏆 Общий рекордный онлайн за день: {}\n".format(total_record)]
    start_idx = (page - 1) * BR_PER_PAGE
    for i, s in enumerate(chunk, start_idx + 1):
        fname = str(s.get("firstname", " ") or s.get("name", " ")).strip()
        emoji = BR_COLOR_EMOJI.get(fname.upper(), "🎮")
        try: online = int(s.get("online", 0) or 0)
        except: online = 0
        try: maxonline = int(s.get("maxonline", 0) or 0)
        except: maxonline = 0
        lines.append("{}. {}{} - {} / {}".format(i, emoji, fname, online, maxonline))
    buttons = []
    if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "br_prev", "page": page - 1})}, "color": "secondary"})
    buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
    if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "br_next", "page": page + 1})}, "color": "secondary"})
    return "\n".join(lines), json.dumps({"inline": True, "buttons": [buttons]}), total_pages

def is_md_member(user_id):
    if user_id == CREATOR_ID or user_id == LEADER_ID: return True
    now = time.time()
    if now - MD_MEMBERS_CACHE["time"] > 300 or not MD_MEMBERS_CACHE["members"]:
        try:
            members_resp = VK.messages.getConversationMembers(peer_id=MD_CHAT_PEER)
            members = set()
            for item in members_resp.get("items", []):
                mid = int(item.get("member_id", 0))
                if mid > 0: members.add(mid)
            MD_MEMBERS_CACHE["time"] = now; MD_MEMBERS_CACHE["members"] = members
        except: pass
    return user_id in MD_MEMBERS_CACHE["members"]

def is_inspector(user_id):
    return get_setting(0, "inspector_{}".format(user_id), "0") == "1"

def is_auctioneer(user_id):
    return get_setting(0, "auctioneer_{}".format(user_id), "0") == "1"

def get_all_auctioneers():
    with DB_LOCK:
        rows = CONN.execute("SELECT key, value FROM settings WHERE key LIKE 'auctioneer_%' AND value='1'").fetchall()
    return [int(r["key"].replace("auctioneer_", "")) for r in rows]

def get_all_bot_chats():
    chats = set()
    try:
        with DB_LOCK:
            for tbl in ["members", "reminders"]:
                for r in CONN.execute("SELECT DISTINCT peer_id FROM {}".format(tbl)).fetchall():
                    pid = r["peer_id"]
                    if pid and pid >= 2000000000: chats.add(pid)
    except: pass
    try:
        offset = 0
        while True:
            resp = VK.messages.getConversations(count=200, offset=offset)
            items = resp.get("items", [])
            if not items: break
            for item in items:
                pid = item.get("peer", {}).get("id", 0)
                if pid and pid >= 2000000000: chats.add(pid)
            if len(items) < 200: break
            offset += 200
            if offset > 1000: break
    except: pass
    return list(chats)

def has_active_dice_punishments(peer, user_id):
    now = int(time.time())
    with DB_LOCK:
        mute_row = CONN.execute("SELECT mute_until FROM members WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
        muted = bool(mute_row and mute_row["mute_until"] and mute_row["mute_until"] > now)
        ment_row = CONN.execute("SELECT id FROM dice_mentions WHERE peer_id=? AND user_id=? AND end_time>?", (peer, user_id, now)).fetchone()
        mentioned = bool(ment_row)
    return muted, mentioned

def dice_blocked(peer, user_id):
    muted, mentioned = has_active_dice_punishments(peer, user_id)
    return muted and mentioned

def get_marriage(peer, user_id):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM marriages WHERE peer_id=? AND (user1=? OR user2=?)", (peer, user_id, user_id)).fetchone()
    return dict(row) if row else None

def get_marriage_partner(marriage, user_id):
    if not marriage: return None
    return marriage["user2"] if marriage["user1"] == user_id else marriage["user1"]

def increment_msg_stat(peer, user_id, is_sticker=False, chars=0):
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO message_stats(user_id, peer_id, msg_count, sticker_count, dice_wins, kmb_wins, char_count) VALUES(?,?,0,0,0,0,0)", (user_id, peer))
        if is_sticker:
            CONN.execute("UPDATE message_stats SET msg_count=msg_count+1, sticker_count=sticker_count+1, char_count=char_count+? WHERE user_id=? AND peer_id=?", (chars, user_id, peer))
        else:
            CONN.execute("UPDATE message_stats SET msg_count=msg_count+1, char_count=char_count+? WHERE user_id=? AND peer_id=?", (chars, user_id, peer))
        CONN.commit()

def increment_dice_win(peer, user_id):
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO message_stats(user_id, peer_id, msg_count, sticker_count, dice_wins, kmb_wins, char_count) VALUES(?,?,0,0,0,0,0)", (user_id, peer))
        CONN.execute("UPDATE message_stats SET dice_wins=dice_wins+1 WHERE user_id=? AND peer_id=?", (user_id, peer))
        CONN.commit()

def increment_kmb_win(peer, user_id):
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO message_stats(user_id, peer_id, msg_count, sticker_count, dice_wins, kmb_wins, char_count) VALUES(?,?,0,0,0,0,0)", (user_id, peer))
        CONN.execute("UPDATE message_stats SET kmb_wins=kmb_wins+1 WHERE user_id=? AND peer_id=?", (user_id, peer))
        CONN.commit()

# ===== КАРТОЧКА =====
def get_card(user_id):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM player_cards WHERE user_id=?", (user_id,)).fetchone()
    if row:
        d = dict(row)
        d.setdefault("design", "{}")
        d.setdefault("verified", 0)
        return d
    return {"user_id": user_id, "name": "", "businesses": "[]", "realty": "[]", "property_val": "",
            "garage": "", "phone": "", "updated_at": 0, "design": "{}", "verified": 0}

def set_card_field(user_id, **kw):
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO player_cards(user_id) VALUES(?)", (user_id,))
        for k, v in kw.items():
            CONN.execute("UPDATE player_cards SET {}=? WHERE user_id=?".format(k), (v, user_id))
        if set(kw.keys()) & CARD_DATA_KEYS:
            CONN.execute("UPDATE player_cards SET verified=0 WHERE user_id=?", (user_id,))
        CONN.execute("UPDATE player_cards SET updated_at=? WHERE user_id=?", (int(time.time()), user_id))
        CONN.commit()

def get_design(user_id):
    try: return json.loads(get_card(user_id).get("design") or "{}")
    except Exception: return {}

def set_design(user_id, **kw):
    design = get_design(user_id)
    design.update(kw)
    set_card_field(user_id, design=json.dumps(design, ensure_ascii=False))

def clear_card_data(user_id):
    set_card_field(user_id, name="", businesses="[]", realty="[]", property_val="", garage="", phone="")
    set_design(user_id, photo="")

def format_businesses(blist):
    return " | ".join("{} #{}".format(b["t"], b["n"]) if b.get("n") else b["t"] for b in blist)

def format_realty(rlist):
    return " | ".join("{} #{}".format(r["t"], r["n"]) for r in rlist)

def format_property(val):
    if not val: return "Неизвестно"
    return "{:,}".format(int(val)).replace(",", ".")

def format_phone(phone):
    if not phone: return "Неизвестно"
    return "-".join([phone[i:i+2] for i in range(0, len(phone), 2)])

def bus_slots_info(blist):
    types = [b["t"] for b in blist]
    has_azs = "АЗС" in types
    slot2 = next((t for t in types if t in BUS_SLOT2), None)
    others = [t for t in types if t != "АЗС" and t not in BUS_SLOT2]
    has_tako = (slot2 == BUS_TAKO)
    used_other = len(others) + (1 if has_tako else 0)
    return has_azs, slot2, others, has_tako, used_other

def can_add_business(blist, biz_type):
    has_azs, slot2, others, has_tako, used_other = bus_slots_info(blist)
    if biz_type == "АЗС":
        return (True, "replace") if has_azs else (True, "add")
    if biz_type in BUS_SLOT2:
        if slot2 == biz_type:
            if biz_type in BUS_NO_NUM: return False, "exists"
            return True, "replace"
        if biz_type == BUS_TAKO:
            if len(others) + 1 > 2: return False, "full"
            return True, "add"
        return True, "add"
    count_same = others.count(biz_type)
    if count_same >= 2: return False, "max2"
    if used_other >= 2: return False, "full"
    return True, "add"

def add_business(user_id, biz_type, num=None):
    card = get_card(user_id)
    blist = json.loads(card["businesses"] or "[]")
    if biz_type == "АЗС":
        for b in blist:
            if b["t"] == biz_type:
                b["n"] = num
                set_card_field(user_id, businesses=json.dumps(blist, ensure_ascii=False))
                return
    if biz_type in BUS_SLOT2:
        same = [b for b in blist if b["t"] == biz_type]
        if same:
            same[0]["n"] = num
            set_card_field(user_id, businesses=json.dumps(blist, ensure_ascii=False))
            return
        blist = [b for b in blist if b["t"] not in BUS_SLOT2]
    entry = {"t": biz_type}
    if num: entry["n"] = num
    blist.append(entry)
    set_card_field(user_id, businesses=json.dumps(blist, ensure_ascii=False))

def add_realty(user_id, realty_type, num):
    card = get_card(user_id)
    rlist = json.loads(card["realty"] or "[]")
    rlist.append({"t": realty_type, "n": num})
    set_card_field(user_id, realty=json.dumps(rlist, ensure_ascii=False))

def get_card_state(user_id, peer_id):
    with DB_LOCK:
        row = CONN.execute("SELECT step, context FROM card_edit_state WHERE user_id=? AND peer_id=?", (user_id, peer_id)).fetchone()
    if row:
        return {"step": row["step"], "context": json.loads(row["context"]) if row["context"] else {}}
    return None

def set_card_state(user_id, peer_id, step, context=None):
    if context is None: context = {}
    context["ts"] = int(time.time())
    with DB_LOCK:
        CONN.execute("INSERT OR REPLACE INTO card_edit_state(user_id, peer_id, step, context) VALUES(?,?,?,?)",
                     (user_id, peer_id, step, json.dumps(context, ensure_ascii=False)))
        CONN.commit()

def clear_card_state(user_id, peer_id):
    with DB_LOCK:
        CONN.execute("DELETE FROM card_edit_state WHERE user_id=? AND peer_id=?", (user_id, peer_id))
        CONN.commit()

# ===== АУКЦИОНЫ =====
def get_auction_state(user_id, peer_id):
    with DB_LOCK:
        row = CONN.execute("SELECT step, context FROM auction_state WHERE user_id=? AND peer_id=?", (user_id, peer_id)).fetchone()
    if row:
        return {"step": row["step"], "context": json.loads(row["context"]) if row["context"] else {}}
    return None

def set_auction_state(user_id, peer_id, step, context=None):
    if context is None: context = {}
    context["ts"] = int(time.time())
    with DB_LOCK:
        CONN.execute("INSERT OR REPLACE INTO auction_state(user_id, peer_id, step, context) VALUES(?,?,?,?)",
                     (user_id, peer_id, step, json.dumps(context, ensure_ascii=False)))
        CONN.commit()

def clear_auction_state(user_id, peer_id):
    with DB_LOCK:
        CONN.execute("DELETE FROM auction_state WHERE user_id=? AND peer_id=?", (user_id, peer_id))
        CONN.commit()

def create_auction(peer_id, name, datetime_str, created_by):
    with DB_LOCK:
        cursor = CONN.execute("INSERT INTO auctions(peer_id, name, datetime_str, created_by, created_at, state) VALUES(?,?,?,?,?,?)",
            (peer_id, name, datetime_str, created_by, int(time.time()), "pending"))
        auction_id = cursor.lastrowid
        CONN.commit()
    return auction_id

def get_auction(auction_id):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM auctions WHERE id=?", (auction_id,)).fetchone()
    return dict(row) if row else None

def get_auctions_for_peer(peer_id):
    with DB_LOCK:
        rows = CONN.execute("SELECT * FROM auctions WHERE peer_id=? AND state IN ('pending','active') ORDER BY id", (peer_id,)).fetchall()
    return [dict(r) for r in rows]

def get_all_auctions():
    with DB_LOCK:
        rows = CONN.execute("SELECT * FROM auctions WHERE state IN ('pending','active') ORDER BY id").fetchall()
    return [dict(r) for r in rows]

def delete_auction(auction_id):
    with DB_LOCK:
        CONN.execute("DELETE FROM auction_lots WHERE auction_id=?", (auction_id,))
        CONN.execute("DELETE FROM auction_bids WHERE lot_id IN (SELECT id FROM auction_lots WHERE auction_id=?)", (auction_id,))
        CONN.execute("DELETE FROM auctions WHERE id=?", (auction_id,))
        CONN.commit()

def add_lot(auction_id, lot_number, name, min_price, photo_url=None, photo_att=None):
    with DB_LOCK:
        CONN.execute("INSERT INTO auction_lots(auction_id, lot_number, name, min_price, photo_url, photo_att) VALUES(?,?,?,?,?,?)",
            (auction_id, lot_number, name, min_price, photo_url, photo_att))
        CONN.commit()

def get_lots(auction_id):
    with DB_LOCK:
        rows = CONN.execute("SELECT * FROM auction_lots WHERE auction_id=? ORDER BY lot_number", (auction_id,)).fetchall()
    return [dict(r) for r in rows]

def get_lot(lot_id):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM auction_lots WHERE id=?", (lot_id,)).fetchone()
    return dict(row) if row else None

def update_lot_name(lot_id, name):
    with DB_LOCK:
        CONN.execute("UPDATE auction_lots SET name=? WHERE id=?", (name, lot_id))
        CONN.commit()

def update_lot_photo(lot_id, photo_url, photo_att):
    with DB_LOCK:
        CONN.execute("UPDATE auction_lots SET photo_url=?, photo_att=? WHERE id=?", (photo_url, photo_att, lot_id))
        CONN.commit()

def delete_lot(lot_id):
    with DB_LOCK:
        CONN.execute("DELETE FROM auction_bids WHERE lot_id=?", (lot_id,))
        CONN.execute("DELETE FROM auction_lots WHERE id=?", (lot_id,))
        CONN.commit()

def update_auction_datetime(auction_id, datetime_str):
    with DB_LOCK:
        CONN.execute("UPDATE auctions SET datetime_str=? WHERE id=?", (datetime_str, auction_id))
        CONN.commit()

def update_auction_name(auction_id, name):
    with DB_LOCK:
        CONN.execute("UPDATE auctions SET name=? WHERE id=?", (name, auction_id))
        CONN.commit()

def start_auction(auction_id):
    with DB_LOCK:
        CONN.execute("UPDATE auctions SET state='active', started_at=? WHERE id=?", (int(time.time()), auction_id))
        CONN.commit()

def finish_auction(auction_id):
    with DB_LOCK:
        CONN.execute("UPDATE auctions SET state='finished' WHERE id=?", (auction_id,))
        CONN.commit()

def stop_auction(auction_id):
    with DB_LOCK:
        CONN.execute("UPDATE auctions SET state='stopped' WHERE id=?", (auction_id,))
        CONN.commit()

def get_active_lot_state(auction_id):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM auction_lots WHERE auction_id=? AND state='active'", (auction_id,)).fetchone()
    return dict(row) if row else None

def set_lot_active(lot_id):
    with DB_LOCK:
        CONN.execute("UPDATE auction_lots SET state='active' WHERE id=?", (lot_id,))
        CONN.commit()

def set_lot_finished(lot_id, winner_id=None, final_price=0, sold=0):
    with DB_LOCK:
        CONN.execute("UPDATE auction_lots SET state='finished', winner_id=?, final_price=?, sold=? WHERE id=?",
            (winner_id, final_price, sold, lot_id))
        CONN.commit()

def add_bid(lot_id, user_id, amount):
    with DB_LOCK:
        cursor = CONN.execute("INSERT INTO auction_bids(lot_id, user_id, amount, bid_time) VALUES(?,?,?,?)",
            (lot_id, user_id, amount, int(time.time())))
        bid_id = cursor.lastrowid
        CONN.commit()
    return bid_id

def get_latest_bid(lot_id):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM auction_bids WHERE lot_id=? ORDER BY amount DESC LIMIT 1", (lot_id,)).fetchone()
    return dict(row) if row else None

def get_all_bids(lot_id):
    with DB_LOCK:
        rows = CONN.execute("SELECT * FROM auction_bids WHERE lot_id=? ORDER BY amount DESC", (lot_id,)).fetchall()
    return [dict(r) for r in rows]

def parse_bid_amount(text):
    text = text.strip().replace(",", ".").replace(" ", "")
    try:
        if "." in text:
            parts = text.split(".")
            if len(parts) == 2:
                whole = parts[0]
                frac = parts[1]
                if len(frac) == 1:
                    return float(whole) * 1000000 + float("0." + frac) * 1000000
                elif len(frac) == 2:
                    return float(whole) * 1000000 + float("0." + frac) * 1000000
                elif len(frac) == 3:
                    return float(whole) * 1000000 + float(frac) * 1000
                else:
                    return float(whole) * 1000000 + float(frac)
        else:
            num = int(text.replace(".", ""))
            if num >= 1000000000:
                return float(num)
            elif num >= 1000000:
                return float(num)
            elif num >= 1000:
                return float(num * 1000)
            elif num >= 20:
                return float(num * 1000000)
            else:
                return float(num * 1000000)
    except:
        return None

def get_min_step(current_price):
    if current_price < 50000000:
        return 1000000
    elif current_price < 100000000:
        return 3000000
    elif current_price < 200000000:
        return 5000000
    elif current_price < 400000000:
        return 7000000
    elif current_price < 1000000000:
        return 15000000
    else:
        return 30000000

def format_price(amount):
    if amount >= 1000000000:
        return "{:.1f} млрд".format(amount / 1000000000)
    elif amount >= 1000000:
        return "{:.1f} млн".format(amount / 1000000)
    elif amount >= 1000:
        return "{:.0f} тыс".format(amount / 1000)
    else:
        return "{:.0f}".format(amount)

def save_auction_photo(user_id, url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MD BOT)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(data) < 1000: return None
        try: os.makedirs(AUCTION_PHOTO_DIR, exist_ok=True)
        except Exception: pass
        filename = "auction_{}_{}.jpg".format(user_id, int(time.time()))
        path = os.path.join(AUCTION_PHOTO_DIR, filename)
        with open(path, "wb") as f: f.write(data)
        return path
    except Exception as e:
        print("save_auction_photo error:", e)
        return None

def upload_auction_photo(peer, img_path):
    try:
        with open(img_path, "rb") as f:
            raw = f.read()
        if len(raw) > 4500000:
            return None
        server = VK.photos.getMessagesUploadServer(peer_id=peer)
        resp = requests.post(server["upload_url"], files={"photo": ("lot.jpg", raw, "image/jpeg")}, timeout=30)
        data = resp.json()
        if not data.get("photo"):
            return None
        saved = VK.photos.saveMessagesPhoto(photo=data["photo"], hash=data["hash"], server=data["server"])
        if not saved:
            return None
        return "photo{}_{}".format(saved[0]["owner_id"], saved[0]["id"])
    except Exception as e:
        print("upload_auction_photo error:", e)
        return None

def handle_auction_input(sender, peer, text, cmid=None, attachments=None):
    state = get_auction_state(sender, peer)
    if not state: return False
    step = state["step"]
    ctx = state.get("context", {})
    prompt_cmid = ctx.get("msg_cmid") or cmid
    if time.time() - ctx.get("ts", 0) > 300:
        clear_auction_state(sender, peer)
        send_msg(peer, "⏰ Время на редактирование аукциона вышло (5 минут бездействия).")
        return True

    def reply(msg, kb=None):
        if prompt_cmid:
            try:
                VK.messages.edit(peer_id=peer, conversation_message_id=prompt_cmid, message=msg, keyboard=json.dumps(kb) if kb else json.dumps({"inline": True, "buttons": []}))
                return
            except: pass
        send_msg(peer, msg, keyboard=kb)

    if text.lower() in ["отмена", "отменить"]:
        clear_auction_state(sender, peer)
        reply("❌ Редактирование аукциона отменено.")
        return True

    if step == "create_peer":
        if not text.isdigit():
            reply("❌ Введите номер чата цифрами.")
            return True
        peer_id = int(text)
        set_auction_state(sender, peer, "create_name", {"peer_id": peer_id})
        reply("Введите название аукциона:")
        return True

    if step == "create_name":
        name = text.strip()
        if not name:
            reply("❌ Название не может быть пустым.")
            return True
        ctx["name"] = name
        set_auction_state(sender, peer, "create_datetime", ctx)
        reply("Введите дату и время проведения (пример: 03.02.26 13:44):")
        return True

    if step == "create_datetime":
        try:
            dt = datetime.datetime.strptime(text.strip(), "%d.%m.%y %H:%M")
            ctx["datetime_str"] = text.strip()
            set_auction_state(sender, peer, "create_lots_count", ctx)
            reply("Сколько лотов желаете добавить?")
            return True
        except:
            reply("❌ Неверный формат. Пример: 03.02.26 13:44")
            return True

    if step == "create_lots_count":
        if not text.isdigit():
            reply("❌ Введите число лотов.")
            return True
        ctx["lots_count"] = int(text)
        ctx["current_lot"] = 1
        ctx["lots"] = []
        set_auction_state(sender, peer, "create_lot_name", ctx)
        reply("Введите лот 1 и его минимальную цену через запятую (пример: н/з х444хх44, 20):")
        return True

    if step == "create_lot_name":
        parts = text.split(",")
        if len(parts) < 2:
            reply("❌ Формат: название, цена (пример: н/з х444хх44, 20)")
            return True
        lot_name = parts[0].strip()
        try:
            min_price = float(parts[1].strip()) * 1000000
        except:
            reply("❌ Неверная цена.")
            return True
        ctx["lots"].append({"name": lot_name, "min_price": min_price})
        set_auction_state(sender, peer, "create_lot_photo", ctx)
        reply("Прикрепите фото лота {}:".format(ctx["current_lot"]))
        return True

    if step == "create_lot_photo":
        photo_url = None
        photo_att = None
        if attachments:
            for att in attachments:
                if att.get("type") == "photo":
                    sizes = (att.get("photo") or {}).get("sizes") or []
                    if sizes:
                        best = max(sizes, key=lambda s: (s.get("width", 0) * s.get("height", 0)))
                        photo_url = best.get("url")
                        ph = att.get("photo", {})
                        if ph.get("owner_id") and ph.get("id"):
                            photo_att = "photo{}_{}".format(ph['owner_id'], ph['id'])
                        break
        if not photo_url:
            reply("❌ Прикрепите фото.")
            return True
        ctx["lots"][-1]["photo_url"] = photo_url
        ctx["lots"][-1]["photo_att"] = photo_att
        if ctx["current_lot"] < ctx["lots_count"]:
            ctx["current_lot"] += 1
            set_auction_state(sender, peer, "create_lot_name", ctx)
            reply("Введите лот {} и его минимальную цену через запятую:".format(ctx["current_lot"]))
        else:
            auction_id = create_auction(ctx["peer_id"], ctx["name"], ctx["datetime_str"], sender)
            for i, lot in enumerate(ctx["lots"], 1):
                add_lot(auction_id, i, lot["name"], lot["min_price"], lot.get("photo_url"), lot.get("photo_att"))
            clear_auction_state(sender, peer)
            reply("✅ Аукцион создан! ID: {}".format(auction_id))
        return True

    if step == "delete_peer":
        if not text.isdigit():
            reply("❌ Введите номер чата.")
            return True
        peer_id = int(text)
        auctions = get_auctions_for_peer(peer_id)
        if not auctions:
            reply("❌ В этом чате нет аукционов.")
            clear_auction_state(sender, peer)
            return True
        ctx["peer_id"] = peer_id
        set_auction_state(sender, peer, "delete_choose", ctx)
        lines = ["Выберите аукцион для удаления:\n"]
        for i, a in enumerate(auctions, 1):
            lines.append("{}. {} ({})".format(i, a["name"], a["datetime_str"]))
        kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": str(i), "payload": json.dumps({"cmd": "auction_delete_select", "id": a["id"]})}, "color": "secondary"} for i, a in enumerate(auctions, 1)][:5]]}
        reply("\n".join(lines), kb)
        return True

    if step == "edit_peer":
        if not text.isdigit():
            reply("❌ Введите номер чата.")
            return True
        peer_id = int(text)
        auctions = get_auctions_for_peer(peer_id)
        if not auctions:
            reply("❌ В этом чате нет аукционов.")
            clear_auction_state(sender, peer)
            return True
        ctx["peer_id"] = peer_id
        set_auction_state(sender, peer, "edit_choose", ctx)
        lines = ["Выберите аукцион для редактирования:\n"]
        for i, a in enumerate(auctions, 1):
            lines.append("{}. {} ({})".format(i, a["name"], a["datetime_str"]))
        kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": str(i), "payload": json.dumps({"cmd": "auction_edit_select", "id": a["id"]})}, "color": "secondary"} for i, a in enumerate(auctions, 1)][:5]]}
        reply("\n".join(lines), kb)
        return True

    if step == "edit_field":
        field = ctx.get("field")
        auction_id = ctx.get("auction_id")
        if field == "datetime":
            try:
                dt = datetime.datetime.strptime(text.strip(), "%d.%m.%y %H:%M")
                update_auction_datetime(auction_id, text.strip())
                clear_auction_state(sender, peer)
                reply("✅ Дата и время обновлены.")
                return True
            except:
                reply("❌ Неверный формат. Пример: 04.06.26 15:00")
                return True
        elif field == "name":
            update_auction_name(auction_id, text.strip())
            clear_auction_state(sender, peer)
            reply("✅ Название обновлено.")
            return True

    if step == "edit_lot_choose":
        if not text.isdigit():
            reply("❌ Введите номер лота.")
            return True
        lot_num = int(text)
        lots = get_lots(ctx["auction_id"])
        if lot_num < 1 or lot_num > len(lots):
            reply("❌ Лот не найден.")
            return True
        lot = lots[lot_num - 1]
        ctx["lot_id"] = lot["id"]
        set_auction_state(sender, peer, "edit_lot_action", ctx)
        kb = {"inline": True, "buttons": [
            [{"action": {"type": "callback", "label": "Удалить", "payload": json.dumps({"cmd": "auction_lot_delete"})}, "color": "negative"}],
            [{"action": {"type": "callback", "label": "Сменить название", "payload": json.dumps({"cmd": "auction_lot_rename"})}, "color": "primary"}],
            [{"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "auction_edit_menu", "id": ctx["auction_id"]})}, "color": "secondary"}]
        ]}
        reply("Что сделать с лотом?", kb)
        return True

    if step == "edit_lot_rename":
        ctx["new_name"] = text.strip()
        set_auction_state(sender, peer, "edit_lot_photo", ctx)
        reply("Прикрепите новое фото лота:")
        return True

    if step == "edit_lot_photo":
        photo_url = None
        photo_att = None
        if attachments:
            for att in attachments:
                if att.get("type") == "photo":
                    sizes = (att.get("photo") or {}).get("sizes") or []
                    if sizes:
                        best = max(sizes, key=lambda s: (s.get("width", 0) * s.get("height", 0)))
                        photo_url = best.get("url")
                        ph = att.get("photo", {})
                        if ph.get("owner_id") and ph.get("id"):
                            photo_att = "photo{}_{}".format(ph['owner_id'], ph['id'])
                        break
        if photo_url:
            update_lot_photo(ctx["lot_id"], photo_url, photo_att)
        update_lot_name(ctx["lot_id"], ctx["new_name"])
        clear_auction_state(sender, peer)
        reply("✅ Лот обновлён.")
        return True

    if step == "announce_peer":
        if not text.isdigit():
            reply("❌ Введите номер чата.")
            return True
        peer_id = int(text)
        auctions = get_auctions_for_peer(peer_id)
        if not auctions:
            reply("❌ В этом чате нет аукционов.")
            clear_auction_state(sender, peer)
            return True
        ctx["peer_id"] = peer_id
        set_auction_state(sender, peer, "announce_choose", ctx)
        lines = ["Выберите аукцион для анонса:\n"]
        for i, a in enumerate(auctions, 1):
            lines.append("{}. {} ({})".format(i, a["name"], a["datetime_str"]))
        kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": str(i), "payload": json.dumps({"cmd": "auction_announce_select", "id": a["id"]})}, "color": "secondary"} for i, a in enumerate(auctions, 1)][:5]]}
        reply("\n".join(lines), kb)
        return True

    if step == "active_peer":
        if not text.isdigit():
            reply("❌ Введите номер чата.")
            return True
        peer_id = int(text)
        auctions = get_auctions_for_peer(peer_id)
        if not auctions:
            reply("❌ В этом чате нет аукционов.")
            clear_auction_state(sender, peer)
            return True
        ctx["peer_id"] = peer_id
        set_auction_state(sender, peer, "active_choose", ctx)
        lines = ["Активные аукционы:\n"]
        for i, a in enumerate(auctions, 1):
            lines.append("{}. {} ({})".format(i, a["name"], a["datetime_str"]))
        kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": str(i), "payload": json.dumps({"cmd": "auction_active_select", "id": a["id"]})}, "color": "secondary"} for i, a in enumerate(auctions, 1)][:5]]}
        reply("\n".join(lines), kb)
        return True

    if step == "stop_peer":
        if not text.isdigit():
            reply("❌ Введите номер чата.")
            return True
        peer_id = int(text)
        auctions = get_auctions_for_peer(peer_id)
        if not auctions:
            reply("❌ В этом чате нет активных аукционов.")
            clear_auction_state(sender, peer)
            return True
        ctx["peer_id"] = peer_id
        set_auction_state(sender, peer, "stop_choose", ctx)
        lines = ["Выберите аукцион для остановки:\n"]
        for i, a in enumerate(auctions, 1):
            lines.append("{}. {} ({})".format(i, a["name"], a["datetime_str"]))
        kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": str(i), "payload": json.dumps({"cmd": "auction_stop_select", "id": a["id"]})}, "color": "secondary"} for i, a in enumerate(auctions, 1)][:5]]}
        reply("\n".join(lines), kb)
        return True

    return False

def resolve_cmid_retry(peer, sent_id, tries=3):
    for i in range(tries):
        try:
            resp = VK.messages.getById(message_ids=[sent_id])
            items = resp.get("items", [])
            if items:
                cm = items[0].get("conversation_message_id")
                if cm: return int(cm)
        except Exception:
            pass
        time.sleep(0.35)
    return sent_id

def close_card_session(peer, ctx, txt):
    cm = ctx.get("msg_cmid"); mid = ctx.get("msg_id")
    deletes = []
    if cm: deletes.append({"conversation_message_ids": [cm], "delete_for_all": 1})
    if mid: deletes.append({"message_ids": [mid], "delete_for_all": 1})
    if mid: deletes.append({"message_ids": [mid]})
    if cm: deletes.append({"conversation_message_ids": [cm]})
    for a in deletes:
        try:
            VK.messages.delete(peer_id=peer, **a)
            send_msg(peer, txt)
            return True
        except Exception:
            continue
    edits = []
    if cm: edits.append({"conversation_message_id": cm})
    if mid: edits.append({"message_id": mid})
    if cm: edits.append({"message_id": cm})
    if mid: edits.append({"conversation_message_id": mid})
    for kw in edits:
        try:
            VK.messages.edit(peer_id=peer, message=txt, keyboard=json.dumps({"inline": True, "buttons": []}), **kw)
            return True
        except Exception:
            continue
    print("card close FAIL peer={} ctx={}".format(peer, ctx))
    send_msg(peer, txt)
    return False

def extract_photo_url(msg_obj):
    for att in (msg_obj.get("attachments") or []):
        if att.get("type") == "photo":
            sizes = (att.get("photo") or {}).get("sizes") or []
            if sizes:
                best = max(sizes, key=lambda s: (s.get("width", 0) * s.get("height", 0)))
                return best.get("url")
    return None

def save_design_photo(user_id, url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MD BOT)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(data) < 1000: return False
        try: os.makedirs(PHOTO_DIR, exist_ok=True)
        except Exception: pass
        path = os.path.join(PHOTO_DIR, "{}.jpg".format(user_id))
        with open(path, "wb") as f: f.write(data)
        return True
    except Exception as e:
        print("save_design_photo error:", e)
        return False

def handle_card_input(sender, peer, text, cmid=None, attachments=None):
    state = get_card_state(sender, peer)
    if not state: return False
    step = state["step"]
    ctx = state.get("context", {})
    prompt_cmid = ctx.get("msg_cmid") or cmid
    if time.time() - ctx.get("ts", 0) > 60:
        clear_card_state(sender, peer)
        close_card_session(peer, ctx, "Время на редактирование вышло, {} вы бездействовали минуту⏳".format(mention(sender)))
        return True

    def reply(msg):
        if prompt_cmid:
            try:
                VK.messages.edit(peer_id=peer, conversation_message_id=prompt_cmid, message=msg, keyboard=json.dumps({"inline": True, "buttons": []}))
                return
            except: pass
        send_msg(peer, msg)

    def reply_kb(msg, back_payload, menu_step, menu_ctx=None):
        kb = {"inline": True, "buttons": [[
            {"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps(back_payload)}, "color": "primary"},
            {"action": {"type": "callback", "label": "✅ Готово", "payload": json.dumps({"cmd": "card_finish"})}, "color": "positive"}]]}
        c = dict(menu_ctx or {})
        c["msg_cmid"] = prompt_cmid
        set_card_state(sender, peer, menu_step, c)
        if prompt_cmid:
            try:
                VK.messages.edit(peer_id=peer, conversation_message_id=prompt_cmid, message=msg, keyboard=json.dumps(kb))
                return
            except: pass
        send_msg(peer, msg, keyboard=kb)

    if text.lower() in ["отмена", "отменить"]:
        clear_card_state(sender, peer)
        reply("❌ Редактирование отменено.")
        return True

    if step == "design_photo_wait":
        if text.strip().lower() in ["дефолт", "default"]:
            set_design(sender, photo="")
            reply_kb("✅ Возвращена дефолтная фотография карточки.", {"cmd": "card_edit_menu"}, "edit_menu")
            return True
        url = extract_photo_url({"attachments": attachments}) if attachments else None
        if not url:
            reply("❌ Прикрепи фото к сообщению (или напиши «дефолт»).")
            return True
        if save_design_photo(sender, url):
            set_design(sender, photo="custom")
            reply_kb("✅ Твоя фотография установлена на карточку!", {"cmd": "card_edit_menu"}, "edit_menu")
        else:
            reply("❌ Не удалось скачать фото, попробуй другое.")
        return True

    if step == "biz_input":
        biz_type = ctx.get("t", "")
        if not re.match(r"^[1-9]\d{0,2}$", text.strip()):
            reply("❌ Неверный номер: максимум 3 цифры, без нуля в начале (нельзя 001, 099).")
            return True
        card = get_card(sender)
        blist = json.loads(card["businesses"] or "[]")
        ok, mode = can_add_business(blist, biz_type)
        if not ok:
            reply("❌ Нет свободных слотов под этот бизнес.")
            return True
        add_business(sender, biz_type, text.strip())
        p = ctx.get("p", 1)
        reply_kb("✅ Бизнес {} #{} успешно добавлен!".format(biz_type, text.strip()),
                 {"cmd": "card_bus_menu", "p": p}, "bus_menu", {"p": p})
        return True

    if step == "realty_input":
        realty_type = ctx.get("t", "")
        if not re.match(r"^[1-9]\d{0,3}$", text.strip()):
            reply("❌ Неверный номер: максимум 4 цифры, без нуля в начале.")
            return True
        add_realty(sender, realty_type, text.strip())
        reply_kb("✅ Недвижимость {} #{} успешно добавлена!".format(realty_type, text.strip()),
                 {"cmd": "card_realty_menu"}, "realty_menu")
        return True

    if step == "garage_input":
        if not re.match(r"^[1-9]\d{0,3}$", text.strip()):
            reply("❌ Неверный номер гаража: максимум 4 цифры, без нуля в начале.")
            return True
        set_card_field(sender, garage=text.strip())
        reply_kb("✅ Гараж #{} успешно добавлен!".format(text.strip()), {"cmd": "card_edit_menu"}, "edit_menu")
        return True

    if step == "phone_input":
        if not re.match(r"^[1-9]\d{3,6}$", text.strip()):
            reply("❌ Неверный телефон: 4–7 цифр, без нуля в начале.")
            return True
        set_card_field(sender, phone=text.strip())
        reply_kb("✅ Телефон {} успешно добавлен!".format(format_phone(text.strip())), {"cmd": "card_edit_menu"}, "edit_menu")
        return True

    if step == "name_input":
        if not re.match(r"^[A-Za-z]{1,15}_[A-Za-z]{1,15}$", text.strip()):
            reply("❌ Неверный формат: Имя_Фамилия, только английские буквы, макс. 15+15 символов.")
            return True
        set_card_field(sender, name=text.strip())
        reply_kb("✅ Имя {} успешно установлено!".format(text.strip()), {"cmd": "card_edit_menu"}, "edit_menu")
        return True

    if step == "property_input":
        if not re.match(r"^\d+$", text.strip()):
            reply("❌ Введите сумму цифрами (например 12000000000).")
            return True
        set_card_field(sender, property_val=text.strip())
        reply_kb("✅ Имущество оценено в {}!".format(format_property(text.strip())), {"cmd": "card_edit_menu"}, "edit_menu")
        return True

    return False

# ===== ШРИФТ =====
FONT_CACHE = os.path.join(DATA_DIR, "card_font_cyr.ttf")
_FONT_RESOLVED = {"path": None, "tried": False}

def ensure_font():
    old = os.path.join(DATA_DIR, "card_font.ttf")
    if os.path.isfile(old):
        try: os.remove(old)
        except: pass
    if os.path.isfile(FONT_CACHE): return FONT_CACHE
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freesans.ttf",
    ]
    for p in candidates:
        if os.path.isfile(p): return p
    try:
        hits = glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
        for h in hits:
            if any(k in h.lower() for k in ["dejavu", "liberation", "ptsans", "roboto", "noto", "freesans"]): return h
        if hits: return hits[0]
    except Exception: pass
    urls = [
        "https://raw.githubusercontent.com/google/fonts/main/ofl/ptsans/PT_Sans-Web-Regular.ttf",
        "https://github.com/google/fonts/raw/main/ofl/ptsans/PT_Sans-Web-Regular.ttf",
        "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans.ttf",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MD BOT)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if len(data) > 100000:
                with open(FONT_CACHE, "wb") as f: f.write(data)
                return FONT_CACHE
        except Exception as e:
            print("font download error:", e)
    return None

def get_font(size):
    if not _FONT_RESOLVED["tried"]:
        _FONT_RESOLVED["path"] = ensure_font()
        _FONT_RESOLVED["tried"] = True
        print("card font resolved:", _FONT_RESOLVED["path"])
    p = _FONT_RESOLVED["path"]
    if p:
        try: return ImageFont.truetype(p, size)
        except Exception: pass
    try: return ImageFont.load_default(size)
    except Exception: return ImageFont.load_default()

# ===== ЗАГРУЗКА В ВК + КЭШ =====
def upload_photo(peer, img_buf):
    try: img_buf.seek(0)
    except Exception: pass
    raw = img_buf.getvalue()
    if not raw: raise RuntimeError("EMPTY_IMAGE: картинка пустая")
    if len(raw) > 4500000: raise RuntimeError("TOO_BIG: файл {} байт (лимит ~5 МБ)".format(len(raw)))
    data = None
    last_resp = None
    for attempt in range(4):
        try:
            if attempt < 3:
                server = VK.photos.getMessagesUploadServer(peer_id=peer)
            else:
                server = VK.photos.getMessagesUploadServer()
            resp = requests.post(server["upload_url"], files={"photo": ("card.jpg", raw, "image/jpeg")}, timeout=30)
            data = resp.json()
            last_resp = data
            print("card upload attempt {}: size={} server={} ok={}".format(attempt + 1, len(raw), server.get("server"), bool(data.get("photo"))))
            if data.get("photo"): break
            data = None
        except Exception as e:
            print("card upload attempt {} exception: {}".format(attempt + 1, e))
            last_resp = {"exception": str(e)}
            data = None
        time.sleep(0.8 + attempt * 0.7)
    if not data or not data.get("photo") or not data.get("hash") or not data.get("server"):
        raise RuntimeError("UPLOAD_BAD_RESPONSE: {} (размер файла: {} байт)".format(str(last_resp)[:200], len(raw)))
    saved = VK.photos.saveMessagesPhoto(photo=data["photo"], hash=data["hash"], server=data["server"])
    if not saved: raise RuntimeError("SAVE_EMPTY: ВК не вернул фото после сохранения")
    return "photo{}_{}".format(saved[0]["owner_id"], saved[0]["id"])

def send_card_image(peer, user_id):
    card = get_card(user_id)
    key = "card_att_v4_{}".format(user_id)
    try: cached = json.loads(get_setting(0, key, "") or "{}")
    except Exception: cached = {}
    if cached.get("ts") == card["updated_at"] and cached.get("att"):
        return cached["att"]
    img_buf = render_card(user_id)
    if not img_buf: return None
    att = upload_photo(peer, img_buf)
    set_setting(0, key, json.dumps({"ts": card["updated_at"], "att": att}))
    return att

def send_card_to(peer, target_id):
    err = ""; att = None
    try: att = send_card_image(peer, target_id)
    except Exception as e:
        err = str(e); print("card send error:", err)
    if not att:
        if err:
            if "[15]" in err or "scope" in err.lower():
                send_msg(peer, "❌ У токена нет права «Фотографии»: Управление → Использование API → галочка «Фото» → пересоздать токен.")
            else:
                send_msg(peer, "❌ Ошибка отправки карточки: {}".format(err))
        else:
            send_msg(peer, "❌ Не найден шаблон карточки (card_male.jpg/png) или не установлен Pillow.")
        return
    card = get_card(target_id)
    txt = "🗃️ Личная карточка: {}".format(silent_mention_badge(target_id, peer))
    txt += " | Информация карточки подтверждена✅" if card.get("verified") else " | Информация карточки не подтверждена❌"
    send_msg(peer, txt, attachments=att)

# ===== ОТРИСОВКА =====
CARD_BOXES = {
    "name":   (0.035, 0.800, 0.340, 0.080),
    "biz":    (0.468, 0.215, 0.525, 0.085),
    "realty": (0.468, 0.378, 0.525, 0.085),
    "prop":   (0.468, 0.520, 0.525, 0.085),
    "garage": (0.468, 0.680, 0.525, 0.085),
    "phone":  (0.468, 0.825, 0.525, 0.085),
}

def get_frame_box(color_key):
    now = time.time()
    if _FRAME_BOXES_CACHE["data"] is None or now - _FRAME_BOXES_CACHE["ts"] > 60:
        try:
            with open(FRAME_BOXES_FILE) as f:
                _FRAME_BOXES_CACHE["data"] = json.load(f)
        except Exception:
            _FRAME_BOXES_CACHE["data"] = {}
        _FRAME_BOXES_CACHE["ts"] = now
    data = _FRAME_BOXES_CACHE["data"] or {}
    for k in (color_key, "default"):
        v = data.get(k)
        if v and len(v) == 4:
            try: return tuple(float(x) for x in v)
            except Exception: pass
    return FRAME_BOX

def card_template_path(color_key):
    base = "card_male" if (not color_key or color_key == "red") else "card_male_{}".format(color_key)
    for b in (base, "card_male"):
        for ext in (".jpg", ".png", ".jpeg"):
            p = os.path.join(DATA_DIR, b + ext)
            if os.path.isfile(p): return p
            if os.path.isfile(b + ext): return b + ext
    return None

def paste_custom_photo(img, user_id, box):
    path = os.path.join(PHOTO_DIR, "{}.jpg".format(user_id))
    if not os.path.isfile(path): return img
    try:
        ph = Image.open(path).convert("RGB")
        W, H = img.size
        rx, ry, rw, rh = box
        fx, fy, fw, fh = int(rx * W), int(ry * H), int(rw * W), int(rh * H)
        target_ratio = fw / float(fh)
        pw, phh = ph.size
        cur = pw / float(phh)
        if cur > target_ratio:
            new_w = int(phh * target_ratio)
            left = (pw - new_w) // 2
            ph = ph.crop((left, 0, left + new_w, phh))
        else:
            new_h = int(pw / target_ratio)
            top = (phh - new_h) // 2
            ph = ph.crop((0, top, pw, top + new_h))
        ph = ph.resize((fw, fh), Image.LANCZOS if hasattr(Image, "LANCZOS") else Image.ANTIALIAS)
        mask = Image.new("L", (fw, fh), 0)
        md = ImageDraw.Draw(mask)
        r = max(6, int(min(fw, fh) * 0.05))
        try:
            md.rounded_rectangle((0, 0, fw - 1, fh - 1), radius=r, fill=255)
            img.paste(ph, (fx, fy), mask)
        except Exception:
            img.paste(ph, (fx, fy))
    except Exception as e:
        print("paste_custom_photo error:", e)
    return img

def render_card(user_id):
    if not PIL_OK: return None
    card = get_card(user_id)
    design = get_design(user_id)
    template = card_template_path(design.get("color", "red"))
    if not template: return None
    img = Image.open(template).convert("RGB")
    W, H = img.size
    if W > 1600:
        ratio = 1600.0 / W
        img = img.resize((1600, int(H * ratio)), Image.LANCZOS if hasattr(Image, "LANCZOS") else Image.ANTIALIAS)
        W, H = img.size
    if design.get("photo"):
        img = paste_custom_photo(img, user_id, get_frame_box(design.get("color", "red")))
    draw = ImageDraw.Draw(img)

    def text_w(t, f):
        try: return draw.textlength(t, font=f)
        except Exception:
            try: return f.getsize(t)[0]
            except Exception: return len(t) * 10

    def draw_box(key, text, color, center_x=False, pad=3):
        rx, ry, rw, rh = CARD_BOXES[key]
        x, y, w, h = rx * W, ry * H, rw * W, rh * H
        size = max(14, int(h * 0.48))
        f = get_font(size)
        while text_w(text, f) > w - pad * 2 and size > 10:
            size -= 1
            f = get_font(size)
        try:
            bb = draw.textbbox((0, 0), text, font=f)
            th = bb[3] - bb[1]; yoff = bb[1]
        except Exception:
            th, yoff = size, 0
        ty = y + (h - th) / 2 - yoff
        tw = text_w(text, f)
        tx = x + (w - tw) / 2 if center_x else x + pad
        draw.text((tx, ty), text, font=f, fill=color)

    biz = format_businesses(json.loads(card["businesses"] or "[]")) or "Неизвестно"
    realty = format_realty(json.loads(card["realty"] or "[]")) or "Неизвестно"
    prop = format_property(card["property_val"])
    garage = ("#" + card["garage"]) if card["garage"] else "Неизвестно"
    phone = format_phone(card["phone"]) if card["phone"] else "Неизвестно"
    name = card["name"] or "Неизвестно"
    draw_box("name", name, (255, 255, 255), center_x=True)
    draw_box("biz", biz, (30, 30, 30), pad=3)
    draw_box("realty", realty, (30, 30, 30), pad=3)
    draw_box("prop", prop, (30, 30, 30), pad=3)
    draw_box("garage", garage, (30, 30, 30), pad=3)
    draw_box("phone", phone, (30, 30, 30), pad=3)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    buf.seek(0)
    return buf

def init_db():
    try:
        os.makedirs(PHOTO_DIR, exist_ok=True)
        os.makedirs(AUCTION_PHOTO_DIR, exist_ok=True)
    except Exception: pass
    with DB_LOCK:
        CONN.execute("""CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, name TEXT, text TEXT,
            attachments TEXT, source_message_id INTEGER DEFAULT 0, interval_minutes INTEGER,
            repeat_count INTEGER DEFAULT 1, next_trigger REAL, enabled INTEGER DEFAULT 1, UNIQUE(peer_id, name))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS settings (peer_id INTEGER, key TEXT, value TEXT, UNIQUE(peer_id, key))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS birthdays (user_id INTEGER, peer_id INTEGER, bdate TEXT, updated_at INTEGER, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS birthday_congratulated (user_id INTEGER, peer_id INTEGER, year INTEGER, congratulated_at INTEGER, PRIMARY KEY(user_id, peer_id, year))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER, peer_id INTEGER, nickname TEXT DEFAULT '', warnings INTEGER DEFAULT 0,
            warn_durations TEXT DEFAULT '', warn_expiry INTEGER DEFAULT 0, last_active TEXT DEFAULT '',
            streak INTEGER DEFAULT 0, poll_protected INTEGER DEFAULT 0, join_time INTEGER DEFAULT 0,
            last_vote_time INTEGER DEFAULT 0, who_name TEXT DEFAULT '', who_ts INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS roles (user_id INTEGER, peer_id INTEGER, role INTEGER DEFAULT 0, UNIQUE(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS statuses (id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, name TEXT, UNIQUE(peer_id, name))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS user_statuses (user_id INTEGER, peer_id INTEGER, status_id INTEGER, UNIQUE(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS punishment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, user_id INTEGER, type TEXT, reason TEXT,
            message_id INTEGER DEFAULT 0, message_text TEXT DEFAULT '', issued_by INTEGER, issued_at INTEGER,
            duration_minutes INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS dice_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, initiator INTEGER, opponent INTEGER,
            state TEXT DEFAULT 'pending', message_id INTEGER DEFAULT 0,
            initiator_roll INTEGER DEFAULT 0, opponent_roll INTEGER DEFAULT 0,
            current_turn INTEGER DEFAULT 0, created_at INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS dice_mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, user_id INTEGER,
            next_trigger INTEGER DEFAULT 0, end_time INTEGER DEFAULT 0, interval_minutes INTEGER DEFAULT 60)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS poll_votes (
            vote_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, peer_id INTEGER, poll_time INTEGER, date TEXT)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS info_blocks (peer_id INTEGER, key TEXT, text TEXT, PRIMARY KEY(peer_id, key))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS marriages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, user1 INTEGER, user2 INTEGER,
            created_at INTEGER DEFAULT 0, UNIQUE(peer_id, user1), UNIQUE(peer_id, user2))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS message_stats (
            user_id INTEGER, peer_id INTEGER, msg_count INTEGER DEFAULT 0,
            sticker_count INTEGER DEFAULT 0, dice_wins INTEGER DEFAULT 0, kmb_wins INTEGER DEFAULT 0,
            char_count INTEGER DEFAULT 0, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER, peer_id INTEGER, banned_by INTEGER, ban_until INTEGER DEFAULT 0,
            reason TEXT DEFAULT '', created_at INTEGER DEFAULT 0, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS kmb_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, initiator INTEGER, opponent INTEGER,
            state TEXT DEFAULT 'pending', message_id INTEGER DEFAULT 0,
            init_choice TEXT DEFAULT '', opp_choice TEXT DEFAULT '', created_at INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS badges (user_id INTEGER, peer_id INTEGER, emoji TEXT DEFAULT '', PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS message_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, cmid INTEGER, from_id INTEGER, ts INTEGER)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS join_stats (
            user_id INTEGER, peer_id INTEGER, first_join INTEGER DEFAULT 0, in_top INTEGER DEFAULT 1,
            PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS player_cards (
            user_id INTEGER PRIMARY KEY, name TEXT DEFAULT '', businesses TEXT DEFAULT '[]',
            realty TEXT DEFAULT '[]', property_val TEXT DEFAULT '', garage TEXT DEFAULT '',
            phone TEXT DEFAULT '', design TEXT DEFAULT '{}', verified INTEGER DEFAULT 0, updated_at INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS card_edit_state (
            user_id INTEGER, peer_id INTEGER, step TEXT, context TEXT, PRIMARY KEY(user_id, peer_id))""")
        # Аукционы
        CONN.execute("""CREATE TABLE IF NOT EXISTS auctions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, name TEXT, datetime_str TEXT,
            created_by INTEGER, created_at INTEGER, state TEXT DEFAULT 'pending', started_at INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS auction_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT, auction_id INTEGER, lot_number INTEGER, name TEXT,
            min_price REAL DEFAULT 20000000, photo_url TEXT, photo_att TEXT, state TEXT DEFAULT 'pending',
            winner_id INTEGER DEFAULT 0, final_price REAL DEFAULT 0, sold INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS auction_bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT, lot_id INTEGER, user_id INTEGER, amount REAL, bid_time INTEGER)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS auction_state (
            user_id INTEGER, peer_id INTEGER, step TEXT, context TEXT, PRIMARY KEY(user_id, peer_id))""")
        migrations = [
            "ALTER TABLE members ADD COLUMN warn_durations TEXT DEFAULT ''",
            "ALTER TABLE members ADD COLUMN last_vote_time INTEGER DEFAULT 0",
            "ALTER TABLE members ADD COLUMN mute_until INTEGER DEFAULT 0",
            "ALTER TABLE members ADD COLUMN mute_reason TEXT DEFAULT ''",
            "ALTER TABLE members ADD COLUMN warn_reasons TEXT DEFAULT ''",
            "ALTER TABLE message_stats ADD COLUMN kmb_wins INTEGER DEFAULT 0",
            "ALTER TABLE message_stats ADD COLUMN char_count INTEGER DEFAULT 0",
            "ALTER TABLE members ADD COLUMN who_name TEXT DEFAULT ''",
            "ALTER TABLE members ADD COLUMN who_ts INTEGER DEFAULT 0",
            "ALTER TABLE player_cards ADD COLUMN design TEXT DEFAULT '{}'",
            "ALTER TABLE player_cards ADD COLUMN verified INTEGER DEFAULT 0",
        ]
        for sql in migrations:
            try: CONN.execute(sql)
            except: pass
        CONN.commit()

def get_setting(peer, key, default=""):
    with DB_LOCK:
        row = CONN.execute("SELECT value FROM settings WHERE peer_id=? AND key=?", (peer, key)).fetchone()
    return row["value"] if row else default

def set_setting(peer, key, value):
    with DB_LOCK:
        CONN.execute("INSERT OR REPLACE INTO settings(peer_id, key, value) VALUES(?,?,?)", (peer, key, value))
        CONN.commit()

def get_chat_owner(peer):
    if VK is None: return OWNER_CACHE.get(peer, 0)
    if peer in OWNER_CACHE: return OWNER_CACHE[peer]
    oid = 0
    try:
        r = VK.messages.getConversationsById(peer_ids=peer)
        items = r.get("items", [])
        if items:
            oid = items[0].get("conversation", {}).get("chat_settings", {}).get("owner_id", 0) or 0
    except: pass
    if oid < 0:
        try:
            managers = VK.groups.getMembers(group_id=abs(oid), filter="managers")
            if managers and managers.get("items"): oid = managers["items"][0]
        except: pass
    if oid == 0:
        try:
            members_resp = VK.messages.getConversationMembers(peer_id=peer)
            for item in members_resp.get("items", []):
                if item.get("is_owner"):
                    oid = int(item.get("member_id", 0)); break
        except: pass
    OWNER_CACHE[peer] = oid
    return oid

def is_real_owner(sender, peer):
    return sender > 0 and (sender == CREATOR_ID or sender == LEADER_ID or sender == get_chat_owner(peer))

def is_moderator(sender, peer):
    if sender <= 0: return False
    if sender == CREATOR_ID or sender == LEADER_ID or sender == get_chat_owner(peer): return True
    return get_user_role(peer, sender) >= 1

def is_admin(sender, peer):
    if sender <= 0: return False
    if sender == CREATOR_ID or sender == LEADER_ID or sender == get_chat_owner(peer): return True
    return get_user_role(peer, sender) >= 2

def is_main_admin(sender, peer):
    if sender <= 0: return False
    if sender == CREATOR_ID or sender == LEADER_ID or sender == get_chat_owner(peer): return True
    return get_user_role(peer, sender) >= 3

def is_owner(sender, peer):
    if is_real_owner(sender, peer): return True
    return sender > 0 and get_user_role(peer, sender) >= 4

def send_msg(peer, text, attachments=None, keyboard=None):
    if VK is None or not peer: return False
    try:
        params = {'peer_id': peer, 'message': text, 'random_id': random.getrandbits(31)}
        if attachments: params['attachment'] = attachments
        if keyboard: params['keyboard'] = keyboard if isinstance(keyboard, str) else json.dumps(keyboard)
        VK.messages.send(**params)
        return True
    except Exception as e:
        LAST_ERR["msg"] = str(e)
        print("send error:", e)
        return False

def resolve_cmid(peer, sent_id):
    try:
        resp = VK.messages.getById(message_ids=[sent_id])
        items = resp.get("items", [])
        if items:
            cm = items[0].get("conversation_message_id")
            if cm: return int(cm)
    except: pass
    return sent_id

def edit_game_message(peer, game_id, text, keyboard_json=None, table="dice_games"):
    if keyboard_json is not None and not isinstance(keyboard_json, str):
        keyboard_json = json.dumps(keyboard_json)
    with DB_LOCK:
        row = CONN.execute("SELECT message_id FROM {} WHERE id=?".format(table), (game_id,)).fetchone()
    stored = row["message_id"] if row else 0
    kb = keyboard_json if keyboard_json else json.dumps({"inline": True, "buttons": []})
    try:
        VK.messages.edit(peer_id=peer, conversation_message_id=stored, message=text, keyboard=kb)
        return True
    except: pass
    try:
        VK.messages.edit(peer_id=peer, message_id=stored, message=text, keyboard=kb)
        return True
    except: pass
    try:
        new_id = VK.messages.send(peer_id=peer, message=text, keyboard=kb, random_id=random.getrandbits(31))
        cmid = resolve_cmid(peer, new_id)
        with DB_LOCK:
            CONN.execute("UPDATE {} SET message_id=? WHERE id=?".format(table), (cmid, game_id))
            CONN.commit()
        return True
    except: return False

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
def silent_mention(user_id): return "[https://vk.com/id{}|{}]".format(user_id, get_user_name(user_id))

def extract_targets(text, reply_from):
    ids = []
    for m in re.finditer(r"\[id(\d+)\|", text, re.I): ids.append(int(m.group(1)))
    for m in re.finditer(r"[@*]id(\d+)", text, re.I): ids.append(int(m.group(1)))
    for m in re.finditer(r"\b(\d{5,})\b", text): ids.append(int(m.group(1)))
    for m in re.finditer(r"https?://vk\.(com|ru)/id(\d+)", text, re.I): ids.append(int(m.group(2)))
    for m in re.finditer(r"https?://vk\.(com|ru)/([a-zA-Z0-9._]+)", text, re.I):
        sn = m.group(2)
        if sn.lower() not in ("id", "club", "public", "event", "app"):
            try:
                res = VK.utils.resolveScreenName(screen_name=sn)
                if res and res.get("type") == "user": ids.append(int(res["object_id"]))
            except: pass
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
    return ", ".join(parts)

# ===== СЛУЖЕБНЫЕ КОМАНДЫ =====
def _ls_segments(body):
    return [s.strip() for s in body.split(",") if s.strip()]

def _ls_date_ts(dstr):
    try:
        d, m, y = [int(x) for x in dstr.split(".")]
        return int(datetime.datetime(y, m, d, 12, 0, 0, tzinfo=MSK_TZ).timestamp())
    except Exception:
        return None

def _ls_user(seg):
    m = re.search(r"\[id(\d+)\|", seg)
    if m: return int(m.group(1)), re.sub(r"\[id\d+\|[^\]]*\]", " ", seg)
    m = re.search(r"@id(\d+)", seg, re.I)
    if m: return int(m.group(1)), re.sub(r"@id\d+", " ", seg, flags=re.I)
    m = re.search(r"https?://vk\.(?:com|ru)/id(\d+)", seg, re.I)
    if m: return int(m.group(1)), re.sub(r"https?://vk\.(?:com|ru)/id\d+", " ", seg, flags=re.I)
    m = re.search(r"@(\d{6,})", seg)
    if m: return int(m.group(1)), re.sub(r"@\d{6,}", " ", seg)
    return None, seg

def _ls_peer(seg):
    m = re.search(r"\b(2\d{9})\b", seg)
    return int(m.group(1)) if m else None

def _ls_apply_firstlogin(body):
    out = []
    for seg in _ls_segments(body):
        uid, rest = _ls_user(seg); peer_id = _ls_peer(seg)
        md = re.search(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", seg)
        ts = _ls_date_ts(md.group(1)) if md else None
        if not uid or not peer_id or ts is None:
            out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        with DB_LOCK:
            CONN.execute("INSERT OR IGNORE INTO join_stats(user_id, peer_id, first_join, in_top) VALUES(?,?,?,1)", (uid, peer_id, ts))
            CONN.execute("UPDATE join_stats SET first_join=?, in_top=1 WHERE user_id=? AND peer_id=?", (ts, uid, peer_id))
            CONN.commit()
        out.append("✅ id{} → первый вход {} (чат {})".format(uid, md.group(1), peer_id))
    return "\n".join(out) or "✅ Готово"

def _ls_apply_lastlogin(body):
    out = []
    for seg in _ls_segments(body):
        uid, rest = _ls_user(seg); peer_id = _ls_peer(seg)
        md = re.search(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", seg)
        ts = _ls_date_ts(md.group(1)) if md else None
        if not uid or not peer_id or ts is None:
            out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        with DB_LOCK:
            CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (uid, peer_id))
            CONN.execute("UPDATE members SET join_time=? WHERE user_id=? AND peer_id=?", (ts, uid, peer_id))
            CONN.commit()
        out.append("✅ id{} → последний вход {} (чат {})".format(uid, md.group(1), peer_id))
    return "\n".join(out) or "✅ Готово"

def _ls_apply_topmsg(body):
    out = []
    for seg in _ls_segments(body):
        uid, rest = _ls_user(seg); peer_id = _ls_peer(seg)
        tmp = re.sub(r"\b2\d{9}\b", " ", rest)
        nums = [int(x) for x in re.findall(r"\b(\d+)\b", tmp)]
        if uid is None:
            if len(nums) >= 3: uid, chars, msgs = nums[0], nums[1], nums[2]
            else:
                out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        else:
            if len(nums) >= 2: chars, msgs = nums[0], nums[1]
            else:
                out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        if peer_id is None:
            out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        with DB_LOCK:
            CONN.execute("INSERT OR IGNORE INTO message_stats(user_id, peer_id, msg_count, sticker_count, dice_wins, kmb_wins, char_count) VALUES(?,?,0,0,0,0,0)", (uid, peer_id))
            CONN.execute("UPDATE message_stats SET char_count=?, msg_count=? WHERE user_id=? AND peer_id=?", (chars, msgs, uid, peer_id))
            CONN.commit()
        out.append("✅ id{} → символы={}, сообщения={} (чат {})".format(uid, chars, msgs, peer_id))
    return "\n".join(out) or "✅ Готово"

def _ls_apply_top(body, field):
    out = []
    for seg in _ls_segments(body):
        uid, rest = _ls_user(seg); peer_id = _ls_peer(seg)
        tmp = re.sub(r"\b2\d{9}\b", " ", rest)
        nums = [int(x) for x in re.findall(r"\b(\d+)\b", tmp)]
        if uid is None:
            if len(nums) >= 2: uid, val = nums[0], nums[1]
            else:
                out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        else:
            val = nums[0] if nums else None
        if peer_id is None or val is None:
            out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        with DB_LOCK:
            CONN.execute("INSERT OR IGNORE INTO message_stats(user_id, peer_id, msg_count, sticker_count, dice_wins, kmb_wins, char_count) VALUES(?,?,0,0,0,0,0)", (uid, peer_id))
            CONN.execute("UPDATE message_stats SET {}=? WHERE user_id=? AND peer_id=?".format(field), (val, uid, peer_id))
            CONN.commit()
        out.append("✅ id{} → {} = {} (чат {})".format(uid, field, val, peer_id))
    return "\n".join(out) or "✅ Готово"

def _ls_apply_rbrak(body):
    out = []
    now_ts = int(time.time())
    for seg in _ls_segments(body):
        uid, rest = _ls_user(seg); peer_id = _ls_peer(seg)
        tmp = re.sub(r"\b2\d{9}\b", " ", rest)
        nums = [int(x) for x in re.findall(r"\b(\d+)\b", tmp)]
        if uid is None:
            if len(nums) >= 2: uid, days = nums[0], nums[1]
            else:
                out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        else:
            days = nums[0] if nums else None
        if peer_id is None or days is None:
            out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        with DB_LOCK:
            row = CONN.execute("SELECT id FROM marriages WHERE peer_id=? AND (user1=? OR user2=?)", (peer_id, uid, uid)).fetchone()
            if not row:
                out.append("❌ id{} не состоит в браке в чате {}".format(uid, peer_id)); continue
            CONN.execute("UPDATE marriages SET created_at=? WHERE id=?", (now_ts - days * 86400, row["id"]))
            CONN.commit()
        out.append("✅ id{} → брак {} дн. (чат {})".format(uid, days, peer_id))
    return "\n".join(out) or "✅ Готово"

def handle_creator_ls(peer, text):
    t = text.strip(); low = t.lower()
    if low.startswith("/firstlogin"):
        send_msg(peer, _ls_apply_firstlogin(t[len("/firstlogin"):].strip()))
    elif low.startswith("/lastlogin"):
        send_msg(peer, _ls_apply_lastlogin(t[len("/lastlogin"):].strip()))
    elif low.startswith("/topmsg"):
        send_msg(peer, _ls_apply_topmsg(t[len("/topmsg"):].strip()))
    elif low.startswith("/topemj"):
        send_msg(peer, _ls_apply_top(t[len("/topemj"):].strip(), "sticker_count"))
    elif low.startswith("/rbrak"):
        send_msg(peer, _ls_apply_rbrak(t[len("/rbrak"):].strip()))
    else:
        send_msg(peer, "ℹ️ Неизвестная служебная команда.")

def sender_if_needed(peer):
    return peer

def sync_members(peer):
    now = time.time()
    if peer in MEMBER_SYNC_CACHE and (now - MEMBER_SYNC_CACHE[peer]) < 300: return
    try:
        members_resp = VK.messages.getConversationMembers(peer_id=peer)
        items = members_resp.get("items", [])
        today = get_msk_now().strftime("%Y-%m-%d")
        current_members = set()
        for item in items:
            uid = int(item.get("member_id", 0))
            if uid > 0: current_members.add(uid)
        with DB_LOCK:
            for uid in current_members:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id, last_active, streak) VALUES(?,?,?,?)", (uid, peer, today, 0))
            all_db = CONN.execute("SELECT user_id FROM members WHERE peer_id=?", (peer,)).fetchall()
            for row in all_db:
                if row["user_id"] not in current_members:
                    CONN.execute("DELETE FROM members WHERE user_id=? AND peer_id=?", (row["user_id"], peer))
            now_ts = int(time.time())
            for uid in current_members:
                CONN.execute("INSERT OR IGNORE INTO join_stats(user_id, peer_id, first_join, in_top) VALUES(?,?,?,1)", (uid, peer, now_ts))
            CONN.execute("UPDATE members SET join_time=? WHERE peer_id=? AND (join_time IS NULL OR join_time=0)", (now_ts, peer))
            CONN.commit()
        MEMBER_SYNC_CACHE[peer] = now
    except: pass

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

def ls_help_text(user_id):
    lines = [
        "📖 Команды, доступные тебе в ЛС с ботом:",
        "1. Мд карта — посмотреть свою карту.",
        "2. Мд карта редактировать — редактировать карту (данные, цвет, фото).",
        "3. Мд очистить карту [параметр] — очистить свою карту (параметры: бизнесы, недвижимость, имущество, гараж, телефон, фото, имя; без параметра — всё кроме цвета).",
        "4. Мд команды — этот список.",
    ]
    if is_inspector(user_id) or user_id in (CREATOR_ID, LEADER_ID):
        lines += [
            "",
            "🕵 Скрытые команды проверяющего:",
            "/verify @ - подтвердить карту.",
            "/deny @ - отменить подтверждение.",
            "/card @ - посмотреть карту любого.",
            "/clearcard @ [параметр] - очистить любую карту.",
        ]
    if is_auctioneer(user_id) or user_id in (CREATOR_ID, LEADER_ID):
        lines += [
            "",
            "📈 Скрытые команды аукционера:",
            "/аукцион - редактор аукционов.",
            "/стопаукцион (номер чата) - отключить аукцион.",
        ]
    if user_id in (CREATOR_ID, LEADER_ID):
        lines += [
            "",
            "👑 Скрытые команды создателя/лидера:",
            "/inspector @ - назначить/снять проверяющего.",
            "/аукционер @ (номер чата) - назначить/снять аукционера.",
            "/аукционеры - список всех аукционеров.",
            "/проверяющие - список всех проверяющих.",
            "/setkto @ <слова> <номер чата> - поставить статус «кто я».",
            "/чаты - список бесед бота.",
            "/firstlogin, /lastlogin, /topmsg, /topemj, /rbrak - служебный занос данных.",
        ]
    return "\n".join(lines)

def get_bdate_map(member_ids):
    bdate_map = {}
    if not member_ids: return bdate_map
    ph = ",".join("?" * len(member_ids))
    with DB_LOCK:
        rows = CONN.execute("SELECT user_id, bdate FROM birthdays WHERE bdate IS NOT NULL AND bdate!='' AND user_id IN ({})".format(ph), member_ids).fetchall()
    for r in rows:
        if r["user_id"] not in bdate_map: bdate_map[r["user_id"]] = r["bdate"]
    return bdate_map

def fill_bdates_from_vk(peer, member_ids, bdate_map):
    missing = [u for u in member_ids if u not in bdate_map]
    for i in range(0, len(missing), 100):
        chunk = missing[i:i+100]
        try: users_data = VK.users.get(user_ids=",".join(map(str, chunk)), fields="bdate")
        except Exception: users_data = []
        for u in users_data:
            bd = (u.get("bdate") or "").strip()
            if bd:
                bdate_map[u["id"]] = bd
                with DB_LOCK:
                    CONN.execute("INSERT OR REPLACE INTO birthdays(user_id, peer_id, bdate, updated_at) VALUES(?,?,?,?)", (u["id"], peer, bd, int(time.time())))
                    CONN.commit()

def check_birthdays(peer):
    now_msk = get_msk_now()
    today_str = now_msk.strftime("%Y-%m-%d")
    current_year = now_msk.year
    if get_setting(peer, "last_bday_check_date", "") == today_str: return
    sync_members(peer)
    with DB_LOCK:
        member_ids = [r["user_id"] for r in CONN.execute("SELECT user_id FROM members WHERE peer_id=?", (peer,)).fetchall()]
    if not member_ids:
        set_setting(peer, "last_bday_check_date", today_str); return
    bdate_map = get_bdate_map(member_ids)
    for user_id in member_ids:
        bdate = bdate_map.get(user_id)
        if not bdate: continue
        parts = bdate.split(".")
        if len(parts) >= 2 and int(parts[0]) == now_msk.day and int(parts[1]) == now_msk.month:
            with DB_LOCK:
                row = CONN.execute("SELECT 1 FROM birthday_congratulated WHERE user_id=? AND peer_id=? AND year=?", (user_id, peer, current_year)).fetchone()
            if row: continue
            if user_id == LEADER_ID:
                text = LEADER_BDAY_TEXT.format(mention=mention(user_id))
            else:
                custom = get_setting(peer, "birthday_text", "")
                text = (custom.rstrip() + "\n\n" + mention(user_id)) if custom else DEFAULT_BDAY_TEXT.format(mention=mention(user_id))
            send_msg(peer, text)
            with DB_LOCK:
                CONN.execute("INSERT OR REPLACE INTO birthday_congratulated(user_id, peer_id, year, congratulated_at) VALUES(?,?,?,?)", (user_id, peer, current_year, int(time.time())))
                CONN.commit()
    set_setting(peer, "last_bday_check_date", today_str)

def execute_top_clean(peer, targets, top_types):
    with DB_LOCK:
        if targets:
            for t in targets:
                for field in top_types:
                    CONN.execute("UPDATE message_stats SET {}=0 WHERE user_id=? AND peer_id=?".format(field), (t, peer))
        else:
            for field in top_types:
                CONN.execute("UPDATE message_stats SET {}=0 WHERE peer_id=?".format(field), (peer,))
        CONN.commit()

def handle_inspector(peer, sender, raw):
    targets = extract_targets(raw, 0)
    if not targets:
        send_msg(peer, "❌ Формат: /inspector @юзер (повторно — снять роль)")
        return
    t = targets[0]
    if t in (CREATOR_ID, LEADER_ID):
        send_msg(peer, "❌ У создателя и лидера доступ есть всегда.")
        return
    key = "inspector_{}".format(t)
    if get_setting(0, key, "0") == "1":
        set_setting(0, key, "0")
        send_msg(peer, "✅ С {} снята роль проверяющего.".format(silent_mention_badge(t, peer)))
        send_msg(t, "📋 Вас сняли с роли проверяющего. Команды /verify, /deny, /card и /clearcard больше недоступны.")
    else:
        set_setting(0, key, "1")
        send_msg(peer, "✅ {} назначен проверяющим.".format(silent_mention_badge(t, peer)))
        send_msg(t, INSPECTOR_WELCOME)

def handle_auctioneer(peer, sender, raw):
    parts = raw.strip().split()
    if not parts:
        send_msg(peer, "❌ Формат: /аукционер @юзер (номер чата)")
        return
    targets = extract_targets(raw, 0)
    if not targets:
        send_msg(peer, "❌ Не найден пользователь.")
        return
    t = targets[0]
    if t in (CREATOR_ID, LEADER_ID):
        send_msg(peer, "❌ У создателя и лидера доступ есть всегда.")
        return
    key = "auctioneer_{}".format(t)
    if get_setting(0, key, "0") == "1":
        set_setting(0, key, "0")
        send_msg(peer, "✅ С {} снята роль аукционера.".format(silent_mention_badge(t, peer)))
        send_msg(t, "📈 Вас сняли с роли аукционера. Команды /аукцион и /стопаукцион больше недоступны.")
    else:
        set_setting(0, key, "1")
        send_msg(peer, "✅ {} назначен аукционером.".format(silent_mention_badge(t, peer)))
        send_msg(t, AUCTIONEER_WELCOME)

def handle_list_inspectors(peer, sender):
    inspectors = []
    with DB_LOCK:
        rows = CONN.execute("SELECT key FROM settings WHERE key LIKE 'inspector_%' AND value='1'").fetchall()
    for r in rows:
        uid = int(r["key"].replace("inspector_", ""))
        inspectors.append(uid)
    if not inspectors:
        send_msg(peer, "📋 Проверяющих нет.")
        return
    lines = ["📋 Список проверяющих:\n"]
    for i, uid in enumerate(inspectors, 1):
        lines.append("{}. | {} |".format(i, silent_mention_badge(uid, peer)))
    send_msg(peer, "\n".join(lines))

def handle_list_auctioneers(peer, sender):
    auctioneers = get_all_auctioneers()
    if not auctioneers:
        send_msg(peer, "📈 Аукционеров нет.")
        return
    lines = ["📈 Список аукционеров:\n"]
    for i, uid in enumerate(auctioneers, 1):
        lines.append("{}. | {} |".format(i, silent_mention_badge(uid, peer)))
    send_msg(peer, "\n".join(lines))

INSPECTOR_WELCOME = ("Вас назначили проверяющим📋\n"
                     "Теперь вы можете использовать скрытые команды (только в личке со мной❗).\n"
                     "/verify @ - подтвердить карту.\n"
                     "/deny @ - отменить подтверждение.\n"
                     "/card @ - посмотреть карту любого.\n"
                     "/clearcard @ [праметр] - очистить любую карту.\n\n"
                     "параметры: бизнесы, недвижимость, имущество, гараж, телефон, фото, имя. "
                     "(если не указать то очистит все кроме цвета)")

AUCTIONEER_WELCOME = ("Вас назначили аукционером📈\n"
                      "Теперь вы можете использовать скрытые команды (только в личке со мной❗).\n"
                      "/аукцион - редактор аукционов.\n"
                      "/стопаукцион (номер чата) - принудительно отключает идущий аукцион в чате.")

def open_auction_menu(peer, sender):
    kb = {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "Активные", "payload": json.dumps({"cmd": "auction_active"})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Создать", "payload": json.dumps({"cmd": "auction_create"})}, "color": "positive"}],
        [{"action": {"type": "callback", "label": "Удалить", "payload": json.dumps({"cmd": "auction_delete"})}, "color": "negative"}],
        [{"action": {"type": "callback", "label": "Редактировать", "payload": json.dumps({"cmd": "auction_edit"})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Анонс", "payload": json.dumps({"cmd": "auction_announce"})}, "color": "positive"}],
        [{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "auction_cancel"})}, "color": "negative"}]
    ]}
    try:
        msg_id = VK.messages.send(peer_id=peer, message="Выберите действие:", keyboard=json.dumps(kb), random_id=random.getrandbits(31))
        cmid = resolve_cmid_retry(peer, msg_id)
    except Exception:
        msg_id = None; cmid = None
    set_auction_state(sender, peer, "menu", {"msg_cmid": cmid, "msg_id": msg_id})

def open_edit_menu(peer, sender):
    try:
        msg_id = VK.messages.send(peer_id=peer, message=MAIN_CARD_TEXT, keyboard=json.dumps(card_edit_main_kb()), random_id=random.getrandbits(31))
        cmid = resolve_cmid_retry(peer, msg_id)
    except Exception:
        msg_id = None; cmid = None
    set_card_state(sender, peer, "edit_menu", {"msg_cmid": cmid, "msg_id": msg_id})

def handle_ls_card(peer, sender, cmd, args):
    if cmd == "карта":
        targets = extract_targets(" ".join(args), 0)
        target_id = targets[0] if (targets and sender in (CREATOR_ID, LEADER_ID)) else sender
        send_card_to(peer, target_id)
    elif cmd == "карта_редактировать":
        open_edit_menu(peer, sender)

def apply_clear_param(peer, target_id, param):
    if param == "фото":
        set_design(target_id, photo="")
        return "✅ Фото карты {} сброшено.".format(silent_mention_badge(target_id, peer))
    field = PARAM_MAP[param]
    set_card_field(target_id, **{field: FIELD_DEFAULT[field]})
    return "✅ Очищено поле «{}» карты {}.".format(param, silent_mention_badge(target_id, peer))

def handle_clearcard(peer, sender, raw):
    targets = extract_targets(raw, 0)
    if not targets:
        send_msg(peer, "❌ Формат: /clearcard @юзер [параметр]")
        return
    t = targets[0]
    param = None
    extra = []
    for tok in re.split(r"\s+", raw):
        tl = tok.strip(".,!?").lower()
        if tl in PARAM_MAP:
            if param is None: param = tl
        elif not re.match(r"^[\[@]", tok) and not re.search(r"vk\.(com|ru)/", tok) and not re.match(r"^\d{5,}$", tok):
            extra.append(tok)
    if param is None and extra:
        send_msg(peer, "❌ Нет такого параметра: {}. Доступные: {}.".format(" ".join(extra), PARAM_HINT))
        return
    if param:
        send_msg(peer, apply_clear_param(peer, t, param))
    else:
        clear_card_data(t)
        send_msg(peer, "✅ Карта {} очищена (кроме цвета).".format(silent_mention_badge(t, peer)))

def handle_card_ls(peer, sender, raw):
    targets = extract_targets(raw, 0)
    if not targets:
        send_msg(peer, "❌ Формат: /card @юзер")
        return
    send_card_to(peer, targets[0])

def handle_stop_auction(peer, sender, raw):
    parts = raw.strip().split()
    if not parts or not parts[0].isdigit():
        send_msg(peer, "❌ Формат: /стопаукцион (номер чата)")
        return
    peer_id = int(parts[0])
    auctions = get_auctions_for_peer(peer_id)
    if not auctions:
        send_msg(peer, "❌ В этом чате нет активных аукционов.")
        return
    for a in auctions:
        stop_auction(a["id"])
    send_msg(peer, "✅ Аукционы в чате {} остановлены.".format(peer_id))

def handle_setkto(peer, sender, raw):
    m_id = re.search(r"(?:@|https?://vk\.(?:com|ru)/|https?://m\.vk\.(?:com|ru)/|\[id)(\d+|[a-zA-Z0-9._]+)", raw, re.I)
    if not m_id:
        send_msg(peer, "❌ Не найден ID или ссылка."); return
    target_str = m_id.group(1)
    if target_str.isdigit():
        target_id = int(target_str)
    else:
        try:
            res = VK.utils.resolveScreenName(screen_name=target_str)
            if res and res.get("type") == "user": target_id = int(res["object_id"])
            else:
                send_msg(peer, "❌ Не удалось найти пользователя по нику."); return
        except:
            send_msg(peer, "❌ Ошибка резолва ника."); return
    m_peer = re.search(r"\b(2\d{9})\b", raw)
    if not m_peer:
        send_msg(peer, "❌ Не найден номер чата."); return
    target_peer = int(m_peer.group(1))
    clean_raw = re.sub(r"(?:@|https?://vk\.(?:com|ru)/|https?://m\.vk\.(?:com|ru)/|\[id)\d+\|?[^\]]*\]?", "", raw, flags=re.I).strip()
    clean_raw = re.sub(r"\b2\d{9}\b", "", clean_raw).strip()
    if not clean_raw:
        send_msg(peer, "❌ Не указаны слова статуса."); return
    clean_status = re.sub(r"[^\w\sа-яА-ЯёЁ]", "", clean_raw).strip().lower()
    final_status = ""
    for key, val in LEGEND_SETKTO.items():
        if key in clean_status:
            final_status = val; break
    if not final_status:
        words = clean_raw.split()
        if len(words) < 2:
            send_msg(peer, "❌ Для обычного статуса нужно прилагательное и существительное."); return
        adj, noun = words[0].lower(), words[1].lower()
        if adj not in WHO_ADJ or noun not in WHO_NOUN:
            send_msg(peer, "❌ Слова должны быть из списков бота!\nПрилагательное найдено: {}\nСуществительное найдено: {}".format(adj in WHO_ADJ, noun in WHO_NOUN))
            return
        final_status = "{} {}".format(adj_form(adj, noun_gender(noun)), noun)
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (target_id, target_peer))
        CONN.execute("UPDATE members SET who_name=?, who_ts=? WHERE user_id=? AND peer_id=?", (final_status, int(time.time()), target_id, target_peer))
        CONN.commit()
    send_msg(peer, "✅ Статус для id{} в чате {} установлен: {}".format(target_id, target_peer, final_status))

def handle_verify(peer, sender, raw, want):
    targets = extract_targets(raw, 0)
    if not targets:
        send_msg(peer, "❌ Формат: /{} @юзер".format("verify" if want else "deny"))
        return
    t = targets[0]
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO player_cards(user_id) VALUES(?)", (t,))
        CONN.execute("UPDATE player_cards SET verified=? WHERE user_id=?", (1 if want else 0, t))
        CONN.commit()
    if want:
        send_msg(peer, "✅ Карточка {} подтверждена.".format(silent_mention_badge(t, peer)))
    else:
        send_msg(peer, "✅ Подтверждение карточки {} снято.".format(silent_mention_badge(t, peer)))

def do_clear_card_command(peer, sender, args):
    param = None
    for a in args:
        al = a.strip(".,!?").lower()
        if al in PARAM_MAP:
            param = al; break
    if args and param is None:
        send_msg(peer, "❌ Нет такого параметра: {}. Доступные параметры: {} (или без параметра — очистит всё кроме цвета).".format(" ".join(args), PARAM_HINT))
        return
    if param:
        if param == "фото":
            set_design(sender, photo="")
            send_msg(peer, "✅ Фото вашей карты сброшено.")
        else:
            field = PARAM_MAP[param]
            set_card_field(sender, **{field: FIELD_DEFAULT[field]})
            send_msg(peer, "✅ Очищено поле «{}» вашей карточки.".format(param))
        return
    CLEAR_PENDING[(peer, sender)] = int(time.time())
    send_msg(peer, CLEAR_CONFIRM_TEXT)

def check_clear_pending(peer, sender, text):
    ts = CLEAR_PENDING.get((peer, sender))
    if ts is None:
        return False
    low = text.strip().lower()
    age = time.time() - ts
    if age > 60:
        CLEAR_PENDING.pop((peer, sender), None)
        if low in ("подтвердить", "отказаться"):
            return True
        return False
    if low == "подтвердить":
        CLEAR_PENDING.pop((peer, sender), None)
        clear_card_data(sender)
        send_msg(peer, "✅ Карточка очищена (кроме цвета).")
        return True
    if low in ("отказаться", "отмена"):
        CLEAR_PENDING.pop((peer, sender), None)
        send_msg(peer, "❌ Очистка отменена.")
        return True
    return False

def handle_message(peer, sender, text, msg_obj):
    first_line = text.split("\n")[0].strip()
    first = norm(first_line)

    if peer < 2000000000:
        low = text.strip().lower()
        is_boss = sender in (CREATOR_ID, LEADER_ID) and peer == sender
        is_insp = is_inspector(sender) and peer == sender
        is_auct = is_auctioneer(sender) and peer == sender
        if is_boss:
            if low == "/чаты":
                send_msg(peer, "⏳ Загрузка списка бесед...")
                chats = get_all_bot_chats()
                if not chats:
                    send_msg(peer, "📭 Бот пока не зафиксировал ни одной беседы."); return
                lines = []; idx = 1
                for i in range(0, len(chats), 100):
                    chunk = chats[i:i+100]
                    try:
                        convos = VK.messages.getConversationsById(peer_ids=chunk)
                        for item in convos.get("items", []):
                            p_id = item.get("peer", {}).get("id", 0)
                            title = item.get("chat_settings", {}).get("title", "Недоступно")
                            owner = item.get("chat_settings", {}).get("owner_id", 0)
                            if owner > 0: owner_link = silent_mention(owner)
                            elif owner < 0: owner_link = "[https://vk.com/club{}|Группа {}]".format(abs(owner), abs(owner))
                            else: owner_link = "Нет/ЛС"
                            member_count = "?"
                            try:
                                mresp = VK.messages.getConversationMembers(peer_id=p_id)
                                member_count = str(len(mresp.get("items", [])))
                                time.sleep(0.15)
                            except: pass
                            lines.append("{}. {} | {} | {} | {} уч.".format(idx, p_id, title, owner_link, member_count))
                            idx += 1
                    except Exception as e:
                        lines.append("Ошибка: {}".format(e))
                msg_text = "📊 Список бесед с ботом:\n" + "\n".join(lines)
                for i in range(0, len(msg_text), 4000):
                    send_msg(peer, msg_text[i:i+4000])
                return
            elif low.startswith("/setkto"):
                handle_setkto(peer, sender, text[len("/setkto"):].strip())
                return
            elif low.startswith("/inspector"):
                handle_inspector(peer, sender, text[len("/inspector"):].strip())
                return
            elif low.startswith("/аукционер"):
                handle_auctioneer(peer, sender, text[len("/аукционер"):].strip())
                return
            elif low == "/аукционеры":
                handle_list_auctioneers(peer, sender)
                return
            elif low == "/проверяющие":
                handle_list_inspectors(peer, sender)
                return
            elif low.startswith("/clearcard"):
                handle_clearcard(peer, sender, text[len("/clearcard"):].strip())
                return
            elif low.startswith("/card"):
                handle_card_ls(peer, sender, text[len("/card"):].strip())
                return
            elif low.startswith("/verify"):
                handle_verify(peer, sender, text[len("/verify"):].strip(), True)
                return
            elif low.startswith("/deny"):
                handle_verify(peer, sender, text[len("/deny"):].strip(), False)
                return
            elif low.startswith("/стопаукцион"):
                handle_stop_auction(peer, sender, text[len("/стопаукцион"):].strip())
                return
            elif low == "/аукцион":
                open_auction_menu(peer, sender)
                return
            elif text.strip().startswith("/"):
                handle_creator_ls(peer, text)
                return
        elif is_insp:
            if low.startswith("/clearcard"):
                handle_clearcard(peer, sender, text[len("/clearcard"):].strip())
                return
            elif low.startswith("/card"):
                handle_card_ls(peer, sender, text[len("/card"):].strip())
                return
            elif low.startswith("/verify"):
                handle_verify(peer, sender, text[len("/verify"):].strip(), True)
                return
            elif low.startswith("/deny"):
                handle_verify(peer, sender, text[len("/deny"):].strip(), False)
                return
            elif low.startswith("/"):
                send_msg(peer, "❌ Неизвестная команда: {}\n\n".format(text.strip().split("\n")[0]) + ls_help_text(sender))
                return
        elif is_auct:
            if low.startswith("/стопаукцион"):
                handle_stop_auction(peer, sender, text[len("/стопаукцион"):].strip())
                return
            elif low == "/аукцион":
                open_auction_menu(peer, sender)
                return
            elif low.startswith("/"):
                send_msg(peer, "❌ Неизвестная команда: {}\n\n".format(text.strip().split("\n")[0]) + ls_help_text(sender))
                return
        if check_clear_pending(peer, sender, text):
            return
        if first.startswith("мд "):
            pn = first[3:].strip().split()
            if pn:
                c2 = "_".join(pn[:2])
                if c2 == "карта_редактировать":
                    handle_ls_card(peer, sender, "карта_редактировать", pn[2:]); return
                if c2 == "очистить_карту":
                    do_clear_card_command(peer, sender, pn[2:]); return
                if pn[0] == "карта":
                    handle_ls_card(peer, sender, "карта", pn[1:]); return
                if pn[0] == "команды":
                    send_msg(peer, ls_help_text(sender)); return
                send_msg(peer, "❌ Неизвестная команда: `мд {}`\n\n".format(" ".join(pn)) + ls_help_text(sender))
                return
        if text.strip().startswith("/"):
            send_msg(peer, "❌ Неизвестная команда: {}\n\n".format(text.strip().split("\n")[0]) + ls_help_text(sender))
            return
        if handle_card_input(sender, peer, text, cmid=msg_obj.get("conversation_message_id"), attachments=msg_obj.get("attachments")):
            return
        if handle_auction_input(sender, peer, text, cmid=msg_obj.get("conversation_message_id"), attachments=msg_obj.get("attachments")):
            return
        return

    # Обработка ставок в аукционе
    if peer >= 2000000000:
        auctions = get_auctions_for_peer(peer)
        for auction in auctions:
            if auction["state"] == "active":
                active_lot = get_active_lot_state(auction["id"])
                if active_lot:
                    amount = parse_bid_amount(text.strip())
                    if amount:
                        latest = get_latest_bid(active_lot["id"])
                        current_price = latest["amount"] if latest else active_lot["min_price"]
                        min_step = get_min_step(current_price)
                        if amount < current_price + min_step:
                            send_msg(peer, "{}, ошибка, минимальный перебив {}!".format(silent_mention_badge(sender, peer), format_price(min_step)))
                            return
                        add_bid(active_lot["id"], sender, amount)
                        send_msg(peer, "{}, ставка {} установлена! У остальных есть 5 минут чтобы ее перебить.".format(
                            silent_mention_badge(sender, peer), format_price(amount)))
                        set_setting(peer, "auction_bid_time_{}".format(active_lot["id"]), str(int(time.time())))
                        return

    if not first.startswith("мд "):
        if check_clear_pending(peer, sender, text):
            return
        if handle_card_input(sender, peer, text, cmid=msg_obj.get("conversation_message_id"), attachments=msg_obj.get("attachments")):
            return
        if handle_auction_input(sender, peer, text, cmid=msg_obj.get("conversation_message_id"), attachments=msg_obj.get("attachments")):
            return
        return

    if sender > 0:
        is_sticker = any(att.get("type") == "sticker" for att in (msg_obj.get("attachments") or []))
        try: increment_msg_stat(peer, sender, is_sticker, len(text or ""))
        except: pass

    action = msg_obj.get("action", {})
    if action.get("type") == "chat_invite_user":
        user_id = action.get("member_id")
        if not user_id: return
        with DB_LOCK:
            ban_row = CONN.execute("SELECT ban_until FROM bans WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
        if ban_row and (ban_row["ban_until"] == 0 or ban_row["ban_until"] > int(time.time())):
            try:
                VK.messages.removeChatUser(chat_id=peer-2000000000, member_id=user_id)
                send_msg(peer, "🚫 {} забанен.".format(silent_mention_badge(user_id, peer)))
            except: pass
            return
        with DB_LOCK:
            row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
            now_ts = int(time.time())
            if row:
                CONN.execute("UPDATE members SET join_time=?, warnings=0, warn_durations='', warn_expiry=0 WHERE user_id=? AND peer_id=?", (now_ts, user_id, peer))
            else:
                CONN.execute("INSERT INTO members(user_id, peer_id, join_time, warnings, warn_durations, warn_expiry) VALUES(?,?,?,0,'',0)", (user_id, peer, now_ts))
            CONN.execute("INSERT OR IGNORE INTO join_stats(user_id, peer_id, first_join, in_top) VALUES(?,?,?,1)", (user_id, peer, now_ts))
            CONN.execute("UPDATE join_stats SET in_top=1 WHERE user_id=? AND peer_id=?", (user_id, peer))
            CONN.commit()
        greeting = get_setting(peer, "greeting_text", "")
        if greeting: send_msg(peer, greeting + "\n\n" + mention(user_id))
        elif get_setting(peer, "control_active") == "1":
            send_msg(peer, "Добро пожаловать, {}! 🎉\nУстанови ник: `Мд ник <твой_ник>`".format(mention(user_id)))
        return

    if action.get("type") == "chat_kick_user":
        user_id = action.get("member_id")
        if user_id:
            with DB_LOCK:
                CONN.execute("DELETE FROM members WHERE user_id=? AND peer_id=?", (user_id, peer)); CONN.commit()
            admin_chat_clean = "".join(filter(str.isdigit, get_setting(peer, "admin_report_chat", "")))
            if len(admin_chat_clean) >= 9:
                chat_name = "Неизвестная беседа"
                try:
                    conv = VK.messages.getConversationsById(peer_ids=peer)
                    if conv.get("items"): chat_name = conv["items"][0].get("chat_settings", {}).get("title", "Неизвестная беседа")
                except: pass
                try: send_msg(int(admin_chat_clean), "🚨 Игрок {} был исключен из беседы '{}'.".format(silent_mention_badge(user_id, peer), chat_name))
                except: pass
        return

    with DB_LOCK:
        mute_row = CONN.execute("SELECT mute_until FROM members WHERE user_id=? AND peer_id=?", (sender, peer)).fetchone()
    if mute_row and mute_row["mute_until"] and mute_row["mute_until"] > time.time():
        if not is_moderator(sender, peer):
            try:
                cmid = msg_obj.get("conversation_message_id")
                if cmid: VK.messages.delete(peer_id=peer, conversation_message_ids=[cmid], delete_for_all=1)
            except: pass
            return

    if get_setting(peer, "silence_mode", "0") == "1":
        if not is_admin(sender, peer):
            try:
                cmid = msg_obj.get("conversation_message_id")
                if cmid: VK.messages.delete(peer_id=peer, conversation_message_ids=[cmid], delete_for_all=1)
            except: pass
            return

    update_member_activity(peer, sender)

    if check_clear_pending(peer, sender, text):
        return

    pend_raw = get_setting(peer, "top_clean_pending", "")
    if pend_raw:
        try: pend = json.loads(pend_raw)
        except: pend = None
        if pend:
            low = text.strip().lower()
            if low in ["подтвердить", "отменить"]:
                if int(time.time()) - pend.get("ts", 0) > 60:
                    set_setting(peer, "top_clean_pending", "")
                    send_msg(peer, "⏰ Время подтверждения истекло. Очистка топа отменена."); return
                if pend.get("asker") != sender:
                    send_msg(peer, "⛔ Подтвердить может только тот, кто запустил очистку."); return
                set_setting(peer, "top_clean_pending", "")
                if low == "отменить":
                    send_msg(peer, "❌ Очистка топа отменена."); return
                execute_top_clean(peer, pend.get("targets") or None, pend.get("types") or ["msg_count", "char_count", "sticker_count", "dice_wins", "kmb_wins"])
                send_msg(peer, "✅ Топ очищен."); return

    if sender > 0:
        cmid0 = msg_obj.get("conversation_message_id") or 0
        if cmid0:
            with DB_LOCK:
                CONN.execute("INSERT INTO message_cache(peer_id, cmid, from_id, ts) VALUES(?,?,?,?)", (peer, cmid0, sender, int(time.time())))
                CONN.execute("DELETE FROM message_cache WHERE ts < ?", (int(time.time()) - 7*86400,))
                CONN.commit()

    if not first.startswith("мд "): return
    parts_norm = first[3:].strip().split()
    if not parts_norm:
        send_msg(peer, "Меня кто то звал?🧐 «Мд команды» список команд."); return
    parts_orig = first_line[3:].strip().split()
    found_cmd = None; found_idx = -1
    for i in range(len(parts_norm), 0, -1):
        candidate = "_".join(parts_norm[:i]).lower()
        if candidate in VALID_COMMANDS:
            found_cmd = candidate; found_idx = i; break
    if not found_cmd:
        found_cmd = parts_norm[0].lower(); found_idx = 1
    cmd = found_cmd.strip()
    args = parts_orig[found_idx:] if found_idx <= len(parts_orig) else []

    if cmd in ["обьява", "объяв", "обьяв"]: cmd = "объява"
    if cmd in ["обьявы"]: cmd = "объявы"
    if cmd in ["кд_обьяв"]: cmd = "кд_объяв"
    if cmd == "предлист": cmd = "преды"
    if cmd == "кмб": cmd = "кнб"

    if cmd not in VALID_COMMANDS:
        send_msg(peer, "Меня кто то звал?🧐 «Мд команды» список команд."); return

    owner = is_owner(sender, peer)
    real_owner = is_real_owner(sender, peer)
    admin = is_admin(sender, peer)
    moderator = is_moderator(sender, peer)
    main_admin = is_main_admin(sender, peer)
    sender_role = get_user_role(peer, sender)
    reply_obj = msg_obj.get("reply_message", {}) or {}
    has_reply = bool(reply_obj and isinstance(reply_obj, dict) and reply_obj.get("from_id"))
    reply_msg_id = reply_obj.get("conversation_message_id", 0) if has_reply else 0
    reply_text = reply_obj.get("text", "") if has_reply else ""
    reply_from = reply_obj.get("from_id", 0) if has_reply else 0

    # ... (все остальные команды остаются без изменений до самого конца)
    # Из-за ограничения длины, я дам только ключевые изменения
    
    # В самом конце файла в timer_loop добавляем обработку аукционов:

# В timer_loop добавить после обработки reminders:
            # Обработка аукционов
            with DB_LOCK:
                pending_auctions = CONN.execute("SELECT * FROM auctions WHERE state='pending'").fetchall()
            for auct in pending_auctions:
                try:
                    dt = datetime.datetime.strptime(auct["datetime_str"], "%d.%m.%y %H:%M")
                    dt = dt.replace(tzinfo=MSK_TZ)
                    if now_msk >= dt:
                        start_auction(auct["id"])
                        lots = get_lots(auct["id"])
                        if lots:
                            set_lot_active(lots[0]["id"])
                            lot = lots[0]
                            txt = ("@all\n🏆 ЛОТ НА АУКЦИОН 🏆\n🟦 Black Russia • BLUE 🟦\n\n"
                                   "━━━━━━━━━━━━━━━━━━━━\n\n"
                                   "📦 Наименование лота:\n{}\n\n"
                                   "💰 Стартовая цена:\n➡️ 20.000.000 рублей\n\n"
                                   "👤 Продавец:\n➡️ {}\n\n"
                                   "━━━━━━━━━━━━━━━━━━━━\n\n"
                                   "🔥 Лот выставлен! Ждём ставок! 🔥\n\n"
                                   "━━━━━━━━━━━━━━━━━━━━").format(lot["name"], silent_mention_badge(auct["created_by"], auct["peer_id"]))
                            send_msg(auct["peer_id"], txt, attachments=lot.get("photo_att"))
                            set_setting(auct["peer_id"], "auction_bid_time_{}".format(lot["id"]), str(int(time.time())))
                except Exception as e:
                    print("auction start error:", e)

            # Проверка завершенных лотов
            with DB_LOCK:
                active_auctions = CONN.execute("SELECT * FROM auctions WHERE state='active'").fetchall()
            for auct in active_auctions:
                active_lot = get_active_lot_state(auct["id"])
                if active_lot:
                    bid_time = int(get_setting(auct["peer_id"], "auction_bid_time_{}".format(active_lot["id"]), "0") or "0")
                    if bid_time > 0 and (now - bid_time) > 300:
                        latest = get_latest_bid(active_lot["id"])
                        if latest:
                            set_lot_finished(active_lot["id"], latest["user_id"], latest["amount"], 1)
                            send_msg(auct["peer_id"], "Лот «{}» продан за {} {}. Поздравим победителя!".format(
                                active_lot["name"], format_price(latest["amount"]), silent_mention_badge(latest["user_id"], auct["peer_id"])))
                        else:
                            set_lot_finished(active_lot["id"], None, 0, 0)
                            send_msg(auct["peer_id"], "Лот «{}» не продан! Никто не поставил ставку.".format(active_lot["name"]))
                        # Следующий лот
                        lots = get_lots(auct["id"])
                        current_idx = next((i for i, l in enumerate(lots) if l["id"] == active_lot["id"]), -1)
                        if current_idx >= 0 and current_idx < len(lots) - 1:
                            next_lot = lots[current_idx + 1]
                            set_lot_active(next_lot["id"])
                            txt = ("@all\n🏆 ЛОТ НА АУКЦИОН 🏆\n🟦 Black Russia • BLUE 🟦\n\n"
                                   "━━━━━━━━━━━━━━━━━━━━\n\n"
                                   "📦 Наименование лота:\n{}\n\n"
                                   "💰 Стартовая цена:\n➡️ 20.000.000 рублей\n\n"
                                   "👤 Продавец:\n➡️ {}\n\n"
                                   "━━━━━━━━━━━━━━━━━━━━\n\n"
                                   "🔥 Лот выставлен! Ждём ставок! 🔥\n\n"
                                   "━━━━━━━━━━━━━━━━━━━━").format(next_lot["name"], silent_mention_badge(auct["created_by"], auct["peer_id"]))
                            send_msg(auct["peer_id"], txt, attachments=next_lot.get("photo_att"))
                            set_setting(auct["peer_id"], "auction_bid_time_{}".format(next_lot["id"]), str(int(time.time())))
                        else:
                            finish_auction(auct["id"])
                            sold_lots = [l for l in lots if l["sold"] == 1]
                            if sold_lots:
                                lines = ["😉Спасибо всем за участие в аукционе!\n\nПроданные лоты сегодня:"]
                                for i, l in enumerate(sold_lots, 1):
                                    lines.append("{}) {} - {}".format(i, l["name"], silent_mention_badge(l["winner_id"], auct["peer_id"])))
                                lines.append("\nℹ️Если желаете поставить свой лот на следующий аукцион напишите в личные сообщения аукционеру.")
                                send_msg(auct["peer_id"], "\n".join(lines))

if __name__ == "__main__":
    main()
