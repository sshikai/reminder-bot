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

def get_msk_now():
    return datetime.datetime.now(MSK_TZ)

DATA_DIR = "/app/data" if os.path.isdir("/app/data") else os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DATA_DIR, "bot.db")
PHOTO_DIR = os.path.join(DATA_DIR, "card_photos")
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
    "Ты проиграл генератору случайных чисел, каково это — быть неудачником на генетическом уровне? 🧬💀",
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
    "объява", "обьява", "объявы", "обьявы", "объяв", "обьяв", "кд_объяв", "кд_обьяв",
    "топ", "браки", "брак", "развод", "онлайн", "др", "кто", "кто_я", "инфа", "монетка",
    "+правила", "-правила", "правила", "+приветствие", "-приветствие", "приветствие",
    "значок", "удалить_значок", "значки", "кнб", "чистка", "айди", "запретить_игры", "разрешить_игры",
    "очистить_топ", "карта", "карта_редактировать", "карта_очистить", "карта_дизайн"
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
BUS_SINGLE = ("АЗС", "ТК", "СК", "Такопарк")
BUS_PAGES = 4
BUS_PER_PAGE = 6
CARD_FIELD_MAP = {"бизнесы": "businesses", "недвижимость": "realty", "имущество": "property_val",
                  "гараж": "garage", "телефон": "phone", "имя": "name"}

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
FRAME_BOX = (0.062, 0.165, 0.286, 0.610)

WHO_ADJ = [
    "тайный", "безумный", "сонный", "хитрый", "гордый", "дерзкий", "мудрый", "лютый", "ленивый", "грустный",
    "честный", "добрый", "грозный", "дикий", "верный", "робкий", "нежный", "бойкий", "строгий", "упрямый",
    "мирный", "жуткий", "милый", "чудной", "скромный", "хмурый", "бодрый", "хладнокровный", "растерянный", "уставший",
    "вдохновленный", "хвастливый", "мнительный", "отчаянный", "наивный", "суровый", "ласковый", "скрытный", "ревнивый", "азартный",
    "космический", "призрачный", "огненный", "ледяной", "грозовой", "звездный", "теневой", "лунный", "солнечный", "ветреный",
    "болотный", "подземный", "небесный", "морской", "туманный", "радиоактивный", "токсичный", "квантовый", "магический", "мистический",
    "цифровой", "виртуальный", "неоновый", "пиксельный", "кибернетический", "древний", "вечный", "проклятый", "святой", "потусторонний",
    "железный", "золотой", "алмазный", "плюшевый", "деревянный", "каменный", "стеклянный", "бархатный", "шелковый", "ватный",
    "бумажный", "картонный", "пластиковый", "резиновый", "ржавый", "глянцевый", "матовый", "колючий", "пушистый", "гладкий",
    "липкий", "скользкий", "твердый", "мягкий", "хрупкий", "жидкий", "газообразный", "порошковый", "шершавый", "летучий",
    "гигантский", "крошечный", "круглый", "квадратный", "плоский", "кривой", "прямой", "бесконечный", "микроскопический", "массивный",
    "тонкий", "толстый", "узкий", "широкий", "вытянутый", "раздутый", "сжатый", "угловатый", "симметричный", "безразмерный",
    "кислый", "сладкий", "горький", "соленый", "острый", "пряный", "мятный", "шоколадный", "ванильный", "чесночный",
    "сырный", "карамельный", "лимонный", "имбирный", "медовый", "жареный", "вареный", "сырой", "копченый", "тушеный",
    "четкий", "хайповый", "кринжовый", "рофляный", "легендарный", "эпический", "дефолтный", "душный", "имбовый", "читерский",
    "забивной", "суетной", "пафосный", "блатной", "козырной", "фартовый", "люксовый", "бюджетный", "запрещенный", "заряженный",
    "базированный", "гигачадский", "мемный", "флексящий", "вайбовый", "чилловый", "попкорновый", "пельменный", "чебуречный",
    "красный", "синий", "зеленый", "желтый", "фиолетовый", "оранжевый", "розовый", "черный", "белый", "серый",
    "бордовый", "бирюзовый", "золотистый", "серебряный", "изумрудный", "яркий", "тусклый", "светящийся", "бледный", "разноцветный",
    "богатый", "бедный", "успешный", "потерянный", "сломанный", "починенный", "забытый", "популярный", "секретный", "опасный",
    "безопасный", "редкий", "обычный", "элитный", "финальный", "начальный", "главный", "запасной", "невидимый", "неуязвимый",
    "серверный", "региональный", "деловой", "бригадный", "гаражный", "трассовый", "премиальный", "дрифтовый"
]
WHO_NOUN = [
    "енот", "кот", "пес", "лис", "волк", "медведь", "лев", "тигр", "панда", "хомяк",
    "суслик", "выдра", "бобр", "заяц", "еж", "крот", "олень", "лось", "кабан", "слон",
    "жираф", "бегемот", "носорог", "обезьяна", "ленивец", "коала", "кенгуру", "утконос", "пингвин", "фламинго",
    "сова", "орел", "ворон", "попугай", "голубь", "лебедь", "акула", "дельфин", "кит", "краб",
    "кальмар", "осьминог", "креветка", "рак", "медуза", "ящерица", "змея", "хамелеон", "лягушка", "жаба",
    "дракон", "феникс", "единорог", "грифон", "пегас", "кентавр", "минотавр", "сфинкс", "гарпия", "сирена",
    "эльф", "гном", "орк", "гоблин", "тролль", "огр", "маг", "чародей", "шаман", "некромант",
    "ведьма", "колдун", "алхимик", "рыцарь", "паладин", "самурай", "ниндзя", "викинг", "пират", "призрак",
    "вампир", "оборотень", "зомби", "мумия", "демон", "ангел", "титан", "голем", "джинн", "леший",
    "шпион", "детектив", "хакер", "программист", "геймер", "стример", "блогер", "админ", "модератор", "босс",
    "директор", "шеф", "повар", "официант", "доктор", "хирург", "ученый", "профессор", "космонавт", "пилот",
    "капитан", "штурман", "водитель", "гонщик", "каскадер", "строитель", "инженер", "архитектор", "художник", "музыкант",
    "актер", "режиссер", "писатель", "поэт", "фотограф", "дизайнер", "модель", "стилист", "учитель", "тренер",
    "синяк", "крекер", "торетто", "стрипуха",
    "робот", "киборг", "андроид", "дрон", "процессор", "чип", "сервер", "ноут", "комп", "телефон",
    "плеер", "калькулятор", "лазер", "бластер", "ракета", "спутник", "телескоп", "микроскоп", "радар", "компас",
    "фонарик", "проектор", "экран", "монитор", "джойстик", "геймпад", "кабель", "провод", "переходник", "флешка",
    "пельмень", "чебурек", "хинкали", "блин", "вареник", "пирожок", "пончик", "круассан", "кекс", "торт",
    "пицца", "бургер", "хотдог", "суши", "ролл", "картофан", "огурец", "помидор", "баклажан", "кабачок",
    "арбуз", "дыня", "ананас", "банан", "яблоко", "груша", "лимон", "апельсин", "орех", "гриб",
    "суп", "борщ", "майонез", "кетчуп", "соус", "горчица", "сухарик", "чипс", "попкорн", "зефир",
    "кактус", "фикус", "баобаб", "дуб", "цветок", "роза", "лотос", "кристалл", "алмаз", "изумруд",
    "рубин", "янтарь", "метеорит", "астероид", "комета", "планета", "звезда", "галактика", "космос", "атом",
    "ларгус", "приора", "бустер", "мент", "бандит", "бизнесмен", "шахтер", "дрифтер", "регион", "бизнес"
]
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

# ===== КАРТОЧКА: ДАННЫЕ =====
def get_card(user_id):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM player_cards WHERE user_id=?", (user_id,)).fetchone()
    if row:
        d = dict(row)
        d.setdefault("design", "{}")
        return d
    return {"user_id": user_id, "name": "", "businesses": "[]", "realty": "[]", "property_val": "",
            "garage": "", "phone": "", "updated_at": 0, "design": "{}"}

def set_card_field(user_id, **kw):
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO player_cards(user_id) VALUES(?)", (user_id,))
        for k, v in kw.items():
            CONN.execute("UPDATE player_cards SET {}=? WHERE user_id=?".format(k), (v, user_id))
        CONN.execute("UPDATE player_cards SET updated_at=? WHERE user_id=?", (int(time.time()), user_id))
        CONN.commit()

def get_design(user_id):
    try: return json.loads(get_card(user_id).get("design") or "{}")
    except Exception: return {}

def set_design(user_id, **kw):
    design = get_design(user_id)
    design.update(kw)
    set_card_field(user_id, design=json.dumps(design, ensure_ascii=False))

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
        msg = "Время на редактирование вышло, {} вы бездействовали минуту⏳".format(mention(sender))
        if prompt_cmid:
            try:
                VK.messages.edit(peer_id=peer, conversation_message_id=prompt_cmid, message=msg, keyboard=json.dumps({"inline": True, "buttons": []}))
                return True
            except: pass
        send_msg(peer, msg)
        return True

    def reply(msg):
        if prompt_cmid:
            try:
                VK.messages.edit(peer_id=peer, conversation_message_id=prompt_cmid, message=msg, keyboard=json.dumps({"inline": True, "buttons": []}))
                return
            except: pass
        send_msg(peer, msg)

    if text.lower() in ["отмена", "отменить"]:
        clear_card_state(sender, peer)
        reply("❌ Редактирование отменено.")
        return True

    if step == "design_photo_wait":
        if text.strip().lower() in ["дефолт", "default"]:
            set_design(sender, photo="")
            set_card_state(sender, peer, "design_main", {"msg_cmid": prompt_cmid})
            reply("✅ Возвращена дефолтная фотография карточки.")
            return True
        url = extract_photo_url({"attachments": attachments}) if attachments else None
        if not url:
            reply("❌ Прикрепи фото к сообщению (или напиши «дефолт»).")
            return True
        if save_design_photo(sender, url):
            set_design(sender, photo="custom")
            set_card_state(sender, peer, "design_main", {"msg_cmid": prompt_cmid})
            reply("✅ Твоя фотография установлена на карточку!")
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
        set_card_state(sender, peer, "bus_menu", {"p": ctx.get("p", 1), "msg_cmid": prompt_cmid})
        reply("✅ Бизнес {} #{} успешно добавлен!".format(biz_type, text.strip()))
        return True

    if step == "realty_input":
        realty_type = ctx.get("t", "")
        if not re.match(r"^[1-9]\d{0,3}$", text.strip()):
            reply("❌ Неверный номер: максимум 4 цифры, без нуля в начале.")
            return True
        add_realty(sender, realty_type, text.strip())
        set_card_state(sender, peer, "realty_menu", {"msg_cmid": prompt_cmid})
        reply("✅ Недвижимость {} #{} успешно добавлена!".format(realty_type, text.strip()))
        return True

    if step == "garage_input":
        if not re.match(r"^[1-9]\d{0,3}$", text.strip()):
            reply("❌ Неверный номер гаража: максимум 4 цифры, без нуля в начале.")
            return True
        set_card_field(sender, garage=text.strip())
        set_card_state(sender, peer, "edit_menu", {"msg_cmid": prompt_cmid})
        reply("✅ Гараж #{} успешно добавлен!".format(text.strip()))
        return True

    if step == "phone_input":
        if not re.match(r"^[1-9]\d{3,6}$", text.strip()):
            reply("❌ Неверный телефон: 4–7 цифр, без нуля в начале.")
            return True
        set_card_field(sender, phone=text.strip())
        set_card_state(sender, peer, "edit_menu", {"msg_cmid": prompt_cmid})
        reply("✅ Телефон {} успешно добавлен!".format(format_phone(text.strip())))
        return True

    if step == "name_input":
        if not re.match(r"^[A-Za-z]{1,15}_[A-Za-z]{1,15}$", text.strip()):
            reply("❌ Неверный формат: Имя_Фамилия, только английские буквы, макс. 15+15 символов.")
            return True
        set_card_field(sender, name=text.strip())
        set_card_state(sender, peer, "edit_menu", {"msg_cmid": prompt_cmid})
        reply("✅ Имя {} успешно установлено!".format(text.strip()))
        return True

    if step == "property_input":
        if not re.match(r"^\d+$", text.strip()):
            reply("❌ Введите сумму цифрами (например 12000000000).")
            return True
        set_card_field(sender, property_val=text.strip())
        set_card_state(sender, peer, "edit_menu", {"msg_cmid": prompt_cmid})
        reply("✅ Имущество оценено в {}!".format(format_property(text.strip())))
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

# ===== ЗАГРУЗКА ФОТО В ВК + КЭШ =====
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
    key = "card_att_{}".format(user_id)
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
    send_msg(peer, "🗃️ Личная карточка: {}".format(silent_mention_badge(target_id, peer)), attachments=att)

# ===== ОТРИСОВКА КАРТОЧКИ =====
CARD_BOXES = {
    "name":   (0.035, 0.800, 0.340, 0.080),
    "biz":    (0.468, 0.215, 0.525, 0.085),
    "realty": (0.468, 0.378, 0.525, 0.085),
    "prop":   (0.468, 0.520, 0.525, 0.085),
    "garage": (0.468, 0.680, 0.525, 0.085),
    "phone":  (0.468, 0.825, 0.525, 0.085),
}

def card_template_path(color_key):
    base = "card_male" if (not color_key or color_key == "red") else "card_male_{}".format(color_key)
    for b in (base, "card_male"):
        for ext in (".jpg", ".png", ".jpeg"):
            p = os.path.join(DATA_DIR, b + ext)
            if os.path.isfile(p): return p
            if os.path.isfile(b + ext): return b + ext
    return None

def paste_custom_photo(img, user_id):
    path = os.path.join(PHOTO_DIR, "{}.jpg".format(user_id))
    if not os.path.isfile(path): return img
    try:
        ph = Image.open(path).convert("RGB")
        W, H = img.size
        rx, ry, rw, rh = FRAME_BOX
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
        img = paste_custom_photo(img, user_id)
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
    try: os.makedirs(PHOTO_DIR, exist_ok=True)
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
            phone TEXT DEFAULT '', design TEXT DEFAULT '{}', updated_at INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS card_edit_state (
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

def get_help_main_buttons():
    return {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "Общие", "payload": json.dumps({"cmd": "help_general"})}, "color": "primary"},
         {"action": {"type": "callback", "label": "Системы MD", "payload": json.dumps({"cmd": "help_systems"})}, "color": "negative"}],
        [{"action": {"type": "callback", "label": "BLACK RUSSIA", "payload": json.dumps({"cmd": "help_br"})}, "color": "positive"},
         {"action": {"type": "callback", "label": "Управление", "payload": json.dumps({"cmd": "help_manage"})}, "color": "negative"}],
        [{"action": {"type": "callback", "label": "Игровые", "payload": json.dumps({"cmd": "help_games"})}, "color": "positive"},
         {"action": {"type": "callback", "label": "MD", "payload": json.dumps({"cmd": "help_md"})}, "color": "negative"}]]}

def get_help_systems_buttons():
    return {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "Напоминалка", "payload": json.dumps({"cmd": "help_remind"})}, "color": "primary"},
         {"action": {"type": "callback", "label": "Опросы", "payload": json.dumps({"cmd": "help_polls"})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_back"})}, "color": "secondary"}]]}

def get_help_manage_buttons():
    return {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "Владелец", "payload": json.dumps({"cmd": "help_owner"})}, "color": "negative"},
         {"action": {"type": "callback", "label": "Главный Админ", "payload": json.dumps({"cmd": "help_main_admin"})}, "color": "negative"}],
        [{"action": {"type": "callback", "label": "Администратор", "payload": json.dumps({"cmd": "help_admin"})}, "color": "negative"},
         {"action": {"type": "callback", "label": "Модератор", "payload": json.dumps({"cmd": "help_moderator"})}, "color": "negative"}],
        [{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_back_main"})}, "color": "secondary"}]]}

def get_help_back_button():
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_back"})}, "color": "secondary"}]]}

def get_help_back_to_manage():
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_manage"})}, "color": "secondary"}]]}

def get_help_back_to_systems():
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_systems"})}, "color": "secondary"}]]}

HELP_GENERAL_TEXT = (
    "👥 Общие:\n\n"
    "Основные💻:\n"
    "1. Мд админы — список руководителей чата.\n"
    "2. Мд участник — твоя статистика.\n"
    "3. Мд ник — установить ник.\n"
    "4. Мд ники — список ников участников.\n"
    "5. Мд участники — список всех участников.\n"
    "6. Мд статусы — список статусов.\n"
    "7. Мд топ — топы чата.\n"
    "8. Мд онлайн — кто сейчас онлайн.\n"
    "9. Мд правила — правила чата.\n"
    "\n"
    "Информационные💼:\n"
    "1. Мд парк — информация об автопарке.\n"
    "2. Мд прем — информация о премиях.\n"
    "3. Мд чат — ссылка на чат для отчетов.\n"
    "\n"
    "Развлекательные🎭:\n"
    "1. Мд браки — список браков.\n"
    "2. Мд др — ближайшие дни рождения.\n"
    "3. Мд кто <слово> — кто является словом.\n"
    "4. Мд кто я — кто ты сегодня.\n"
    "5. Мд инфа <текст> — рандомные проценты.\n"
    "6. Мд монетка — орёл или решка.\n"
    "7. Мд значки — список значков.\n"
    "8. Мд значок — установить/посмотреть значок.\n"
    "9. Мд удалить значок — удалить значок."
)
HELP_ADMIN_TEXT = (
    "🛡 Команды Администратора:\n"
    "1. Мд ник [@юз] <имя> — установить ник другому.\n"
    "2. Мд номер чата — узнать ID чата.\n"
    "3. Мд проверка [@юз] — история наказаний.\n"
    "4. Мд тишина / тишина офф.\n"
    "5. Мд назначить @игрок <ранг> — ранг 1.\n"
    "6. Мд снять @игрок — снять роль.\n"
    "7. Мд чистка @игрок <число> — удалить сообщения (макс 50, КД 30 сек).\n"
    "8. Мд карта @игрок — посмотреть чужую карту.\n"
    "9. Мд карта очистить @игрок — очистить чужую карту.\n"
    "Имеет возможности прошлых ролей."
)
HELP_REMIND_TEXT = (
    "🔔 Напоминалка:\n"
    "1. Мд создать <название> <минуты> [кол-во]\n"
    "2. Мд список\n"
    "3. Мд удалить <название/номер>\n"
    "4. Мд редактировать <название/номер> <минуты>\n"
    "5. Мд отключить / включить\n"
    "6. Мд развернуть <название/номер>"
)
HELP_OWNER_TEXT = (
    "👑 Команды владельца:\n"
    "1. Мд адмчат <id> / удалить\n"
    "2. Мд лимит предов <число>\n"
    "3. Мд кд предов <дней>\n"
    "4. Мд текст др — текст поздравления.\n"
    "5. Мд назначить @игрок <1-4>\n"
    "6. Мд снять @игрок\n"
    "Имеет возможности прошлых ролей."
)
HELP_POLLS_TEXT = (
    "📢 Система опросов:\n"
    "🛡️Админские:\n"
    "1. Мд голоса / голоса вчера\n"
    "2. Мд защита / -защита [@юз]\n"
    "🤴Владельца:\n"
    "1. Мд старт/стоп контроль\n"
    "2. Мд время опросов <ЧЧ:ММ> <ЧЧ:ММ>\n"
    "3. Мд проверка опроса <ЧЧ:ММ>"
)
HELP_BR_TEXT = (
    "🎮 BLACK RUSSIA:\n\n"
    "ℹ️Информационные:\n"
    "1. Мд бр — список серверов и онлайн.\n\n"
    "🗃️Личная карточка:\n"
    "1. Мд карта — выводит фото карты.\n"
    "2. Мд карта редактировать — редактирование.\n"
    "3. Мд карта очистить [поле] — очистить карту.\n"
    "4. Мд карта дизайн — дизайн карты (цвет/фото).\n\n"
    "Желательно использовать в лс бота, чтобы не засорять чат😉"
)
HELP_MODERATOR_TEXT = (
    "👮‍️ Команды Модератора:\n"
    "1. Мд пред [@юз] причина — выдать пред.\n"
    "2. Мд снять пред [@юз] — снять пред.\n"
    "3. Мд бан [@юз] [дни/навсегда] — забанить.\n"
    "4. Мд разбан [@юз] — разбанить.\n"
    "5. Мд баны — список забаненных.\n"
    "6. Мд мут [@юз] <минуты> причина — выдать мут.\n"
    "7. Мд снять мут [@юз] — снять мут.\n"
    "8. Мд муты — список замученных.\n"
    "9. Мд преды — список предупреждений.\n"
    "10. Мд айди [@юз] — настоящий айди страницы.\n"
    "Наказания только для участников ниже рангом."
)
HELP_MAIN_ADMIN_TEXT = (
    "🥷 Команды Главного Админа:\n"
    "1. Мд статус @игрок <номер>\n"
    "2. Мд статус создать/удалить/редактировать/снять\n"
    "3. Мд +правила / -правила (ответом)\n"
    "4. Мд +приветствие / -приветствие (ответом)\n"
    "5. Мд запретить игры / разрешить игры\n"
    "6. Мд очистить топ [@игроки] [тип]\n"
    "Имеет возможности прошлых ролей."
)
HELP_GAMES_TEXT = (
    "🎯 Игровые команды:\n"
    "1. Мд кости @игрок — пригласить игрока бросить кости. 🎲\n"
    "Победитель выбирает наказание проигравшему:\n"
    "• 🔇 Мут на 30 минут\n"
    "• 📢 Упоминать каждые 60 мин, 5 часов\n"
    "• 🕊 Помиловать\n"
    "2. Мд кнб @игрок — камень, ножницы, бумага ✊✌️✋\n"
    "За проигрыш в КНБ наказания нет."
)
HELP_MD_TEXT = (
    "👊 Основной состав MD:\n"
    "1. Мд объява — объявление во все чаты.\n"
    "🛡️ Админские:\n"
    "1. Мд кд объяв <минуты>\n"
    "2. Мд объявы — вкл/выкл объявления."
)

MAIN_CARD_TEXT = "Какую информацию вы хотите отредактировать в личной карточке?"
DESIGN_MAIN_TEXT = "Что вы хотите поменять?"
DESIGN_PHOTO_TEXT = ("Если хотите установить свою фотографию — отправьте её в чат.\n"
                     "Если вернуть дефолтную — нажмите кнопку «Дефолт».")

def bus_menu_text(page=1):
    return ("Какой бизнес вы хотите добавить? (стр. {}/{})\n"
            "(Слоты: АЗС 1 | ТК/СК/Такопарк 1 | остальные 2. Один бизнес макс. 2 шт., Такопарк занимает 2 слота!)").format(page, BUS_PAGES)

def design_colors_text(page=1):
    return "Выберите цвет карточки (стр. {}/{}):".format(page, DESIGN_PAGES)

def card_edit_main_kb():
    P = lambda f: json.dumps({"cmd": "card_edit", "f": f, "field": f})
    return {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "Бизнесы", "payload": P("biz")}, "color": "primary"},
         {"action": {"type": "callback", "label": "Недвижимость", "payload": P("realty")}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Имущество", "payload": P("prop")}, "color": "primary"},
         {"action": {"type": "callback", "label": "Гараж", "payload": P("garage")}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Телефон", "payload": P("phone")}, "color": "primary"},
         {"action": {"type": "callback", "label": "Имя", "payload": P("name")}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"}]]}

def card_bus_kb(page=1):
    page = max(1, min(page, BUS_PAGES))
    types = BUS_TYPES_ORDER[(page - 1) * BUS_PER_PAGE: page * BUS_PER_PAGE]
    rows = []
    for i in range(0, len(types), 3):
        rows.append([{"action": {"type": "callback", "label": t, "payload": json.dumps({"cmd": "card_bus", "t": t, "type": t, "p": page})}, "color": "secondary"} for t in types[i:i+3]])
    nav = []
    if page > 1: nav.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "card_bus_menu", "p": page - 1})}, "color": "primary"})
    if page < BUS_PAGES: nav.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "card_bus_menu", "p": page + 1})}, "color": "primary"})
    nav.append({"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_edit_menu"})}, "color": "primary"})
    nav.append({"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"})
    rows.append(nav)
    return {"inline": True, "buttons": rows}

def card_realty_kb():
    return {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "Дом", "payload": json.dumps({"cmd": "card_realty", "t": "Дом", "type": "Дом"})}, "color": "secondary"},
         {"action": {"type": "callback", "label": "Квартира", "payload": json.dumps({"cmd": "card_realty", "t": "Квартира", "type": "Квартира"})}, "color": "secondary"}],
        [{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"},
         {"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_edit_menu"})}, "color": "primary"}]]}

def card_input_kb(back_cmd, back_page=None):
    back_payload = {"cmd": back_cmd}
    if back_page: back_payload["p"] = back_page
    return {"inline": True, "buttons": [[
        {"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"},
        {"action": {"type": "callback", "label": "Назад", "payload": json.dumps(back_payload)}, "color": "primary"}]]}

def design_main_kb():
    return {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "Цвет карточки", "payload": json.dumps({"cmd": "card_design_colors", "p": 1})}, "color": "primary"},
         {"action": {"type": "callback", "label": "Фото карточки", "payload": json.dumps({"cmd": "card_design_photo"})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"}]]}

def design_colors_kb(page=1):
    page = max(1, min(page, DESIGN_PAGES))
    chunk = COLORS_ORDER[(page - 1) * DESIGN_PER_PAGE: page * DESIGN_PER_PAGE]
    rows = []
    for i in range(0, len(chunk), 2):
        rows.append([{"action": {"type": "callback", "label": lab, "payload": json.dumps({"cmd": "card_design_color", "key": key, "p": page})}, "color": "secondary"} for key, lab in chunk[i:i+2]])
    nav = []
    if page > 1: nav.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "card_design_colors", "p": page - 1})}, "color": "primary"})
    if page < DESIGN_PAGES: nav.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "card_design_colors", "p": page + 1})}, "color": "primary"})
    nav.append({"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_design_main"})}, "color": "primary"})
    nav.append({"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"})
    rows.append(nav)
    return {"inline": True, "buttons": rows}

def design_photo_kb():
    return {"inline": True, "buttons": [[
        {"action": {"type": "callback", "label": "Дефолт", "payload": json.dumps({"cmd": "card_design_default"})}, "color": "primary"},
        {"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_design_main"})}, "color": "primary"},
        {"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"}]]}

def expire_stale_games(peer):
    now = int(time.time())
    with DB_LOCK:
        CONN.execute("UPDATE dice_games SET state='expired' WHERE peer_id=? AND state='pending' AND created_at<=?", (peer, now - 60))
        CONN.execute("UPDATE dice_games SET state='expired' WHERE peer_id=? AND state='playing' AND created_at<=?", (peer, now - 600))
        CONN.execute("UPDATE kmb_games SET state='expired' WHERE peer_id=? AND state IN ('pending','choosing') AND created_at<=?", (peer, now - 300))
        CONN.commit()

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
        cmid = obj.get("conversation_message_id")

        def snackbar(text):
            try:
                VK.messages.sendMessageEventAnswer(event_id=event_id, user_id=user_id, peer_id=peer_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": text}))
            except: pass

        def edit_msg(text, kb=None):
            kbj = json.dumps(kb) if kb else json.dumps({"inline": True, "buttons": []})
            if cmid:
                try:
                    VK.messages.edit(peer_id=peer_id, conversation_message_id=cmid, message=text, keyboard=kbj)
                    return True
                except Exception as e:
                    LAST_ERR["msg"] = str(e)
                    print("card edit error:", e)
            return send_msg(peer_id, text, keyboard=kb)

        def show(text, kb):
            ok = edit_msg(text, kb)
            if not ok: snackbar("❌ VK: {}".format(LAST_ERR["msg"][:70]))
            return ok

        def set_state(step, extra=None):
            c = dict(extra or {})
            c["msg_cmid"] = cmid
            set_card_state(user_id, peer_id, step, c)

        if cmd.startswith("card_"):
            state = get_card_state(user_id, peer_id)
            if not state:
                snackbar("⛔ Это не ваше меню или время вышло!")
                return
            if cmd == "card_cancel":
                clear_card_state(user_id, peer_id)
                show("❌ Редактирование карточки отменено.", None)
                snackbar("❌ Отменено")
                return
            ctx = state.get("context", {})
            if time.time() - ctx.get("ts", 0) > 60:
                clear_card_state(user_id, peer_id)
                show("Время на редактирование вышло, {} вы бездействовали минуту⏳".format(mention(user_id)), None)
                snackbar("⏳ Время вышло")
                return
            try:
                if cmd in ("card_main", "card_edit_menu", "card_back_main"):
                    set_state("edit_menu")
                    show(MAIN_CARD_TEXT, card_edit_main_kb()); snackbar("✅ Меню")
                elif cmd in ("card_edit", "card_field"):
                    f = payload.get("f") or payload.get("field") or ""
                    if f == "biz":
                        set_state("bus_menu", {"p": 1})
                        show(bus_menu_text(1), card_bus_kb(1))
                    elif f == "realty":
                        set_state("realty_menu")
                        show("Что вы хотите добавить? (макс. 2 недвижимости)", card_realty_kb())
                    elif f == "prop":
                        set_state("property_input")
                        show("Введите сумму, в которую оцениваете имущество (только цифры):", card_input_kb("card_edit_menu"))
                    elif f == "garage":
                        set_state("garage_input")
                        show("Введите номер гаража (макс. 4 цифры, без нуля в начале):", card_input_kb("card_edit_menu"))
                    elif f == "phone":
                        set_state("phone_input")
                        show("Введите номер телефона (4–7 цифр, без нуля в начале):", card_input_kb("card_edit_menu"))
                    elif f == "name":
                        set_state("name_input")
                        show("Введите имя формата Имя_Фамилия (англ. буквы, макс. 15+15):", card_input_kb("card_edit_menu"))
                    else:
                        snackbar("⚠️ debug payload: {}".format(str(payload)[:80])); return
                    snackbar("✅ Выполнено")
                elif cmd in ("card_bus_menu", "card_back_bus"):
                    p = int(payload.get("p", 1) or 1)
                    set_state("bus_menu", {"p": p})
                    show(bus_menu_text(p), card_bus_kb(p)); snackbar("✅ Бизнесы")
                elif cmd in ("card_bus", "card_biz_select"):
                    t = payload.get("t") or payload.get("type") or ""
                    p = int(payload.get("p", 1) or 1)
                    card = get_card(user_id)
                    blist = json.loads(card["businesses"] or "[]")
                    ok, mode = can_add_business(blist, t)
                    if not ok:
                        if mode == "exists": snackbar("ℹ️ «{}» уже есть в карточке".format(t))
                        elif mode == "max2": snackbar("⛔ Максимум 2 одинаковых бизнеса!")
                        else: snackbar("⛔ Нет слотов! Макс 4 бизнеса, Такопарк занимает 2 слота")
                        return
                    if t in BUS_NO_NUM:
                        add_business(user_id, t, None)
                        set_state("bus_menu", {"p": p})
                        show("✅ Бизнес «{}» добавлен!\n".format(t) + bus_menu_text(p), card_bus_kb(p))
                        snackbar("✅ Добавлено")
                    else:
                        set_state("biz_input", {"t": t, "p": p})
                        show("Введите номер для «{}» (макс. 3 цифры, без нуля в начале, напр. 33):".format(t), card_input_kb("card_bus_menu", p))
                        snackbar("✅ Введите номер")
                elif cmd in ("card_realty_menu", "card_back_realty"):
                    set_state("realty_menu")
                    show("Что вы хотите добавить? (макс. 2 недвижимости)", card_realty_kb()); snackbar("✅ Недвижимость")
                elif cmd in ("card_realty", "card_realty_select"):
                    t = payload.get("t") or payload.get("type") or ""
                    card = get_card(user_id)
                    rlist = json.loads(card["realty"] or "[]")
                    if len(rlist) >= 2:
                        snackbar("⛔ Максимум 2 недвижимости!"); return
                    set_state("realty_input", {"t": t})
                    show("Введите номер для «{}» (макс. 4 цифры, без нуля в начале):".format(t), card_input_kb("card_realty_menu"))
                    snackbar("✅ Введите номер")
                elif cmd == "card_garage":
                    set_state("garage_input")
                    show("Введите номер гаража (макс. 4 цифры, без нуля в начале):", card_input_kb("card_edit_menu"))
                    snackbar("✅ Введите номер")
                elif cmd == "card_phone":
                    set_state("phone_input")
                    show("Введите номер телефона (4–7 цифр, без нуля в начале):", card_input_kb("card_edit_menu"))
                    snackbar("✅ Введите номер")
                elif cmd == "card_name":
                    set_state("name_input")
                    show("Введите имя формата Имя_Фамилия (англ. буквы, макс. 15+15):", card_input_kb("card_edit_menu"))
                    snackbar("✅ Введите имя")
                elif cmd in ("card_prop", "card_property"):
                    set_state("property_input")
                    show("Введите сумму, в которую оцениваете имущество (только цифры):", card_input_kb("card_edit_menu"))
                    snackbar("✅ Введите сумму")
                elif cmd == "card_design_main":
                    set_state("design_main")
                    show(DESIGN_MAIN_TEXT, design_main_kb()); snackbar("✅ Дизайн")
                elif cmd == "card_design_colors":
                    p = int(payload.get("p", 1) or 1)
                    set_state("design_color", {"p": p})
                    show(design_colors_text(p), design_colors_kb(p)); snackbar("✅ Цвета")
                elif cmd == "card_design_color":
                    key = payload.get("key", "")
                    if key not in ALL_COLOR_KEYS:
                        snackbar("❌ Неизвестный цвет"); return
                    p = int(payload.get("p", 1) or 1)
                    set_design(user_id, color=key)
                    set_state("design_color", {"p": p})
                    show("✅ Цвет применён!\n" + design_colors_text(p), design_colors_kb(p))
                    snackbar("✅ Цвет применён")
                elif cmd == "card_design_photo":
                    set_state("design_photo_wait")
                    show(DESIGN_PHOTO_TEXT, design_photo_kb()); snackbar("✅ Жду фото")
                elif cmd == "card_design_default":
                    set_design(user_id, photo="")
                    set_state("design_main")
                    show("✅ Возвращена дефолтная фотография.\n" + DESIGN_MAIN_TEXT, design_main_kb())
                    snackbar("✅ Дефолт")
                else:
                    snackbar("❌ Неизвестная кнопка карточки")
            except Exception as e:
                print("card callback error:", e)
                try: snackbar("❌ Ошибка карточки: {}".format(str(e)[:60]))
                except: pass
            return

        if cmd in ["check_warns", "check_mutes", "check_back"]:
            target_id = int(payload.get("target", 0))
            if not target_id: snackbar("❌ Ошибка"); return
            target_name = silent_mention_badge(target_id, peer_id)
            month_ago = int(time.time()) - 30 * 86400
            if cmd == "check_back":
                kb = {"inline": True, "buttons": [[
                    {"action": {"type": "callback", "label": "⚠️ Предупреждения", "payload": json.dumps({"cmd": "check_warns", "target": target_id})}, "color": "negative"},
                    {"action": {"type": "callback", "label": "🔇 Муты", "payload": json.dumps({"cmd": "check_mutes", "target": target_id})}, "color": "primary"}]]}
                edit_msg("📜 История наказаний {} за месяц:".format(target_name), kb)
                snackbar("✅ Выполнено"); return
            if cmd == "check_warns":
                with DB_LOCK:
                    rows = CONN.execute("SELECT reason, message_text, issued_by, issued_at, duration_minutes FROM punishment_history WHERE peer_id=? AND user_id=? AND type='warn' AND issued_at>=? ORDER BY issued_at DESC", (peer_id, target_id, month_ago)).fetchall()
                lines = ["📜 История предупреждений {} за месяц:\n".format(target_name)]
                if not rows: lines.append("Предупреждений нет.")
                else:
                    for idx, r in enumerate(rows, 1):
                        dt = datetime.datetime.fromtimestamp(r["issued_at"], MSK_TZ).strftime("%d.%m %H:%M")
                        issuer = silent_mention_badge(r["issued_by"], peer_id) if r["issued_by"] else "Неизвестно"
                        reason = r["reason"] or "Не указана"
                        if r["message_text"]: reason += ' - "{}"'.format(r["message_text"][:100])
                        lines.append("{}. | {} | {} | Причина: {} | Выдал: {}|".format(idx, dt, fmt_warn_duration(r["duration_minutes"]), reason, issuer))
                edit_msg("\n".join(lines), {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "check_back", "target": target_id})}, "color": "secondary"}]]})
                snackbar("✅ Выполнено"); return
            if cmd == "check_mutes":
                with DB_LOCK:
                    rows = CONN.execute("SELECT reason, message_text, issued_by, issued_at, duration_minutes FROM punishment_history WHERE peer_id=? AND user_id=? AND type='mute' AND issued_at>=? ORDER BY issued_at DESC", (peer_id, target_id, month_ago)).fetchall()
                lines = ["📜 История мутов {} за месяц:\n".format(target_name)]
                if not rows: lines.append("Мутов нет.")
                else:
                    for idx, r in enumerate(rows, 1):
                        dt = datetime.datetime.fromtimestamp(r["issued_at"], MSK_TZ).strftime("%d.%m %H:%M")
                        issuer = silent_mention_badge(r["issued_by"], peer_id) if r["issued_by"] else "Неизвестно"
                        reason = r["reason"] or "Не указана"
                        if r["message_text"]: reason += ' - "{}"'.format(r["message_text"][:100])
                        lines.append("{}. | {} | {} | Причина: {} | Выдал: {}|".format(idx, dt, fmt_mute_duration(r["duration_minutes"]), reason, issuer))
                edit_msg("\n".join(lines), {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "check_back", "target": target_id})}, "color": "secondary"}]]})
                snackbar("✅ Выполнено"); return

        if cmd in ["dice_accept", "dice_decline", "dice_roll", "dice_punish_mute", "dice_punish_mention", "dice_punish_pardon"]:
            game_id = payload.get("game_id", 0)
            with DB_LOCK:
                game = CONN.execute("SELECT * FROM dice_games WHERE id=?", (game_id,)).fetchone()
            if not game: snackbar("❌ Игра не найдена"); return
            now = int(time.time())
            if game["state"] == "pending" and (now - game["created_at"]) > 60:
                with DB_LOCK:
                    CONN.execute("UPDATE dice_games SET state='expired' WHERE id=?", (game_id,)); CONN.commit()
                edit_game_message(peer_id, game_id, "⏰ Время вышло! {} не успел принять вызов от {} 🕐".format(
                    silent_mention_badge(game["opponent"], peer_id), silent_mention_badge(game["initiator"], peer_id)))
                snackbar("⏰ Время вышло"); return
            if cmd == "dice_accept":
                if user_id != game["opponent"]: snackbar("⛔ Это не твой вызов"); return
                if game["state"] != "pending": snackbar("⚠️ Игра уже неактивна"); return
                with DB_LOCK:
                    CONN.execute("UPDATE dice_games SET state='playing', current_turn=? WHERE id=?", (game["initiator"], game_id)); CONN.commit()
                edit_game_message(peer_id, game_id, "✅ {} принял вызов! Начинаем! 🎲\n{}, твоя очередь!".format(
                    silent_mention_badge(game["opponent"], peer_id), silent_mention_badge(game["initiator"], peer_id)),
                    {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "🎲 Бросить кость", "payload": json.dumps({"cmd": "dice_roll", "game_id": game_id})}, "color": "positive"}]]})
                snackbar("🎲 Игра началась!"); return
            elif cmd == "dice_decline":
                if user_id != game["opponent"]: snackbar("⛔ Не твой вызов"); return
                if game["state"] != "pending": snackbar("⚠️ Игра уже неактивна"); return
                with DB_LOCK:
                    CONN.execute("UPDATE dice_games SET state='declined' WHERE id=?", (game_id,)); CONN.commit()
                edit_game_message(peer_id, game_id, "😞 {} отказался от игры с {}. 💔".format(
                    silent_mention_badge(game["opponent"], peer_id), silent_mention_badge(game["initiator"], peer_id)))
                snackbar("❌ Отменено"); return
            elif cmd == "dice_roll":
                if game["state"] != "playing": snackbar("⚠️ Игра уже неактивна"); return
                if user_id != game["current_turn"]: snackbar("⛔ Не твоя очередь"); return
                roll = random.randint(1, 6)
                ini, opp = game["initiator"], game["opponent"]
                if user_id == ini: ni, no, nt = roll, game["opponent_roll"], opp
                else: ni, no, nt = game["initiator_roll"], roll, ini
                with DB_LOCK:
                    CONN.execute("UPDATE dice_games SET initiator_roll=?, opponent_roll=?, current_turn=? WHERE id=?", (ni, no, nt, game_id)); CONN.commit()
                if ni > 0 and no > 0:
                    if ni == no:
                        with DB_LOCK:
                            CONN.execute("UPDATE dice_games SET initiator_roll=0, opponent_roll=0, current_turn=? WHERE id=?", (ini, game_id)); CONN.commit()
                        edit_game_message(peer_id, game_id, "🤝 Ничья! Перекидываем! 🔄\n{}, бросай снова!".format(silent_mention_badge(ini, peer_id)),
                            {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "🎲 Бросить кость", "payload": json.dumps({"cmd": "dice_roll", "game_id": game_id})}, "color": "positive"}]]})
                    else:
                        winner = ini if ni > no else opp
                        loser = opp if ni > no else ini
                        with DB_LOCK:
                            CONN.execute("UPDATE dice_games SET state='finished' WHERE id=?", (game_id,)); CONN.commit()
                        increment_dice_win(peer_id, winner)
                        edit_game_message(peer_id, game_id, "🎉 {} побеждает! 🏆\n{}, выбирай наказание для {}:".format(
                            silent_mention_badge(winner, peer_id), silent_mention_badge(winner, peer_id), silent_mention_badge(loser, peer_id)),
                            {"inline": True, "buttons": [
                                [{"action": {"type": "callback", "label": "🔇 Мут 30 мин", "payload": json.dumps({"cmd": "dice_punish_mute", "game_id": game_id})}, "color": "negative"}],
                                [{"action": {"type": "callback", "label": "📢 Упоминать 60м/5ч", "payload": json.dumps({"cmd": "dice_punish_mention", "game_id": game_id})}, "color": "primary"}],
                                [{"action": {"type": "callback", "label": "🕊 Помиловать", "payload": json.dumps({"cmd": "dice_punish_pardon", "game_id": game_id})}, "color": "positive"}]]})
                else:
                    edit_game_message(peer_id, game_id, "🎲 {} выбросил {}!\n{}, твоя очередь!".format(
                        silent_mention_badge(user_id, peer_id), roll, silent_mention_badge(nt, peer_id)),
                        {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "🎲 Бросить кость", "payload": json.dumps({"cmd": "dice_roll", "game_id": game_id})}, "color": "positive"}]]})
                snackbar("🎲 Выпало: {}".format(roll)); return
            elif cmd == "dice_punish_mute":
                if game["state"] != "finished": snackbar("⚠️ Игра уже неактивна"); return
                ini, opp = game["initiator"], game["opponent"]
                winner = ini if game["initiator_roll"] > game["opponent_roll"] else opp
                loser = opp if game["initiator_roll"] > game["opponent_roll"] else ini
                if user_id != winner: snackbar("⛔ Только победитель"); return
                muted_now, _ = has_active_dice_punishments(peer_id, loser)
                if muted_now: snackbar("⚠️ Уже замучен!"); return
                mute_until = int(time.time()) + 30 * 60
                with DB_LOCK:
                    CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (loser, peer_id))
                    CONN.execute("UPDATE members SET mute_until=?, mute_reason=? WHERE user_id=? AND peer_id=?", (mute_until, "Проиграл в кости 🎲", loser, peer_id))
                    CONN.commit()
                add_punishment(peer_id, loser, "mute", "Проиграл в кости 🎲", 0, "", winner, 30)
                edit_game_message(peer_id, game_id, "🔇 {} выдал мут на 30 минут для {}! 🎲".format(
                    silent_mention_badge(winner, peer_id), silent_mention_badge(loser, peer_id)))
                snackbar("🔇 Мут выдан!"); return
            elif cmd == "dice_punish_mention":
                if game["state"] != "finished": snackbar("⚠️ Игра уже неактивна"); return
                ini, opp = game["initiator"], game["opponent"]
                winner = ini if game["initiator_roll"] > game["opponent_roll"] else opp
                loser = opp if game["initiator_roll"] > game["opponent_roll"] else ini
                if user_id != winner: snackbar("⛔ Только победитель"); return
                _, ment_now = has_active_dice_punishments(peer_id, loser)
                if ment_now: snackbar("⚠️ Уже упоминается!"); return
                now_ts = int(time.time())
                with DB_LOCK:
                    CONN.execute("DELETE FROM dice_mentions WHERE peer_id=? AND user_id=?", (peer_id, loser))
                    CONN.execute("INSERT INTO dice_mentions(peer_id, user_id, next_trigger, end_time, interval_minutes) VALUES(?,?,?,?,?)",
                        (peer_id, loser, now_ts + 3600, now_ts + 5*3600, 60))
                    CONN.commit()
                edit_game_message(peer_id, game_id, "📢 {} будет упоминать {} каждые 60 мин / 5 часов! 🎲".format(
                    silent_mention_badge(winner, peer_id), silent_mention_badge(loser, peer_id)))
                snackbar("📢 Упоминания запущены!"); return
            elif cmd == "dice_punish_pardon":
                if game["state"] != "finished": snackbar("⚠️ Игра уже неактивна"); return
                ini, opp = game["initiator"], game["opponent"]
                winner = ini if game["initiator_roll"] > game["opponent_roll"] else opp
                loser = opp if game["initiator_roll"] > game["opponent_roll"] else ini
                if user_id != winner: snackbar("⛔ Только победитель"); return
                edit_game_message(peer_id, game_id, "🕊 {} помиловал {}! 🎲❤️".format(
                    silent_mention_badge(winner, peer_id), silent_mention_badge(loser, peer_id)))
                snackbar("🕊 Помилован!"); return

        if cmd in ["kmb_accept", "kmb_decline", "kmb_choice"]:
            game_id = payload.get("game_id", 0)
            with DB_LOCK:
                game = CONN.execute("SELECT * FROM kmb_games WHERE id=?", (game_id,)).fetchone()
            if not game: snackbar("❌ Игра не найдена"); return
            chat_peer = game["peer_id"]
            now = int(time.time())
            if game["state"] == "pending" and (now - game["created_at"]) > 60:
                with DB_LOCK:
                    CONN.execute("UPDATE kmb_games SET state='expired' WHERE id=?", (game_id,)); CONN.commit()
                edit_game_message(chat_peer, game_id, "⏰ КНБ: время вышло!", table="kmb_games")
                snackbar("⏰ Время вышло"); return
            kmb_kb = {"inline": True, "buttons": [[
                {"action": {"type": "callback", "label": "👊 Камень", "payload": json.dumps({"cmd": "kmb_choice", "game_id": game_id, "choice": "rock"})}, "color": "primary"},
                {"action": {"type": "callback", "label": "✌️ Ножницы", "payload": json.dumps({"cmd": "kmb_choice", "game_id": game_id, "choice": "scissors"})}, "color": "primary"},
                {"action": {"type": "callback", "label": "✋ Бумага", "payload": json.dumps({"cmd": "kmb_choice", "game_id": game_id, "choice": "paper"})}, "color": "primary"}]]}
            if cmd == "kmb_accept":
                if user_id != game["opponent"]: snackbar("⛔ Не твой вызов"); return
                if game["state"] != "pending": snackbar("⚠️ Игра уже неактивна"); return
                with DB_LOCK:
                    CONN.execute("UPDATE kmb_games SET state='choosing', created_at=? WHERE id=?", (int(time.time()), game_id)); CONN.commit()
                edit_game_message(chat_peer, game_id, "✅ {} принял вызов КНБ! ✊✌️✋ Кнопки в ЛС!".format(silent_mention_badge(game["opponent"], chat_peer)), table="kmb_games")
                send_msg(game["initiator"], "🎮 КНБ: выбери ход!", keyboard=kmb_kb)
                send_msg(game["opponent"], "🎮 КНБ: выбери ход!", keyboard=kmb_kb)
                snackbar("✅ Проверь ЛС!"); return
            elif cmd == "kmb_decline":
                if user_id != game["opponent"]: snackbar("⛔ Не твой вызов"); return
                if game["state"] != "pending": snackbar("⚠️ Игра уже неактивна"); return
                with DB_LOCK:
                    CONN.execute("UPDATE kmb_games SET state='declined' WHERE id=?", (game_id,)); CONN.commit()
                edit_game_message(chat_peer, game_id, "😞 {} отказался от КНБ. 💔".format(silent_mention_badge(game["opponent"], chat_peer)), table="kmb_games")
                snackbar("❌ Отменено"); return
            elif cmd == "kmb_choice":
                if game["state"] != "choosing": snackbar("⚠️ Игра уже неактивна"); return
                if user_id not in [game["initiator"], game["opponent"]]: snackbar("⛔ Ты не участвуешь"); return
                choice = payload.get("choice", "")
                if not choice: snackbar("❌ Неверный выбор"); return
                with DB_LOCK:
                    if user_id == game["initiator"]:
                        if game["init_choice"]: snackbar("⚠️ Уже выбрал!"); return
                        CONN.execute("UPDATE kmb_games SET init_choice=? WHERE id=?", (choice, game_id))
                    else:
                        if game["opp_choice"]: snackbar("⚠️ Уже выбрал!"); return
                        CONN.execute("UPDATE kmb_games SET opp_choice=? WHERE id=?", (choice, game_id))
                    CONN.commit()
                    game = CONN.execute("SELECT * FROM kmb_games WHERE id=?", (game_id,)).fetchone()
                snackbar("✅ Выбор сохранён!")
                if game["init_choice"] and game["opp_choice"]:
                    ic, oc = game["init_choice"], game["opp_choice"]
                    beats = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
                    emojis = {"rock": "👊", "scissors": "✌️", "paper": "✋"}
                    if ic == oc:
                        with DB_LOCK:
                            CONN.execute("UPDATE kmb_games SET init_choice='', opp_choice='', created_at=? WHERE id=?", (int(time.time()), game_id)); CONN.commit()
                        send_msg(chat_peer, "🤝 Ничья! Оба выбрали {}\nПереигрываем! Проверьте ЛС.".format(emojis[ic]))
                        send_msg(game["initiator"], "🎮 КНБ: переигровка!", keyboard=kmb_kb)
                        send_msg(game["opponent"], "🎮 КНБ: переигровка!", keyboard=kmb_kb)
                    else:
                        winner = game["initiator"] if beats[ic] == oc else game["opponent"]
                        wc = ic if winner == game["initiator"] else oc
                        with DB_LOCK:
                            CONN.execute("UPDATE kmb_games SET state='finished' WHERE id=?", (game_id,)); CONN.commit()
                        increment_kmb_win(chat_peer, winner)
                        send_msg(chat_peer, "✊✌️✋ Результат КМБ:\n{} {}  vs {} {}\n\n🏆 {} {} побеждает!".format(
                            silent_mention_badge(game["initiator"], chat_peer), emojis[ic],
                            silent_mention_badge(game["opponent"], chat_peer), emojis[oc],
                            silent_mention_badge(winner, chat_peer), emojis[wc]))
                return

        if cmd in ["marriage_accept", "marriage_decline"]:
            proposer = payload.get("proposer", 0); target = payload.get("target", 0)
            if user_id != target: snackbar("⛔ Не тебе предложение!"); return
            with DB_LOCK:
                prop = CONN.execute("SELECT * FROM dice_games WHERE state='marriage' AND peer_id=? AND initiator=? AND opponent=? ORDER BY id DESC LIMIT 1", (peer_id, proposer, target)).fetchone()
            if not prop or (int(time.time()) - prop["created_at"]) > 60:
                snackbar("⏰ Время предложения истекло!"); return
            if cmd == "marriage_accept":
                if get_marriage(peer_id, proposer) or get_marriage(peer_id, target): snackbar("⚠️ Кто-то уже в браке!"); return
                with DB_LOCK:
                    try:
                        CONN.execute("INSERT INTO marriages(peer_id, user1, user2, created_at) VALUES(?,?,?,?)", (peer_id, proposer, target, int(time.time())))
                        CONN.execute("UPDATE dice_games SET state='married' WHERE id=?", (prop["id"],)); CONN.commit()
                    except: snackbar("❌ Ошибка"); return
                try:
                    users_info = VK.users.get(user_ids="{},{}".format(proposer, target), fields='sex')
                    sex_map = {u['id']: u.get('sex', 0) for u in users_info}
                    if sex_map.get(proposer) == 2 and sex_map.get(target) == 2:
                        send_msg(peer_id, "Мужики вы что геи что ли? А я не гей..")
                except: pass
                edit_game_message(peer_id, prop["id"], "💕️ Поздравляю, теперь {} и {} в счастливом браке!".format(
                    silent_mention_badge(proposer, peer_id), silent_mention_badge(target, peer_id)))
                snackbar("💍 Вы в браке!"); return
            else:
                with DB_LOCK:
                    CONN.execute("UPDATE dice_games SET state='declined' WHERE id=?", (prop["id"],)); CONN.commit()
                edit_game_message(peer_id, prop["id"], "💔 {} отказал(а) {}... Не судьба. 😢".format(
                    silent_mention_badge(target, peer_id), silent_mention_badge(proposer, peer_id)))
                snackbar("❌ Отказ"); return

        if cmd == "poll_vote":
            now_ts = int(time.time())
            today_str = get_msk_now().strftime("%Y-%m-%d")
            payload_time = payload.get("time", 0)
            if payload_time > 0 and (now_ts - payload_time) > 600: snackbar("⏰ Время вышло!"); return
            try:
                with DB_LOCK:
                    existing = CONN.execute("SELECT 1 FROM poll_votes WHERE user_id=? AND peer_id=? AND poll_time=?", (user_id, peer_id, payload_time)).fetchone()
                    if existing: snackbar("⚠️ Уже голосовал!")
                    else:
                        mem_row = CONN.execute("SELECT last_vote_time FROM members WHERE user_id=? AND peer_id=?", (user_id, peer_id)).fetchone()
                        last_vote = mem_row["last_vote_time"] if mem_row and mem_row["last_vote_time"] else 0
                        if (now_ts - last_vote) < 3600: snackbar("⏳ КД: {}м".format((3600-(now_ts-last_vote))//60))
                        else:
                            CONN.execute("INSERT INTO poll_votes(user_id, peer_id, poll_time, date) VALUES(?,?,?,?)", (user_id, peer_id, payload_time, today_str))
                            CONN.execute("UPDATE members SET last_vote_time=? WHERE user_id=? AND peer_id=?", (now_ts, user_id, peer_id))
                            CONN.commit()
                            send_msg(peer_id, "✅ {} Зайдет на этот кд!".format(silent_mention_badge(user_id, peer_id)))
                            snackbar("✅ Отметился!")
            except: snackbar("❌ Ошибка"); return

        if cmd == "page_info": snackbar("📄 Стр. {} из {}".format(payload.get("page",1), payload.get("total",1))); return

        if cmd in ["niki_prev", "niki_next"]:
            page = int(payload.get("page", 1))
            with DB_LOCK:
                rows = CONN.execute("SELECT user_id, nickname FROM members WHERE peer_id=? AND nickname!='' AND nickname IS NOT NULL ORDER BY user_id LIMIT 40 OFFSET ?", (peer_id, (page-1)*40)).fetchall()
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND nickname!='' AND nickname IS NOT NULL", (peer_id,)).fetchone()[0]
            per_page = 40; total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages))
            lines = ["📝 Ники (стр. {}/{}):\n".format(page, total_pages)]
            for idx, r in enumerate(rows, (page-1)*per_page+1):
                lines.append('{}. {} — "{}"'.format(idx, silent_mention_badge(r["user_id"], peer_id), r["nickname"]))
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "niki_prev", "page": page-1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "niki_next", "page": page+1})}, "color": "secondary"})
            edit_msg("\n".join(lines), {"inline": True, "buttons": [buttons]})
            snackbar("📄 Стр. {}".format(page)); return

        if cmd in ["participants_prev", "participants_next"]:
            page = int(payload.get("page", 1))
            with DB_LOCK:
                rows = CONN.execute("SELECT user_id, nickname FROM members WHERE peer_id=? ORDER BY user_id LIMIT 40 OFFSET ?", (peer_id, (page-1)*40)).fetchall()
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=?", (peer_id,)).fetchone()[0]
            per_page = 40; total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages))
            lines = ["👥 Участники (стр. {}/{}):\n".format(page, total_pages)]
            for idx, r in enumerate(rows, (page-1)*per_page+1):
                lines.append('{}. {} — "{}"'.format(idx, silent_mention_badge(r["user_id"], peer_id), r["nickname"] or "Не установлен"))
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "participants_prev", "page": page-1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "participants_next", "page": page+1})}, "color": "secondary"})
            edit_msg("\n".join(lines), {"inline": True, "buttons": [buttons]})
            snackbar("📄 Стр. {}".format(page)); return

        if cmd in ["predy_prev", "predy_next"]:
            page = int(payload.get("page", 1)); per_page = 20
            with DB_LOCK:
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND warnings>0", (peer_id,)).fetchone()[0]
                rows = CONN.execute("SELECT user_id, warnings, warn_durations FROM members WHERE peer_id=? AND warnings>0 ORDER BY warnings DESC LIMIT ? OFFSET ?", (peer_id, per_page, (page-1)*per_page)).fetchall()
            total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages))
            lines = ["⚠️ Предупреждения (стр. {}/{}):\n".format(page, total_pages)]
            for idx, r in enumerate(rows, (page-1)*per_page+1):
                lines.append("{}. {} — {} пред. ({} дн.)".format(idx, silent_mention_badge(r["user_id"], peer_id), r["warnings"], r["warn_durations"] or "0"))
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "predy_prev", "page": page-1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "predy_next", "page": page+1})}, "color": "secondary"})
            edit_msg("\n".join(lines), {"inline": True, "buttons": [buttons]})
            snackbar("📄 Стр. {}".format(page)); return

        if cmd in ["br_prev", "br_next"]:
            page = int(payload.get("page", 1))
            text, keyboard_json, _ = build_br_page(page)
            if text is None: snackbar("❌ Нет данных"); return
            edit_msg(text, json.loads(keyboard_json))
            snackbar("📄 Стр. {}".format(page)); return

        if cmd in ["status_prev", "status_next"]:
            page = int(payload.get("page", 1))
            text, keyboard_json, _ = build_status_page(peer_id, page)
            if text is None: snackbar("❌ Статусов нет"); return
            edit_msg(text, json.loads(keyboard_json))
            snackbar("📄 Стр. {}".format(page)); return

        if cmd in ["top_messages", "top_stickers", "top_dice", "top_marriages", "top_kmb", "top_days", "top_streaks"]:
            top_type = cmd.replace("top_", "")
            page = int(payload.get("page", 1)); per_page = 50
            total = 0; lines = []
            if top_type == "messages":
                with DB_LOCK:
                    total = CONN.execute("SELECT COUNT(*) FROM message_stats WHERE peer_id=? AND (msg_count>0 OR char_count>0)", (peer_id,)).fetchone()[0]
                    rows = CONN.execute("SELECT user_id, msg_count, char_count FROM message_stats WHERE peer_id=? AND (msg_count>0 OR char_count>0) ORDER BY char_count DESC LIMIT ? OFFSET ?", (peer_id, per_page, (page-1)*per_page)).fetchall()
                lines = ["🏆 Топ пользователей", "[💬 символы | ✉ сообщения]\n"]
                for idx, r in enumerate(rows, (page-1)*per_page+1):
                    lines.append("{}. {} — {} | {}".format(idx, silent_mention_badge(r["user_id"], peer_id), r["char_count"], r["msg_count"]))
            elif top_type == "stickers":
                with DB_LOCK:
                    total = CONN.execute("SELECT COUNT(*) FROM message_stats WHERE peer_id=? AND sticker_count>0", (peer_id,)).fetchone()[0]
                    rows = CONN.execute("SELECT user_id, sticker_count FROM message_stats WHERE peer_id=? AND sticker_count>0 ORDER BY sticker_count DESC LIMIT ? OFFSET ?", (peer_id, per_page, (page-1)*per_page)).fetchall()
                lines = ["🎨 Топ стикеров:\n"]
                for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append("{}. {} — {}".format(idx, silent_mention_badge(r["user_id"], peer_id), r["sticker_count"]))
            elif top_type == "dice":
                with DB_LOCK:
                    total = CONN.execute("SELECT COUNT(*) FROM message_stats WHERE peer_id=? AND dice_wins>0", (peer_id,)).fetchone()[0]
                    rows = CONN.execute("SELECT user_id, dice_wins FROM message_stats WHERE peer_id=? AND dice_wins>0 ORDER BY dice_wins DESC LIMIT ? OFFSET ?", (peer_id, per_page, (page-1)*per_page)).fetchall()
                lines = ["🎲 Топ кости:\n"]
                for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append("{}. {} — {}".format(idx, silent_mention_badge(r["user_id"], peer_id), r["dice_wins"]))
            elif top_type == "kmb":
                with DB_LOCK:
                    total = CONN.execute("SELECT COUNT(*) FROM message_stats WHERE peer_id=? AND kmb_wins>0", (peer_id,)).fetchone()[0]
                    rows = CONN.execute("SELECT user_id, kmb_wins FROM message_stats WHERE peer_id=? AND kmb_wins>0 ORDER BY kmb_wins DESC LIMIT ? OFFSET ?", (peer_id, per_page, (page-1)*per_page)).fetchall()
                lines = ["✊✌️✋ Топ КНБ:\n"]
                for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append("{}. {} — {}".format(idx, silent_mention_badge(r["user_id"], peer_id), r["kmb_wins"]))
            elif top_type == "marriages":
                with DB_LOCK:
                    rows_all = CONN.execute("SELECT user1, user2, created_at FROM marriages WHERE peer_id=? ORDER BY created_at ASC", (peer_id,)).fetchall()
                    active_rows = []
                    for r in rows_all:
                        m1 = CONN.execute("SELECT 1 FROM members WHERE user_id=? AND peer_id=?", (r["user1"], peer_id)).fetchone()
                        m2 = CONN.execute("SELECT 1 FROM members WHERE user_id=? AND peer_id=?", (r["user2"], peer_id)).fetchone()
                        if m1 or m2: active_rows.append(r)
                    total = len(active_rows)
                    start = (page-1)*per_page
                    rows_page = active_rows[start:start+per_page]
                lines = ["💒 Топ браков:\n"]
                now_ts = int(time.time())
                for idx, r in enumerate(rows_page, start+1):
                    lines.append("{}. {} и {} ({} дн.)".format(idx, silent_mention_badge(r["user1"], peer_id), silent_mention_badge(r["user2"], peer_id), (now_ts - r["created_at"]) // 86400))
            elif top_type == "days":
                with DB_LOCK:
                    total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND join_time>0", (peer_id,)).fetchone()[0]
                    rows = CONN.execute("SELECT user_id, join_time FROM members WHERE peer_id=? AND join_time>0 ORDER BY join_time ASC LIMIT ? OFFSET ?", (peer_id, per_page, (page-1)*per_page)).fetchall()
                lines = ["📅 Топ дней в чате (с последнего захода):\n"]
                for idx, r in enumerate(rows, (page-1)*per_page+1):
                    lines.append("{}. {} — {} дн.".format(idx, silent_mention_badge(r["user_id"], peer_id), days_since(r["join_time"])))
            elif top_type == "streaks":
                with DB_LOCK:
                    total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND streak>0", (peer_id,)).fetchone()[0]
                    rows = CONN.execute("SELECT user_id, streak FROM members WHERE peer_id=? AND streak>0 ORDER BY streak DESC LIMIT ? OFFSET ?", (peer_id, per_page, (page-1)*per_page)).fetchall()
                lines = ["🔥 Топ серий:\n"]
                for idx, r in enumerate(rows, (page-1)*per_page+1):
                    lines.append("{}. {} — {} дн. {}".format(idx, silent_mention_badge(r["user_id"], peer_id), r["streak"], get_streak_emoji(r["streak"])))
            total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages))
            nav = []
            if page > 1: nav.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": cmd, "page": page-1})}, "color": "secondary"})
            nav.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: nav.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": cmd, "page": page+1})}, "color": "secondary"})
            cats1 = [
                {"action": {"type": "callback", "label": "💬", "payload": json.dumps({"cmd": "top_messages", "page": 1})}, "color": "primary" if top_type=="messages" else "secondary"},
                {"action": {"type": "callback", "label": "🎨", "payload": json.dumps({"cmd": "top_stickers", "page": 1})}, "color": "primary" if top_type=="stickers" else "secondary"},
                {"action": {"type": "callback", "label": "🎲", "payload": json.dumps({"cmd": "top_dice", "page": 1})}, "color": "primary" if top_type=="dice" else "secondary"}]
            cats2 = [
                {"action": {"type": "callback", "label": "✊✌️✋", "payload": json.dumps({"cmd": "top_kmb", "page": 1})}, "color": "primary" if top_type=="kmb" else "secondary"},
                {"action": {"type": "callback", "label": "💒", "payload": json.dumps({"cmd": "top_marriages", "page": 1})}, "color": "primary" if top_type=="marriages" else "secondary"},
                {"action": {"type": "callback", "label": "📅", "payload": json.dumps({"cmd": "top_days", "page": 1})}, "color": "primary" if top_type=="days" else "secondary"}]
            cats3 = [{"action": {"type": "callback", "label": "🔥", "payload": json.dumps({"cmd": "top_streaks", "page": 1})}, "color": "primary" if top_type=="streaks" else "secondary"}]
            edit_msg("\n".join(lines), {"inline": True, "buttons": [cats1, cats2, cats3, nav]})
            snackbar("📄 Стр. {}".format(page)); return

        if cmd in ["help_general", "help_systems", "help_manage", "help_remind", "help_polls",
                   "help_admin", "help_moderator", "help_main_admin", "help_owner", "help_br", "help_games", "help_md", "help_back", "help_back_main"]:
            checks = {"help_systems": is_admin, "help_manage": is_moderator, "help_moderator": is_moderator,
                      "help_admin": is_admin, "help_main_admin": is_main_admin, "help_owner": is_owner,
                      "help_remind": is_admin, "help_polls": is_admin, "help_md": is_md_member}
            if cmd in checks:
                fn = checks[cmd]
                ok = fn(user_id) if cmd == "help_md" else fn(user_id, peer_id)
                if not ok: snackbar("У вас нет прав⛔️"); return
            if cmd in ["help_back", "help_back_main"]:
                message_text = "📖 Команды MD BOT"; kb_dict = get_help_main_buttons()
            elif cmd == "help_general": message_text = HELP_GENERAL_TEXT; kb_dict = get_help_back_button()
            elif cmd == "help_systems": message_text = "⚙️ Системы MD:\nВыберите раздел:"; kb_dict = get_help_systems_buttons()
            elif cmd == "help_manage": message_text = "🎛 Управление:\nВыберите роль:"; kb_dict = get_help_manage_buttons()
            elif cmd == "help_remind": message_text = HELP_REMIND_TEXT; kb_dict = get_help_back_to_systems()
            elif cmd == "help_polls": message_text = HELP_POLLS_TEXT; kb_dict = get_help_back_to_systems()
            elif cmd == "help_admin": message_text = HELP_ADMIN_TEXT; kb_dict = get_help_back_to_manage()
            elif cmd == "help_moderator": message_text = HELP_MODERATOR_TEXT; kb_dict = get_help_back_to_manage()
            elif cmd == "help_main_admin": message_text = HELP_MAIN_ADMIN_TEXT; kb_dict = get_help_back_to_manage()
            elif cmd == "help_owner": message_text = HELP_OWNER_TEXT; kb_dict = get_help_back_to_manage()
            elif cmd == "help_br": message_text = HELP_BR_TEXT; kb_dict = get_help_back_button()
            elif cmd == "help_games": message_text = HELP_GAMES_TEXT; kb_dict = get_help_back_button()
            elif cmd == "help_md": message_text = HELP_MD_TEXT; kb_dict = get_help_back_button()
            else: return
            edit_msg(message_text, kb_dict)
            snackbar("✅ Выполнено")
            return
    except Exception as e:
        print("event error:", e)

STATUS_PER_PAGE = 5
def build_status_page(peer, page):
    with DB_LOCK:
        statuses = CONN.execute("SELECT id, name FROM statuses WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
    if not statuses: return None, None, 1
    total = len(statuses)
    total_pages = max(1, (total + STATUS_PER_PAGE - 1) // STATUS_PER_PAGE)
    try: page = int(page)
    except: page = 1
    page = max(1, min(page, total_pages))
    chunk = statuses[(page-1)*STATUS_PER_PAGE: page*STATUS_PER_PAGE]
    lines = ["📋 Статусы (стр. {}/{}):\n".format(page, total_pages)]
    for idx, s in enumerate(chunk, (page-1)*STATUS_PER_PAGE+1):
        with DB_LOCK:
            users = CONN.execute("SELECT user_id FROM user_statuses WHERE status_id=? AND peer_id=?", (s["id"], peer)).fetchall()
        links = [silent_mention_badge(u["user_id"], peer) for u in users]
        lines.append("{} {}\n{}".format(idx, s["name"], "\n".join(links)) if links else "{} {}\n(пусто)".format(idx, s["name"]))
        lines.append("")
    buttons = []
    if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "status_prev", "page": page-1})}, "color": "secondary"})
    buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
    if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "status_next", "page": page+1})}, "color": "secondary"})
    return "\n".join(lines), json.dumps({"inline": True, "buttons": [buttons]}), total_pages

LEGENDARY_WHO = ["Пират🏴‍☠️", "Босс 👑", "Абсолют 🪐", "Легенда 🐐", "Олигарх 🎩", "Вампир 🧛", "Чародей 🧙", "Клоун 🤡", "Феникс🐦🔥", "Мафиози🕴️"]
LEGEND_SETKTO = {"пират": "Пират🏴‍️", "босс": "Босс 👑", "абсолют": "Абсолют 🪐", "легенда": "Легенда 🐐",
                 "олигарх": "Олигарх 🎩", "вампир": "Вампир 🧛", "чародей": "Чародей 🧙", "клоун": "Клоун 🤡",
                 "феникс": "Феникс🐦🔥", "мафиози": "Мафиози🕴️"}

def handle_ls_card(peer, sender, cmd, args):
    if cmd == "карта":
        targets = extract_targets(" ".join(args), 0)
        target_id = targets[0] if (targets and sender in (CREATOR_ID, LEADER_ID)) else sender
        send_card_to(peer, target_id)
    elif cmd == "карта_редактировать":
        set_card_state(sender, peer, "edit_menu", {"msg_cmid": None})
        send_msg(peer, MAIN_CARD_TEXT, keyboard=card_edit_main_kb())
    elif cmd == "карта_дизайн":
        set_card_state(sender, peer, "design_main", {"msg_cmid": None})
        send_msg(peer, DESIGN_MAIN_TEXT, keyboard=design_main_kb())
    elif cmd == "карта_очистить":
        fld = None
        for a in args:
            if a.lower() in CARD_FIELD_MAP: fld = CARD_FIELD_MAP[a.lower()]
        if fld:
            default = "[]" if fld in ("businesses", "realty") else ""
            set_card_field(sender, **{fld: default})
            send_msg(peer, "✅ Очищено поле карточки: {}.".format(fld))
        else:
            with DB_LOCK:
                CONN.execute("DELETE FROM player_cards WHERE user_id=?", (sender,)); CONN.commit()
            send_msg(peer, "✅ Ваша карточка очищена полностью.")

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
    send_msg(peer, "✅ Статус для id{} в чате {} установлен: **{}**".format(target_id, target_peer, final_status))

def handle_message(peer, sender, text, msg_obj):
    first_line = text.split("\n")[0].strip()
    first = norm(first_line)

    if peer < 2000000000:
        if sender in (CREATOR_ID, LEADER_ID) and peer == sender:
            low = text.strip().lower()
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
            elif text.strip().startswith("/"):
                handle_creator_ls(peer, text)
                return
        if first.startswith("мд "):
            pn = first[3:].strip().split()
            if pn:
                c2 = "_".join(pn[:2])
                if c2 == "карта_редактировать":
                    handle_ls_card(peer, sender, "карта_редактировать", pn[2:]); return
                if c2 == "карта_очистить":
                    handle_ls_card(peer, sender, "карта_очистить", pn[2:]); return
                if c2 == "карта_дизайн":
                    handle_ls_card(peer, sender, "карта_дизайн", pn[2:]); return
                if pn[0] == "карта":
                    handle_ls_card(peer, sender, "карта", pn[1:]); return
        if handle_card_input(sender, peer, text, cmid=msg_obj.get("conversation_message_id"), attachments=msg_obj.get("attachments")):
            return
        return

    if not first.startswith("мд "):
        if handle_card_input(sender, peer, text, cmid=msg_obj.get("conversation_message_id"), attachments=msg_obj.get("attachments")):
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

    if cmd == "команды":
        send_msg(peer, "📖 Команды MD BOT", keyboard=get_help_main_buttons())

    elif cmd == "админы":
        chat_owner_id = get_chat_owner(peer)
        with DB_LOCK:
            co_owners = [r["user_id"] for r in CONN.execute("SELECT user_id FROM roles WHERE peer_id=? AND role=4", (peer,)).fetchall()]
            main_admins = [r["user_id"] for r in CONN.execute("SELECT user_id FROM roles WHERE peer_id=? AND role=3", (peer,)).fetchall()]
            admins_list = [r["user_id"] for r in CONN.execute("SELECT user_id FROM roles WHERE peer_id=? AND role=2", (peer,)).fetchall()]
            moderators_list = [r["user_id"] for r in CONN.execute("SELECT user_id FROM roles WHERE peer_id=? AND role=1", (peer,)).fetchall()]
        owners_line = []
        if chat_owner_id: owners_line.append(silent_mention_badge(chat_owner_id, peer))
        for u in co_owners:
            if u != chat_owner_id: owners_line.append(silent_mention_badge(u, peer))
        lines = ["👑 Владелец: {}".format(", ".join(owners_line) if owners_line else "не определён"),
                 "🥷 Главные Админы(3): {}".format(", ".join(silent_mention_badge(u, peer) for u in main_admins) if main_admins else "отсутствуют"),
                 "🛡 Админы(2): {}".format(", ".join(silent_mention_badge(u, peer) for u in admins_list) if admins_list else "отсутствуют"),
                 "👮‍️ Модераторы(1): {}".format(", ".join(silent_mention_badge(u, peer) for u in moderators_list) if moderators_list else "отсутствуют")]
        send_msg(peer, "\n".join(lines))

    elif cmd == "участник":
        target_id = sender
        if args or has_reply:
            targets = extract_targets(" ".join(args), reply_from)
            if targets:
                target_id = targets[0]
                if target_id != sender and not is_moderator(sender, peer):
                    send_msg(peer, "⛔ Чужую статистику могут смотреть только модераторы и выше."); return
        with DB_LOCK:
            row = CONN.execute("SELECT nickname, warnings, warn_durations, warn_expiry, streak, join_time, who_name, who_ts FROM members WHERE user_id=? AND peer_id=?", (target_id, peer)).fetchone()
            js_row = CONN.execute("SELECT first_join FROM join_stats WHERE user_id=? AND peer_id=?", (target_id, peer)).fetchone()
            st_row = CONN.execute("SELECT s.name FROM user_statuses us JOIN statuses s ON us.status_id=s.id WHERE us.user_id=? AND us.peer_id=?", (target_id, peer)).fetchone()
        if not row and target_id not in (CREATOR_ID, LEADER_ID):
            send_msg(peer, "ℹ️ Участник {} еще не проявлял активность.".format(silent_mention_badge(target_id, peer))); return
        nick = row["nickname"] if row else "Не установлен"
        warns = row["warnings"] if row else 0
        durations_raw = row["warn_durations"] if row else "0"
        max_warns = int(get_setting(peer, "max_warns", "3") or "3")
        streak = row["streak"] if row else 0
        role_str = get_role_display(peer, target_id)
        marriage = get_marriage(peer, target_id)
        marriage_str = "💍 В браке с {}".format(silent_mention_badge(get_marriage_partner(marriage, target_id), peer)) if marriage else "💍 Не состоит в браке"
        join_ts = row["join_time"] if row and row["join_time"] else 0
        if not join_ts and js_row: join_ts = js_row["first_join"]
        first_ts = js_row["first_join"] if js_row else 0
        join_line = "📅 В чате: с {} ({} дн.)".format(fmt_join_date(join_ts), days_since(join_ts)) if join_ts else "📅 В чате: неизвестно"
        first_line_txt = "📅 Первый вход: {} ({} дн.)".format(fmt_join_date(first_ts), days_since(first_ts)) if first_ts else "📅 Первый вход: неизвестно"
        status_str = "🎯Статус: {}".format(st_row["name"]) if st_row else "🎯Статус: Отсутствует."
        who_name = row["who_name"] if row and row["who_name"] else ""
        who_ts = row["who_ts"] if row else 0
        if who_name:
            disp = "**{}**".format(who_name) if who_name in LEGENDARY_WHO else who_name
            who_line = "👤 Кто это: {}".format(disp) if int(time.time()) - who_ts <= 86400 else "🫆 Раньше был: {} ({})".format(disp, fmt_join_date(who_ts))
        else:
            who_line = "👤 Кто это: не определено"
        msg = ("👥 Участник {}:\n🎮 Ник: {}\n⚠️ Предупреждений: {}/{} ({} дн.)\n{}\n{}\n🙆‍️ Роль: {}\n{}\n{}\n🔥 Серия посещения: {} дн. {}\n{}").format(
            silent_mention_badge(target_id, peer), nick, warns, max_warns, durations_raw,
            join_line, first_line_txt, role_str, status_str, marriage_str, streak, get_streak_emoji(streak), who_line)
        send_msg(peer, msg)

    elif cmd == "ники":
        try:
            page = int(args[0]) if args and args[0].isdigit() else 1
            with DB_LOCK:
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND nickname!='' AND nickname IS NOT NULL", (peer,)).fetchone()[0]
                rows = CONN.execute("SELECT user_id, nickname FROM members WHERE peer_id=? AND nickname!='' AND nickname IS NOT NULL ORDER BY user_id LIMIT 40 OFFSET ?", (peer, (page-1)*40)).fetchall()
            if not rows: send_msg(peer, "📝 Никого с ником нет."); return
            per_page = 40; total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages))
            lines = ["📝 Ники (стр. {}/{}):\n".format(page, total_pages)]
            for idx, r in enumerate(rows, (page-1)*per_page+1):
                lines.append('{}. {} — "{}"'.format(idx, silent_mention_badge(r["user_id"], peer), r["nickname"]))
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "niki_prev", "page": page-1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "niki_next", "page": page+1})}, "color": "secondary"})
            VK.messages.send(peer_id=peer, message="\n".join(lines), keyboard=json.dumps({"inline": True, "buttons": [buttons]}), random_id=random.getrandbits(31))
        except Exception as e: send_msg(peer, "❌ Ошибка: {}".format(e))

    elif cmd == "участники":
        try:
            page = int(args[0]) if args and args[0].isdigit() else 1
            with DB_LOCK:
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=?", (peer,)).fetchone()[0]
                rows = CONN.execute("SELECT user_id, nickname FROM members WHERE peer_id=? ORDER BY user_id LIMIT 40 OFFSET ?", (peer, (page-1)*40)).fetchall()
            if not rows: send_msg(peer, "📝 Список пуст."); return
            per_page = 40; total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages))
            lines = ["👥 Участники (стр. {}/{}):\n".format(page, total_pages)]
            for idx, r in enumerate(rows, (page-1)*per_page+1):
                lines.append('{}. {} — "{}"'.format(idx, silent_mention_badge(r["user_id"], peer), r["nickname"] or "Не установлен"))
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "participants_prev", "page": page-1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "participants_next", "page": page+1})}, "color": "secondary"})
            VK.messages.send(peer_id=peer, message="\n".join(lines), keyboard=json.dumps({"inline": True, "buttons": [buttons]}), random_id=random.getrandbits(31))
        except Exception as e: send_msg(peer, "❌ Ошибка: {}".format(e))

    elif cmd == "ник":
        if not args: send_msg(peer, "❌ Формат: `Мд ник <ваш_ник>`"); return
        targets = extract_targets(" ".join(args), reply_from)
        if targets and admin:
            target_id = targets[0]
            nick_args = [a for a in args if not re.match(r"^\[id\d+\|", a) and not re.match(r"^@id\d+", a) and not re.match(r"^\d{5,}$", a)]
            if not nick_args: send_msg(peer, "❌ Укажите ник."); return
            new_nick = " ".join(nick_args)
            with DB_LOCK:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (target_id, peer))
                CONN.execute("UPDATE members SET nickname=? WHERE user_id=? AND peer_id=?", (new_nick, target_id, peer))
                CONN.commit()
            send_msg(peer, "✅ Ник {} установлен: **{}**".format(silent_mention_badge(target_id, peer), new_nick))
        else:
            new_nick = " ".join(args)
            with DB_LOCK:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (sender, peer))
                CONN.execute("UPDATE members SET nickname=? WHERE user_id=? AND peer_id=?", (new_nick, sender, peer))
                CONN.commit()
            send_msg(peer, "✅ Твой ник установлен: **{}**".format(new_nick))

    elif cmd == "проверка":
        if not admin: send_msg(peer, "⛔ Только администратор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд проверка @игрок`"); return
        target_id = targets[0]
        kb = {"inline": True, "buttons": [[
            {"action": {"type": "callback", "label": "⚠️ Предупреждения", "payload": json.dumps({"cmd": "check_warns", "target": target_id})}, "color": "negative"},
            {"action": {"type": "callback", "label": "🔇 Муты", "payload": json.dumps({"cmd": "check_mutes", "target": target_id})}, "color": "primary"}]]}
        send_msg(peer, "📜 История наказаний {} за месяц:".format(silent_mention_badge(target_id, peer)), keyboard=kb)

    elif cmd == "голоса":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        is_yesterday = args and args[0].lower() == "вчера"
        target_date = (get_msk_now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d") if is_yesterday else get_msk_now().strftime("%Y-%m-%d")
        day_name = "вчера" if is_yesterday else "сегодня"
        with DB_LOCK:
            rows = CONN.execute("SELECT user_id, COUNT(*) as count FROM poll_votes WHERE peer_id=? AND date=? GROUP BY user_id ORDER BY count DESC", (peer, target_date)).fetchall()
        if not rows: send_msg(peer, "🗳 {} никто не голосовал.".format(day_name)); return
        lines = ["🗳 Голоса за {} ({}):\n".format(day_name, target_date)]
        for r in rows: lines.append("• {} — {} раз(а)".format(silent_mention_badge(r['user_id'], peer), r['count']))
        send_msg(peer, "\n".join(lines))

    elif cmd in ["парк", "прем", "чат"]:
        key = {"парк": "park", "прем": "prem", "чат": "chat"}[cmd]
        reply = msg_obj.get("reply_message", {})
        if reply and isinstance(reply, dict) and reply.get("text"):
            if not admin: send_msg(peer, "⛔ Только администраторы."); return
            with DB_LOCK:
                CONN.execute("INSERT OR REPLACE INTO info_blocks(peer_id, key, text) VALUES(?,?,?)", (peer, key, reply["text"].strip())); CONN.commit()
            send_msg(peer, "✅ Информация '{}' обновлена.".format(cmd))
        else:
            with DB_LOCK:
                row = CONN.execute("SELECT text FROM info_blocks WHERE peer_id=? AND key=?", (peer, key)).fetchone()
            if row and row["text"]: send_msg(peer, "📌 Информация ({}):\n{}".format(cmd.capitalize(), row['text']))
            else: send_msg(peer, "ℹ️ Информация '{}' не установлена.".format(cmd))

    elif cmd == "пред":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        duration_days = int(get_setting(peer, "default_warn_days", "7") or "7")
        reason_parts = []
        for arg in args:
            if arg.isdigit() and not re.match(r"^\d{5,}$", arg): duration_days = int(arg)
            elif arg.lower() == "навсегда": duration_days = 9999
            elif not re.match(r"^\[id\d+\|", arg) and not re.match(r"^@id\d+", arg) and not re.match(r"^\d{5,}$", arg): reason_parts.append(arg)
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд пред @игрок причина`"); return
        reason = " ".join(reason_parts).strip()
        if not reason and not has_reply: send_msg(peer, "❌ Укажите причину."); return
        if not reason: reason = "Ответом на сообщение"
        max_warns = int(get_setting(peer, "max_warns", "3") or "3")
        now = time.time()
        expiry = now + (duration_days * 86400) if duration_days < 9999 else now + (36500 * 86400)
        for t_id in targets:
            if not can_punish(sender, t_id, peer): send_msg(peer, "⛔ Нельзя наказывать {}.".format(silent_mention_badge(t_id, peer))); continue
            days_str = "∞" if duration_days >= 9999 else str(duration_days)
            with DB_LOCK:
                row = CONN.execute("SELECT warnings, warn_durations, warn_reasons FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                if row:
                    cw = (row["warnings"] or 0) + 1
                    od = row["warn_durations"] or ""; orr = row["warn_reasons"] or ""
                    nd = "{}|{}".format(od, days_str) if od else days_str
                    nr = "{}|{}".format(orr, reason) if orr else reason
                    CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=?, warn_reasons=? WHERE user_id=? AND peer_id=?", (cw, nd, expiry, nr, t_id, peer))
                else:
                    cw = 1; nd = days_str; nr = reason
                    CONN.execute("INSERT INTO members(user_id, peer_id, warnings, warn_durations, warn_expiry, warn_reasons) VALUES(?,?,?,?,?,?)", (t_id, peer, cw, nd, expiry, nr))
                CONN.commit()
            add_punishment(peer, t_id, "warn", reason, reply_msg_id, reply_text, sender, duration_days * 1440)
            send_msg(peer, "⚠️ {} получает пред ({}/{}) ({} дн.). Причина: {}".format(silent_mention_badge(t_id, peer), cw, max_warns, nd, reason))
            if cw >= max_warns:
                try:
                    VK.messages.removeChatUser(chat_id=peer-2000000000, member_id=t_id)
                    add_punishment(peer, t_id, "ban", "Автокик за {} предов".format(max_warns), 0, "", sender, 0)
                    with DB_LOCK:
                        CONN.execute("UPDATE members SET warnings=0, warn_durations='', warn_expiry=0, warn_reasons='' WHERE user_id=? AND peer_id=?", (t_id, peer)); CONN.commit()
                except: pass

    elif cmd == "снять_пред":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд снять пред @игрок`"); return
        for t_id in targets:
            with DB_LOCK:
                row = CONN.execute("SELECT warnings, warn_durations, warn_reasons, warn_expiry FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                if row and row["warnings"] and row["warnings"] > 0:
                    nw = row["warnings"] - 1
                    parts_d = (row["warn_durations"] or "").split("|")
                    if parts_d and parts_d[-1] != '': parts_d.pop()
                    parts_r = (row["warn_reasons"] or "").split("|")
                    if parts_r and parts_r[-1] != '': parts_r.pop()
                    ne = 0 if nw == 0 else (row["warn_expiry"] or 0)
                    CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=?, warn_reasons=? WHERE user_id=? AND peer_id=?", (nw, "|".join(parts_d), ne, "|".join(parts_r), t_id, peer))
                    CONN.commit()
                    send_msg(peer, "✅ С {} снято предупреждение. Осталось: {}".format(silent_mention_badge(t_id, peer), nw))
                else:
                    send_msg(peer, "ℹ️ У {} нет предупреждений.".format(silent_mention_badge(t_id, peer)))

    elif cmd == "бан":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя."); return
        ban_days = 0; reason_parts = []
        for arg in args:
            if arg.isdigit() and not re.match(r"^\d{5,}$", arg) and ban_days == 0: ban_days = int(arg)
            elif arg.lower() == "навсегда": ban_days = -1
            elif not re.match(r"^\[id\d+\|", arg) and not re.match(r"^@id\d+", arg) and not re.match(r"^\d{5,}$", arg): reason_parts.append(arg)
        reason = " ".join(reason_parts).strip() or "Бан через команду"
        for t_id in targets:
            if not can_punish(sender, t_id, peer): send_msg(peer, "⛔ Нельзя забанить {}.".format(silent_mention_badge(t_id, peer))); continue
            ban_until = 0 if ban_days <= 0 else int(time.time()) + ban_days * 86400
            try:
                VK.messages.removeChatUser(chat_id=peer-2000000000, member_id=t_id)
                with DB_LOCK:
                    CONN.execute("INSERT OR REPLACE INTO bans(user_id, peer_id, banned_by, ban_until, reason, created_at) VALUES(?,?,?,?,?,?)", (t_id, peer, sender, ban_until, reason, int(time.time())))
                    CONN.execute("UPDATE members SET warnings=0, warn_durations='', warn_expiry=0 WHERE user_id=? AND peer_id=?", (t_id, peer))
                    CONN.commit()
                add_punishment(peer, t_id, "ban", reason, reply_msg_id, reply_text, sender, 0)
                send_msg(peer, "🚫 {} забанен {}.".format(silent_mention_badge(t_id, peer), "навсегда" if ban_days <= 0 else "на {} дн.".format(ban_days)))
            except Exception as e: send_msg(peer, "❌ Не удалось забанить: {}".format(e))

    elif cmd == "разбан":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя."); return
        for t_id in targets:
            with DB_LOCK:
                res = CONN.execute("DELETE FROM bans WHERE user_id=? AND peer_id=?", (t_id, peer)); CONN.commit()
            send_msg(peer, "✅ {} разбанен.".format(silent_mention_badge(t_id, peer)) if res.rowcount > 0 else "ℹ️ {} не забанен.".format(silent_mention_badge(t_id, peer)))

    elif cmd == "баны":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        now_ts = int(time.time())
        with DB_LOCK:
            rows = CONN.execute("SELECT user_id, ban_until, reason FROM bans WHERE peer_id=?", (peer,)).fetchall()
        active = [r for r in rows if r["ban_until"] == 0 or r["ban_until"] > now_ts]
        if not active: send_msg(peer, "✅ Забаненных нет."); return
        lines = ["🚫 Забаненные:\n"]
        for r in active:
            dur = "навсегда" if r["ban_until"] == 0 else "{} дн.".format(max(0, (r["ban_until"] - now_ts) // 86400))
            lines.append("• {} — {} | {}".format(silent_mention_badge(r["user_id"], peer), dur, r["reason"] or "Не указана"))
        send_msg(peer, "\n".join(lines))

    elif cmd == "мут":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        minutes = None; reason_parts = []
        for arg in args:
            if arg.isdigit() and not re.match(r"^\d{5,}$", arg):
                if minutes is None: minutes = int(arg)
            elif not re.match(r"^\[id\d+\|", arg) and not re.match(r"^@id\d+", arg) and not re.match(r"^\d{5,}$", arg): reason_parts.append(arg)
        if not targets: send_msg(peer, "❌ Укажите пользователя."); return
        if minutes is None or minutes <= 0: send_msg(peer, "❌ Укажите время мута."); return
        reason = " ".join(reason_parts).strip()
        if not reason and not has_reply: send_msg(peer, "❌ Укажите причину."); return
        if not reason: reason = "Ответом на сообщение"
        mute_until = int(time.time()) + minutes * 60
        for t in targets:
            if not can_punish(sender, t, peer): send_msg(peer, "⛔ Нельзя мутить {}.".format(silent_mention_badge(t, peer))); continue
            with DB_LOCK:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (t, peer))
                CONN.execute("UPDATE members SET mute_until=?, mute_reason=? WHERE user_id=? AND peer_id=?", (mute_until, reason, t, peer))
                CONN.commit()
            add_punishment(peer, t, "mute", reason, reply_msg_id, reply_text, sender, minutes)
            send_msg(peer, "🔇 {} получил мут на {} мин. Причина: {}".format(silent_mention_badge(t, peer), minutes, reason))

    elif cmd == "снять_мут":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд снять мут @игрок`"); return
        for t in targets:
            with DB_LOCK:
                CONN.execute("UPDATE members SET mute_until=0, mute_reason='' WHERE user_id=? AND peer_id=?", (t, peer)); CONN.commit()
            send_msg(peer, "🔊 Мут снят с {}.".format(silent_mention_badge(t, peer)))

    elif cmd == "муты":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        now_ts = int(time.time())
        with DB_LOCK:
            rows = CONN.execute("SELECT user_id, mute_until, mute_reason FROM members WHERE peer_id=? AND mute_until>?", (peer, now_ts)).fetchall()
        if not rows: send_msg(peer, "✅ Замученных нет."); return
        lines = ["🔇 Замученные:\n"]
        for r in rows:
            rem = r["mute_until"] - now_ts
            d, h, m, s = rem//86400, (rem%86400)//3600, (rem%3600)//60, rem%60
            tp = []
            if d > 0: tp.append("{} дн".format(d))
            if h > 0: tp.append("{} ч".format(h))
            if m > 0: tp.append("{} мин".format(m))
            tp.append("{} сек".format(s))
            lines.append("• {} — {} | {}".format(silent_mention_badge(r["user_id"], peer), " ".join(tp), r["mute_reason"] or "Не указана"))
        send_msg(peer, "\n".join(lines))

    elif cmd == "преды":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        page = int(args[0]) if args and args[0].isdigit() else 1
        per_page = 20
        with DB_LOCK:
            total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND warnings>0", (peer,)).fetchone()[0]
            rows = CONN.execute("SELECT user_id, warnings, warn_durations FROM members WHERE peer_id=? AND warnings>0 ORDER BY warnings DESC LIMIT ? OFFSET ?", (peer, per_page, (page-1)*per_page)).fetchall()
        if not rows: send_msg(peer, "✅ Предупреждений нет."); return
        total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages))
        lines = ["⚠️ Предупреждения (стр. {}/{}):\n".format(page, total_pages)]
        for idx, r in enumerate(rows, (page-1)*per_page+1):
            lines.append("{}. {} — {} пред. ({} дн.)".format(idx, silent_mention_badge(r["user_id"], peer), r["warnings"], r["warn_durations"] or "0"))
        buttons = []
        if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "predy_prev", "page": page-1})}, "color": "secondary"})
        buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
        if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "predy_next", "page": page+1})}, "color": "secondary"})
        VK.messages.send(peer_id=peer, message="\n".join(lines), keyboard=json.dumps({"inline": True, "buttons": [buttons]}), random_id=random.getrandbits(31))

    elif cmd == "статусы":
        text, kb, _ = build_status_page(peer, 1)
        if text is None: send_msg(peer, "ℹ️ Статусов нет."); return
        VK.messages.send(peer_id=peer, message=text, keyboard=kb, random_id=random.getrandbits(31))

    elif cmd == "статус":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        if not args: send_msg(peer, "❌ Формат: `Мд статус @игрок <номер>` / `создать` / `удалить` / `редактировать` / `снять`"); return
        subcmd = args[0].lower()
        if subcmd == "создать":
            name = " ".join(args[1:])
            if not name: send_msg(peer, "❌ Формат: `Мд статус создать <название>`"); return
            with DB_LOCK:
                try:
                    CONN.execute("INSERT INTO statuses(peer_id, name) VALUES(?,?)", (peer, name)); CONN.commit()
                    send_msg(peer, "✅ Статус «{}» создан.".format(name))
                except: send_msg(peer, "❌ Уже существует.")
        elif subcmd == "удалить":
            if len(args) < 2 or not args[1].isdigit(): send_msg(peer, "❌ Формат: `Мд статус удалить <номер>`"); return
            sn = int(args[1])
            with DB_LOCK:
                rows = CONN.execute("SELECT id FROM statuses WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if sn < 1 or sn > len(rows): send_msg(peer, "❌ Не найден."); return
                sid = rows[sn-1]["id"]
                CONN.execute("DELETE FROM statuses WHERE id=?", (sid,))
                CONN.execute("DELETE FROM user_statuses WHERE status_id=?", (sid,))
                CONN.commit()
            send_msg(peer, "✅ Статус удалён.")
        elif subcmd == "редактировать":
            if len(args) < 3 or not args[1].isdigit(): send_msg(peer, "❌ Формат: `Мд статус редактировать <номер> <название>`"); return
            sn = int(args[1]); nn = " ".join(args[2:])
            with DB_LOCK:
                rows = CONN.execute("SELECT id FROM statuses WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if sn < 1 or sn > len(rows): send_msg(peer, "❌ Не найден."); return
                CONN.execute("UPDATE statuses SET name=? WHERE id=?", (nn, rows[sn-1]["id"])); CONN.commit()
            send_msg(peer, "✅ Переименован в «{}».".format(nn))
        elif subcmd == "снять":
            targets = extract_targets(" ".join(args[1:]), reply_from)
            if not targets: send_msg(peer, "❌ Укажите пользователя."); return
            for t in targets:
                with DB_LOCK:
                    CONN.execute("DELETE FROM user_statuses WHERE user_id=? AND peer_id=?", (t, peer)); CONN.commit()
            send_msg(peer, "✅ Статус снят.")
        else:
            try: sn = int(args[-1])
            except: send_msg(peer, "❌ Формат: `Мд статус @игрок <номер>`"); return
            targets = extract_targets(" ".join(args[:-1]), reply_from)
            if not targets: send_msg(peer, "❌ Укажите пользователя."); return
            with DB_LOCK:
                rows = CONN.execute("SELECT id, name FROM statuses WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if sn < 1 or sn > len(rows): send_msg(peer, "❌ Не найден."); return
                sid, sname = rows[sn-1]["id"], rows[sn-1]["name"]
            for t in targets:
                with DB_LOCK:
                    CONN.execute("INSERT OR REPLACE INTO user_statuses(user_id, peer_id, status_id) VALUES(?,?,?)", (t, peer, sid)); CONN.commit()
            send_msg(peer, "✅ Назначены на статус «{}».".format(sname))

    elif cmd == "кости":
        if get_setting(peer, "games_disabled", "0") == "1": send_msg(peer, "⛔ Игры в этом чате запрещены."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд кости @игрок`"); return
        opponent = targets[0]
        if opponent == sender: send_msg(peer, "❌ Нельзя играть с самим собой!"); return
        if opponent == CREATOR_ID or opponent == LEADER_ID or opponent == get_chat_owner(peer): send_msg(peer, "❌ Нельзя вызвать владельца."); return
        if dice_blocked(peer, sender): send_msg(peer, "❌ Ты не можешь играть: оба наказания активны!"); return
        if dice_blocked(peer, opponent): send_msg(peer, "❌ {} не может играть!".format(silent_mention_badge(opponent, peer))); return
        expire_stale_games(peer)
        with DB_LOCK:
            active = CONN.execute("SELECT id FROM dice_games WHERE peer_id=? AND state IN ('pending','playing')", (peer,)).fetchone()
            active_kmb = CONN.execute("SELECT id FROM kmb_games WHERE peer_id=? AND state IN ('pending','choosing')", (peer,)).fetchone()
        if active or active_kmb: send_msg(peer, "❌ Уже идёт игра!"); return
        now = int(time.time())
        with DB_LOCK:
            cursor = CONN.execute("INSERT INTO dice_games(peer_id, initiator, opponent, state, created_at) VALUES(?,?,?,?,?)", (peer, sender, opponent, "pending", now))
            game_id = cursor.lastrowid; CONN.commit()
        kb = json.dumps({"inline": True, "buttons": [[
            {"action": {"type": "callback", "label": "✅ Принять", "payload": json.dumps({"cmd": "dice_accept", "game_id": game_id})}, "color": "positive"},
            {"action": {"type": "callback", "label": "❌ Отказаться", "payload": json.dumps({"cmd": "dice_decline", "game_id": game_id})}, "color": "negative"}]]})
        try:
            msg_id = VK.messages.send(peer_id=peer, message="🎲 {}, {} вызывает вас в кости! ⏰ 1 минута".format(
                silent_mention_badge(opponent, peer), silent_mention_badge(sender, peer)), keyboard=kb, random_id=random.getrandbits(31))
            cmid = resolve_cmid(peer, msg_id)
            with DB_LOCK:
                CONN.execute("UPDATE dice_games SET message_id=? WHERE id=?", (cmid, game_id)); CONN.commit()
        except: pass

    elif cmd == "кнб":
        if get_setting(peer, "games_disabled", "0") == "1": send_msg(peer, "⛔ Игры в этом чате запрещены."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд кнб @игрок`"); return
        opponent = targets[0]
        if opponent == sender: send_msg(peer, "❌ Нельзя играть с самим собой!"); return
        expire_stale_games(peer)
        with DB_LOCK:
            active = CONN.execute("SELECT id FROM dice_games WHERE peer_id=? AND state IN ('pending','playing')", (peer,)).fetchone()
            active_kmb = CONN.execute("SELECT id FROM kmb_games WHERE peer_id=? AND state IN ('pending','choosing')", (peer,)).fetchone()
        if active or active_kmb: send_msg(peer, "❌ Уже идёт игра!"); return
        now = int(time.time())
        with DB_LOCK:
            cursor = CONN.execute("INSERT INTO kmb_games(peer_id, initiator, opponent, state, created_at) VALUES(?,?,?,?,?)", (peer, sender, opponent, "pending", now))
            game_id = cursor.lastrowid; CONN.commit()
        kb = json.dumps({"inline": True, "buttons": [[
            {"action": {"type": "callback", "label": "✅ Принять", "payload": json.dumps({"cmd": "kmb_accept", "game_id": game_id})}, "color": "positive"},
            {"action": {"type": "callback", "label": "❌ Отказаться", "payload": json.dumps({"cmd": "kmb_decline", "game_id": game_id})}, "color": "negative"}]]})
        try:
            msg_id = VK.messages.send(peer_id=peer, message="✊✌️✋ {}, {} вызывает вас на КНБ! ⏰ 1 минута".format(
                silent_mention_badge(opponent, peer), silent_mention_badge(sender, peer)), keyboard=kb, random_id=random.getrandbits(31))
            cmid = resolve_cmid(peer, msg_id)
            with DB_LOCK:
                CONN.execute("UPDATE kmb_games SET message_id=? WHERE id=?", (cmid, game_id)); CONN.commit()
        except: pass

    elif cmd == "айди":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд айди @игрок`"); return
        lines = ["🆔 Настоящие айди:"]
        for t in targets: lines.append("• {} — {}".format(silent_mention_badge(t, peer), t))
        send_msg(peer, "\n".join(lines))

    elif cmd == "запретить_игры":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        set_setting(peer, "games_disabled", "1"); send_msg(peer, "🚫 Игры в этом чате запрещены.")

    elif cmd == "разрешить_игры":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        set_setting(peer, "games_disabled", "0"); send_msg(peer, "✅ Игры в этом чате разрешены.")

    elif cmd == "очистить_топ":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        group_fields = {"сообщений": ["msg_count", "char_count"], "эмодзи": ["sticker_count"], "стики": ["sticker_count"],
                        "стикеров": ["sticker_count"], "кости": ["dice_wins"], "кнб": ["kmb_wins"]}
        group_names = {"сообщений": "символы/сообщения", "эмодзи": "эмодзи", "стики": "эмодзи", "стикеров": "эмодзи", "кости": "кости", "кнб": "кнб"}
        selected = []
        for arg in args:
            g = arg.lower()
            if g in group_fields and g not in selected: selected.append(g)
        if not selected: selected = ["сообщений", "эмодзи", "кости", "кнб"]
        top_types = []
        for g in selected:
            for f in group_fields[g]:
                if f not in top_types: top_types.append(f)
        targets = extract_targets(" ".join(args), 0)
        if reply_from and reply_from not in targets: targets.append(reply_from)
        set_setting(peer, "top_clean_pending", json.dumps({"asker": sender, "ts": int(time.time()), "targets": targets, "types": top_types}))
        names = ", ".join(group_names[g] for g in selected)
        if targets:
            send_msg(peer, "⚠️ Очистить топ(ы) [{}] для: {}?\n«Подтвердить» или «Отменить». ⏰ 1 минута.".format(names, ", ".join(silent_mention_badge(t, peer) for t in targets)))
        else:
            send_msg(peer, "⚠️ Очистить топ(ы) [{}] для всех?\n«Подтвердить» или «Отменить». ⏰ 1 минута.".format(names))

    elif cmd == "чистка":
        if not admin: send_msg(peer, "⛔ Только администратор и выше."); return
        if not real_owner:
            last_clean = int(get_setting(peer, "last_clean_{}".format(sender), "0") or "0")
            if time.time() - last_clean < 30:
                send_msg(peer, "⏳ КД на очистку: {} сек.".format(30 - int(time.time() - last_clean))); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд чистка @игрок <число>`"); return
        target_id = targets[0]
        count = None
        for a in args:
            if a.isdigit() and 1 <= len(a) <= 3: count = int(a)
        if count is None: send_msg(peer, "❌ Укажите число сообщений: `Мд чистка @игрок <число>` (максимум 50)."); return
        count = max(1, min(count, 50))
        cmids = []; history_ok = True
        try:
            history = VK.messages.getHistory(peer_id=peer, count=200)
            for m in history.get("items", []):
                if m.get("from_id") == target_id:
                    cm = m.get("conversation_message_id") or m.get("id")
                    if cm: cmids.append(cm)
                    if len(cmids) >= count: break
        except Exception as e:
            print("clean history error:", e); history_ok = False
        if not history_ok:
            with DB_LOCK:
                rows = CONN.execute("SELECT cmid FROM message_cache WHERE peer_id=? AND from_id=? AND cmid>0 ORDER BY id DESC LIMIT ?", (peer, target_id, count)).fetchall()
            cmids = [r["cmid"] for r in rows]
        if not cmids: send_msg(peer, "ℹ️ Не найдено сообщений {} для удаления.".format(silent_mention_badge(target_id, peer))); return
        success = 0; failed = 0
        for cm in cmids:
            ok = False
            try:
                VK.messages.delete(peer_id=peer, conversation_message_ids=[cm], delete_for_all=1); ok = True
            except Exception:
                try:
                    VK.messages.delete(peer_id=peer, message_ids=[cm], delete_for_all=1); ok = True
                except Exception:
                    failed += 1
            if ok: success += 1
        if not real_owner: set_setting(peer, "last_clean_{}".format(sender), str(int(time.time())))
        if success > 0:
            msg = "🧹 Удалено {} сообщений {}.".format(success, silent_mention_badge(target_id, peer))
            if failed: msg += "\n⚠️ Не удалось удалить {}: VK не даёт удалить сообщения старше 24 часов.".format(failed)
            send_msg(peer, msg)
        else:
            send_msg(peer, "❌ Не удалось удалить ни одного сообщения (VK [15]).")

    elif cmd in ["адмчат", "admg"]:
        if not owner: send_msg(peer, "⛔ Только владелец."); return
        if args and args[0].lower() == "удалить":
            with DB_LOCK:
                CONN.execute("DELETE FROM settings WHERE peer_id=? AND key='admin_report_chat'", (peer,)); CONN.commit()
            send_msg(peer, "✅ Привязка удалена."); return
        if not args or not args[0].isdigit():
            send_msg(peer, "📌 Текущий чат: `{}`".format(get_setting(peer, "admin_report_chat", "Не установлена"))); return
        set_setting(peer, "admin_report_chat", args[0])
        send_msg(peer, "✅ Репорты в чат {}.".format(args[0]))

    elif cmd == "номер_чата":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        chat_owner_id = get_chat_owner(peer)
        send_msg(peer, "📌 Номер чата: {}\nСоздатель: {}".format(peer, silent_mention_badge(chat_owner_id, peer) if chat_owner_id else "Не определён"))

    elif cmd == "лимит_предов":
        if not owner: send_msg(peer, "⛔ Только владелец."); return
        if not args or not args[0].isdigit(): send_msg(peer, "❌ Формат: `Мд лимит предов <число>`"); return
        set_setting(peer, "max_warns", args[0]); send_msg(peer, "✅ Макс. предов: {}".format(args[0]))

    elif cmd == "кд_предов":
        if not owner: send_msg(peer, "⛔ Только владелец."); return
        if not args or not args[0].isdigit(): send_msg(peer, "❌ Формат: `Мд кд предов <дней>`"); return
        set_setting(peer, "default_warn_days", args[0]); send_msg(peer, "✅ Срок преда: {} дн.".format(args[0]))

    elif cmd == "старт_контроль":
        if not owner: send_msg(peer, "⛔ Только владелец."); return
        set_setting(peer, "control_active", "1"); send_msg(peer, "✅ Контроль включен.")

    elif cmd == "стоп_контроль":
        if not owner: send_msg(peer, "⛔ Только владелец."); return
        set_setting(peer, "control_active", "0"); send_msg(peer, "❌ Контроль выключен.")

    elif cmd == "время_опросов":
        if not owner: send_msg(peer, "⛔ Только владелец."); return
        if len(args) >= 2:
            try:
                sh, sm = map(int, args[0].split(":")); eh, em = map(int, args[1].split(":"))
                if sm != em: send_msg(peer, "❌ Минуты должны совпадать."); return
                set_setting(peer, "poll_start", str(sh)); set_setting(peer, "poll_end", str(eh)); set_setting(peer, "poll_minute", str(sm))
                send_msg(peer, "✅ Опросы: {}:{} - {}:{}".format(sh, sm, eh, em))
            except: send_msg(peer, "❌ Формат: `Мд время опросов ЧЧ:ММ ЧЧ:ММ`")
        else: send_msg(peer, "❌ Формат: `Мд время опросов ЧЧ:ММ ЧЧ:ММ`")

    elif cmd == "защита":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets:
            with DB_LOCK:
                protected = [int(r["user_id"]) for r in CONN.execute("SELECT user_id FROM members WHERE peer_id=? AND poll_protected=1", (peer,)).fetchall()]
            send_msg(peer, ("🛡 Защищенные: " + ", ".join(silent_mention_badge(x, peer) for x in protected)) if protected else "🛡 Нет защищенных.")
            return
        for t_id in targets:
            with DB_LOCK:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (t_id, peer))
                CONN.execute("UPDATE members SET poll_protected=1 WHERE user_id=? AND peer_id=?", (t_id, peer)); CONN.commit()
            send_msg(peer, "🛡 {} защищён.".format(silent_mention_badge(t_id, peer)))

    elif cmd == "-защита":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя."); return
        for t_id in targets:
            with DB_LOCK:
                CONN.execute("UPDATE members SET poll_protected=0 WHERE user_id=? AND peer_id=?", (t_id, peer)); CONN.commit()
            send_msg(peer, "✅ {} убран из защиты.".format(silent_mention_badge(t_id, peer)))

    elif cmd == "текст_др":
        if not owner: send_msg(peer, "⛔ Только владелец."); return
        reply = msg_obj.get("reply_message", {})
        if not isinstance(reply, dict) or not reply.get("text"):
            current = get_setting(peer, "birthday_text", "")
            send_msg(peer, "📝 Текущий текст:\n{}".format(current) if current else "📝 Стандартный текст.")
            return
        set_setting(peer, "birthday_text", reply["text"].strip()); send_msg(peer, "✅ Текст сохранён.")

    elif cmd == "создать":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        reply = msg_obj.get("reply_message", {})
        if not isinstance(reply, dict) or (not reply.get("text") and not reply.get("attachments")): send_msg(peer, "❌ Ответьте на сообщение."); return
        if len(args) < 2: send_msg(peer, "❌ Формат: `Мд создать <название> <минуты> [кол-во]`"); return
        try:
            rc = 1
            if len(args) >= 3 and args[-1].isdigit(): rc = int(args[-1]); minutes = int(args[-2]); name = " ".join(args[:-2])
            else: minutes = int(args[-1]); name = " ".join(args[:-1])
        except: send_msg(peer, "❌ Числа должны быть числами."); return
        src = int(reply.get("conversation_message_id", 0) or 0)
        att = parse_reply_attachments(reply)
        with DB_LOCK:
            try:
                CONN.execute("INSERT INTO reminders(peer_id, name, text, attachments, source_message_id, interval_minutes, repeat_count, next_trigger) VALUES(?,?,?,?,?,?,?,?)",
                    (peer, name, reply.get("text", ""), att, src, minutes, rc, time.time() + minutes*60)); CONN.commit()
                send_msg(peer, "✅ Напоминание «{}» создано. {} мин.".format(name, minutes))
            except: send_msg(peer, "❌ Уже существует.")

    elif cmd == "список":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        with DB_LOCK:
            rows = CONN.execute("SELECT id, name, interval_minutes, repeat_count, next_trigger, enabled FROM reminders WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
        if not rows: send_msg(peer, "📭 Пусто."); return
        msg = "📋 Напоминания:\n"; now = time.time()
        for idx, r in enumerate(rows, 1):
            rem = max(0, r["next_trigger"] - now)
            msg += "#{} {} | {} мин | {}м {}с\n".format(idx, r['name'], r['interval_minutes'], int(rem//60), int(rem%60))
        send_msg(peer, msg)

    elif cmd == "удалить":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        if not args: send_msg(peer, "❌ Формат: `Мд удалить <номер/название>`"); return
        arg = " ".join(args)
        with DB_LOCK:
            if arg.isdigit():
                row = CONN.execute("SELECT name FROM reminders WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if 1 <= int(arg) <= len(row): arg = row[int(arg)-1]["name"]
            res = CONN.execute("DELETE FROM reminders WHERE peer_id=? AND name=?", (peer, arg)); CONN.commit()
        send_msg(peer, "✅ «{}» удалено.".format(arg) if res.rowcount > 0 else "❌ Не найдено.")

    elif cmd == "редактировать":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        if len(args) < 2: send_msg(peer, "❌ Формат: `Мд редактировать <название> <минуты>`"); return
        try: minutes = int(args[-1]); arg = " ".join(args[:-1])
        except: send_msg(peer, "❌ Минуты — число."); return
        with DB_LOCK:
            if arg.isdigit():
                row = CONN.execute("SELECT name FROM reminders WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if 1 <= int(arg) <= len(row): arg = row[int(arg)-1]["name"]
            res = CONN.execute("UPDATE reminders SET interval_minutes=?, next_trigger=? WHERE peer_id=? AND name=?", (minutes, time.time()+minutes*60, peer, arg)); CONN.commit()
        send_msg(peer, "✅ «{}» обновлено.".format(arg) if res.rowcount > 0 else "❌ Не найдено.")

    elif cmd == "включить":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        arg = " ".join(args) if args else None
        with DB_LOCK:
            if arg: CONN.execute("UPDATE reminders SET enabled=1, next_trigger=? WHERE peer_id=? AND name=?", (time.time()+60, peer, arg))
            else: CONN.execute("UPDATE reminders SET enabled=1 WHERE peer_id=?", (peer,))
            CONN.commit()
        send_msg(peer, "✅ Включено.")

    elif cmd == "отключить":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        arg = " ".join(args) if args else None
        with DB_LOCK:
            if arg: CONN.execute("UPDATE reminders SET enabled=0 WHERE peer_id=? AND name=?", (peer, arg))
            else: CONN.execute("UPDATE reminders SET enabled=0 WHERE peer_id=?", (peer,))
            CONN.commit()
        send_msg(peer, "✅ Отключено.")

    elif cmd == "развернуть":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        if not args: send_msg(peer, "❌ Формат: `Мд развернуть <название>`"); return
        arg = " ".join(args)
        with DB_LOCK:
            if arg.isdigit():
                row = CONN.execute("SELECT name FROM reminders WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if 1 <= int(arg) <= len(row): arg = row[int(arg)-1]["name"]
            row = CONN.execute("SELECT text FROM reminders WHERE peer_id=? AND name=?", (peer, arg)).fetchone()
        send_msg(peer, "📝 {}:\n{}".format(arg, row['text']) if row else "❌ Не найдено.")

    elif cmd == "назначить":
        if sender_role < 2: send_msg(peer, "⛔ Только админ и выше."); return
        if not args: send_msg(peer, "❌ Формат: `Мд назначить @игрок <ранг 1-4>`"); return
        try: target_role = int(args[-1])
        except: send_msg(peer, "❌ Укажите ранг."); return
        if target_role not in [1,2,3,4]: send_msg(peer, "❌ Ранг 1-4."); return
        if target_role == 4 and not real_owner: send_msg(peer, "⛔ Ранг 4 — только владелец."); return
        if sender_role == 2 and target_role > 1: send_msg(peer, "⛔ Админ → только ранг 1."); return
        if sender_role == 3 and target_role > 2: send_msg(peer, "⛔ Гл.Админ → ранг 1-2."); return
        targets = extract_targets(" ".join(args[:-1]), reply_from)
        if not targets: send_msg(peer, "❌ Укажите игрока."); return
        for t in targets:
            if t == CREATOR_ID or t == LEADER_ID or t == get_chat_owner(peer): send_msg(peer, "❌ Нельзя менять роль владельца/лидера."); continue
            old = get_user_role(peer, t)
            if old == 4 and not real_owner: send_msg(peer, "⛔ Нельзя менять совладельца."); continue
            set_user_role(peer, t, target_role)
            if old > target_role: send_msg(peer, "⬇️ {} понижен до {}.".format(silent_mention_badge(t, peer), ROLE_NAMES[target_role]))
            elif old < target_role: send_msg(peer, "⬆️ {} повышен до {}.".format(silent_mention_badge(t, peer), ROLE_NAMES[target_role]))
            else: send_msg(peer, "ℹ️ {} уже {}.".format(silent_mention_badge(t, peer), ROLE_NAMES[target_role]))

    elif cmd == "снять":
        if sender_role < 2: send_msg(peer, "⛔ Только админ и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите игрока."); return
        for t in targets:
            if t == CREATOR_ID or t == LEADER_ID or t == get_chat_owner(peer): send_msg(peer, "❌ Нельзя снять владельца/лидера."); continue
            old = get_user_role(peer, t)
            if old == 0: send_msg(peer, "ℹ️ {} уже участник.".format(silent_mention_badge(t, peer))); continue
            if old == 4 and not real_owner: send_msg(peer, "⛔ Только владелец."); continue
            if old >= sender_role and not real_owner: send_msg(peer, "⛔ Нельзя снять равного/выше."); continue
            set_user_role(peer, t, 0)
            send_msg(peer, "✅ {} теперь участник.".format(silent_mention_badge(t, peer)))

    elif cmd == "тишина":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        set_setting(peer, "silence_mode", "1"); send_msg(peer, "🔇 Тишина включена.")

    elif cmd == "тишина_офф":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        set_setting(peer, "silence_mode", "0"); send_msg(peer, "🔊 Тишина выключена.")

    elif cmd == "проверка_опроса":
        if not owner: send_msg(peer, "⛔ Только владелец."); return
        if len(args) >= 1:
            try:
                tp = args[0].split(":")
                ch = int(tp[0]); cm = int(tp[1]) if len(tp) > 1 else 0
                set_setting(peer, "check_hour", str(ch)); set_setting(peer, "check_minute", str(cm)); set_setting(peer, "last_23_check", "")
                send_msg(peer, "✅ Проверка: {:02d}:{:02d}".format(ch, cm))
            except: send_msg(peer, "❌ Формат: `Мд проверка опроса ЧЧ:ММ`")
        else:
            send_msg(peer, "📌 Проверка: {:02d}:{:02d}".format(int(get_setting(peer, "check_hour", "23")), int(get_setting(peer, "check_minute", "0"))))

    elif cmd == "бр":
        try:
            page = int(args[0]) if args and args[0].isdigit() else 1
            text, kb, _ = build_br_page(page)
            if text is None: send_msg(peer, "❌ Нет данных."); return
            VK.messages.send(peer_id=peer, message=text, keyboard=kb, random_id=random.getrandbits(31))
        except Exception as e: send_msg(peer, "❌ Ошибка: {}".format(e))

    elif cmd == "объява":
        if peer != MD_CHAT_PEER: send_msg(peer, "❌ Только в основной беседе MD."); return
        reply = msg_obj.get("reply_message", {})
        if not reply or not isinstance(reply, dict) or not reply.get("conversation_message_id"): send_msg(peer, "❌ Ответь на сообщение."); return
        cd = int(get_setting(MD_CHAT_PEER, "announce_cd", "60") or "60")
        last = int(get_setting(MD_CHAT_PEER, "last_announce_{}".format(sender), "0") or "0")
        now = time.time()
        if last > 0 and (now - last) < cd * 60:
            send_msg(peer, "⏳ КД: {} мин.".format(int((cd*60-(now-last))/60)+1)); return
        cmid = reply.get("conversation_message_id")
        chats = get_all_bot_chats(); sc = 0
        for cp in chats:
            if cp == MD_CHAT_PEER: continue
            if get_setting(cp, "announcements_enabled", "1") != "1": continue
            try:
                fj = json.dumps({"peer_id": MD_CHAT_PEER, "conversation_message_ids": [cmid]})
                VK.messages.send(peer_id=cp, message="📢 Объявление от семьи Million Dollars:", forward=fj, random_id=random.getrandbits(31))
                sc += 1; time.sleep(0.4)
            except: pass
        set_setting(MD_CHAT_PEER, "last_announce_{}".format(sender), str(int(time.time())))
        send_msg(peer, "✅ Объявление в {} чатов.".format(sc))

    elif cmd == "кд_объяв":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        if not args or not args[0].isdigit():
            send_msg(peer, "📌 КД: {} мин.".format(get_setting(MD_CHAT_PEER, "announce_cd", "60"))); return
        m = int(args[0])
        if m < 1: send_msg(peer, "❌ Минимум 1 мин."); return
        set_setting(MD_CHAT_PEER, "announce_cd", str(m)); send_msg(peer, "✅ КД: {} мин.".format(m))

    elif cmd == "объявы":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        cur = get_setting(peer, "announcements_enabled", "1")
        if cur == "1":
            set_setting(peer, "announcements_enabled", "0"); send_msg(peer, "🔕 Объявления ВЫКЛ.")
        else:
            set_setting(peer, "announcements_enabled", "1"); send_msg(peer, "🔔 Объявления ВКЛ.")

    elif cmd == "топ":
        kb = json.dumps({"inline": True, "buttons": [
            [{"action": {"type": "callback", "label": "💬 Символы / ✉ Сообщения", "payload": json.dumps({"cmd": "top_messages", "page": 1})}, "color": "primary"},
             {"action": {"type": "callback", "label": "🎨 Стикеры", "payload": json.dumps({"cmd": "top_stickers", "page": 1})}, "color": "primary"}],
            [{"action": {"type": "callback", "label": "🎲 Кости", "payload": json.dumps({"cmd": "top_dice", "page": 1})}, "color": "primary"},
             {"action": {"type": "callback", "label": "✊✌️✋ КНБ", "payload": json.dumps({"cmd": "top_kmb", "page": 1})}, "color": "primary"}],
            [{"action": {"type": "callback", "label": "💒 Браки", "payload": json.dumps({"cmd": "top_marriages", "page": 1})}, "color": "primary"},
             {"action": {"type": "callback", "label": "📅 Дней в чате", "payload": json.dumps({"cmd": "top_days", "page": 1})}, "color": "primary"},
             {"action": {"type": "callback", "label": "🔥 Серий", "payload": json.dumps({"cmd": "top_streaks", "page": 1})}, "color": "primary"}]]})
        send_msg(peer, "🏆 Топы чата — выберите категорию:", keyboard=kb)

    elif cmd == "браки":
        with DB_LOCK:
            rows_all = CONN.execute("SELECT user1, user2, created_at FROM marriages WHERE peer_id=? ORDER BY created_at DESC", (peer,)).fetchall()
            active_rows = []
            for r in rows_all:
                m1 = CONN.execute("SELECT 1 FROM members WHERE user_id=? AND peer_id=?", (r["user1"], peer)).fetchone()
                m2 = CONN.execute("SELECT 1 FROM members WHERE user_id=? AND peer_id=?", (r["user2"], peer)).fetchone()
                if m1 or m2: active_rows.append(r)
        if not active_rows: send_msg(peer, "💒 Браков пока нет."); return
        now_ts = int(time.time())
        lines = ["💒 Браки пользователей чата:\n"]
        for r in active_rows:
            lines.append("{} и {} ({} дн.)".format(silent_mention_badge(r["user1"], peer), silent_mention_badge(r["user2"], peer), (now_ts - r["created_at"]) // 86400))
        send_msg(peer, "\n".join(lines))

    elif cmd == "брак":
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Формат: `Мд брак @игрок`"); return
        target = targets[0]
        if target == sender: send_msg(peer, "❌ На себе жениться нельзя!"); return
        if get_marriage(peer, sender): send_msg(peer, "❌ Ты уже в браке!"); return
        if get_marriage(peer, target): send_msg(peer, "❌ {} уже в браке!".format(silent_mention_badge(target, peer))); return
        kb = json.dumps({"inline": True, "buttons": [[
            {"action": {"type": "callback", "label": "💍 Согласиться", "payload": json.dumps({"cmd": "marriage_accept", "proposer": sender, "target": target})}, "color": "positive"},
            {"action": {"type": "callback", "label": "❌ Отказать", "payload": json.dumps({"cmd": "marriage_decline", "proposer": sender, "target": target})}, "color": "negative"}]]})
        try:
            msg_id = VK.messages.send(peer_id=peer, message="💍 {} делает предложение {}!\nЧто скажешь? ⏰ 1 минута".format(
                silent_mention_badge(sender, peer), mention(target)), keyboard=kb, random_id=random.getrandbits(31))
            cmid = resolve_cmid(peer, msg_id)
            with DB_LOCK:
                CONN.execute("INSERT INTO dice_games(peer_id, initiator, opponent, state, message_id, created_at) VALUES(?,?,?,?,?,?)", (peer, sender, target, "marriage", cmid, int(time.time())))
                CONN.commit()
        except Exception as e: print("marriage send error:", e)

    elif cmd == "развод":
        marriage = get_marriage(peer, sender)
        if not marriage: send_msg(peer, "❌ Ты не в браке."); return
        if args and args[0].lower() == "подтвердить":
            partner = get_marriage_partner(marriage, sender)
            with DB_LOCK:
                CONN.execute("DELETE FROM marriages WHERE id=?", (marriage["id"],)); CONN.commit()
            set_setting(peer, "divorce_confirm_{}".format(sender), "")
            send_msg(peer, "💔 {} и {} развелись.".format(silent_mention_badge(sender, peer), silent_mention_badge(partner, peer)))
        else:
            set_setting(peer, "divorce_confirm_{}".format(sender), "ожидание")
            send_msg(peer, "🥲 Для подтверждения развода напишите: `Мд развод подтвердить`")

    elif cmd == "онлайн":
        try:
            members_resp = VK.messages.getConversationMembers(peer_id=peer)
            user_ids = [p["id"] for p in members_resp.get("profiles", []) if p.get("id", 0) > 0]
            if not user_ids: send_msg(peer, "❌ Нет участников."); return
            online_users = []
            for i in range(0, len(user_ids), 100):
                chunk = user_ids[i:i+100]
                try:
                    users_data = VK.users.get(user_ids=",".join(map(str, chunk)), fields="online,last_seen")
                    for u in users_data:
                        if u.get("online") == 1:
                            platform = (u.get("last_seen", {}) or {}).get("platform", 0)
                            icon = "🍏" if platform in [2,3,4] else ("🖥️" if platform in [5,6] else "📱")
                            online_users.append((u.get("first_name", "") + " " + u.get("last_name", ""), icon, u["id"]))
                except: pass
            if not online_users: send_msg(peer, "📝 Никто не онлайн."); return
            lines = ["📝 Список пользователей онлайн:\n"]
            for idx, (name, icon, uid) in enumerate(online_users, 1):
                lines.append("{}. {} ({})".format(idx, silent_mention(uid), icon))
            send_msg(peer, "\n".join(lines))
        except Exception as e: send_msg(peer, "❌ Ошибка: {}".format(e))

    elif cmd == "др":
        try:
            sync_members(peer)
            now_msk = get_msk_now()
            with DB_LOCK:
                member_ids = [r["user_id"] for r in CONN.execute("SELECT user_id FROM members WHERE peer_id=?", (peer,)).fetchall()]
            if not member_ids: send_msg(peer, "❌ Нет участников."); return
            bdate_map = get_bdate_map(member_ids)
            fill_bdates_from_vk(peer, member_ids, bdate_map)
            upcoming = []
            for uid, bdate in bdate_map.items():
                parts = bdate.split(".")
                if len(parts) < 2: continue
                try: day, month = int(parts[0]), int(parts[1])
                except: continue
                try: bday = now_msk.replace(month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
                except: continue
                if bday.date() < now_msk.date():
                    try: bday = bday.replace(year=now_msk.year + 1)
                    except: continue
                diff = (bday - now_msk).days
                if 0 <= diff <= 60:
                    upcoming.append((diff, uid, get_zodiac(day, month), "{} {}".format(day, RU_MONTHS[month-1])))
            upcoming.sort(key=lambda x: x[0])
            if not upcoming: send_msg(peer, "📝 Ближайших дней рождения нет."); return
            lines = ["📝 Ближайшие дни рождения:\n"]
            for diff, uid, zodiac, ds in upcoming:
                day_word = "день" if diff == 1 else ("дня" if 2 <= diff <= 4 else "дней")
                if diff == 0: lines.append("{} [{}]: сегодня! 🎉".format(silent_mention_badge(uid, peer), zodiac))
                else: lines.append("{} [{}]: через {} {} ({})".format(silent_mention_badge(uid, peer), zodiac, diff, day_word, ds))
            send_msg(peer, "\n".join(lines))
        except Exception as e: send_msg(peer, "❌ Ошибка: {}".format(e))

    elif cmd == "кто_я":
        last_ts = int(get_setting(peer, "who_i_cd_{}".format(sender), "0") or "0")
        now_ts = int(time.time())
        diff = now_ts - last_ts
        if diff < 10800:
            rem = 10800 - diff
            m, s = divmod(rem, 60)
            send_msg(peer, "⏳ {}, вы уже использовали эту команду. До следующего раза осталось {}:{:02d}".format(silent_mention_badge(sender, peer), m, s))
            return
        with DB_LOCK:
            CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (sender, peer))
        if random.randint(1, 100) == 1:
            legend = random.choice(LEGENDARY_WHO)
            with DB_LOCK:
                CONN.execute("UPDATE members SET who_name=?, who_ts=? WHERE user_id=? AND peer_id=?", (legend, now_ts, sender, peer)); CONN.commit()
            set_setting(peer, "who_i_cd_{}".format(sender), str(now_ts))
            send_msg(peer, "🍀 {}, поздравляю вы получили легендарный статус - **{}**! (Шанс 1%)".format(silent_mention_badge(sender, peer), legend))
            return
        adj = random.choice(WHO_ADJ)
        noun = random.choice(WHO_NOUN)
        phrase = "{} {}".format(adj_form(adj, noun_gender(noun)), noun)
        with DB_LOCK:
            CONN.execute("UPDATE members SET who_name=?, who_ts=? WHERE user_id=? AND peer_id=?", (phrase, now_ts, sender, peer)); CONN.commit()
        set_setting(peer, "who_i_cd_{}".format(sender), str(now_ts))
        send_msg(peer, "🍀 {}, вы - {}".format(silent_mention_badge(sender, peer), phrase))

    elif cmd == "кто":
        word = " ".join(args) if args else "это"
        try:
            members_resp = VK.messages.getConversationMembers(peer_id=peer)
            user_ids = [int(i.get("member_id", 0)) for i in members_resp.get("items", []) if int(i.get("member_id", 0)) > 0]
            if not user_ids: send_msg(peer, "❌ Нет участников."); return
            send_msg(peer, "💬 {},  очевидно, {} — {}!".format(silent_mention_badge(sender, peer), word, silent_mention_badge(random.choice(user_ids), peer)))
        except Exception as e: print("кто error:", e)

    elif cmd == "инфа":
        send_msg(peer, "💬 {}, вероятно, это {}%.".format(silent_mention_badge(sender, peer), random.randint(0, 100)))

    elif cmd == "монетка":
        result = random.choice([("орёл🪙", "выпал"), ("решка1️⃣", "выпала")])
        send_msg(peer, "{}, {} {}!".format(silent_mention_badge(sender, peer), result[1], result[0]))

    elif cmd == "+правила":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        reply = msg_obj.get("reply_message", {})
        if not isinstance(reply, dict) or not reply.get("text"): send_msg(peer, "❌ Ответь на сообщение с правилами."); return
        set_setting(peer, "rules_text", reply["text"].strip()); send_msg(peer, "✅ Правила установлены.")

    elif cmd == "-правила":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        set_setting(peer, "rules_text", ""); send_msg(peer, "✅ Правила удалены.")

    elif cmd == "правила":
        rules = get_setting(peer, "rules_text", "")
        send_msg(peer, "📜 Правила чата:\n{}".format(rules) if rules else "ℹ️ Правила не установлены.")

    elif cmd == "+приветствие":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        reply = msg_obj.get("reply_message", {})
        if not isinstance(reply, dict) or not reply.get("text"): send_msg(peer, "❌ Ответь на сообщение с приветствием."); return
        set_setting(peer, "greeting_text", reply["text"].strip()); send_msg(peer, "✅ Приветствие установлено.")

    elif cmd == "-приветствие":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        set_setting(peer, "greeting_text", ""); send_msg(peer, "✅ Приветствие удалено.")

    elif cmd == "приветствие":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        greeting = get_setting(peer, "greeting_text", "")
        send_msg(peer, "👋 Приветствие:\n{}".format(greeting) if greeting else "ℹ️ Приветствие не установлено.")

    elif cmd == "значок":
        if not args:
            cur = get_badge(sender, peer)
            if cur: send_msg(peer, "🏷 Ваш значок: {}".format(cur))
            else: send_msg(peer, "ℹ️ У вас ещё нет значка.\nУстановить: `Мд значок <эмодзи/цифры>` (макс. 4 символа, не больше 1 эмодзи).")
            return
        badge_str = args[0]
        if len(badge_str) > 4: send_msg(peer, "❌ Значок не может быть длиннее 4 символов!"); return
        rest = "".join(ch for ch in badge_str if not ch.isdigit())
        if rest and not EM_CLUSTER.match(rest): send_msg(peer, "❌ Значок: максимум 1 эмодзи + цифры!"); return
        with DB_LOCK:
            CONN.execute("INSERT OR REPLACE INTO badges(user_id, peer_id, emoji) VALUES(?,?,?)", (sender, peer, badge_str)); CONN.commit()
        send_msg(peer, "✅ Значок {} установлен!".format(badge_str))

    elif cmd == "удалить_значок":
        with DB_LOCK:
            CONN.execute("DELETE FROM badges WHERE user_id=? AND peer_id=?", (sender, peer)); CONN.commit()
        send_msg(peer, "✅ Значок удалён.")

    elif cmd == "значки":
        with DB_LOCK:
            rows = CONN.execute("SELECT user_id, emoji FROM badges WHERE peer_id=? AND emoji!=''", (peer,)).fetchall()
        if not rows: send_msg(peer, "ℹ️ Значков нет."); return
        lines = ["🏷 Значки участников:\n"]
        for r in rows: lines.append("{} — {}".format(silent_mention_badge(r["user_id"], peer), r["emoji"]))
        send_msg(peer, "\n".join(lines))

    elif cmd == "карта":
        targets = extract_targets(" ".join(args), reply_from)
        target_id = targets[0] if targets else sender
        if target_id != sender and not admin:
            send_msg(peer, "⛔ Только админы могут смотреть чужие карты."); return
        send_card_to(peer, target_id)

    elif cmd == "карта_редактировать":
        set_card_state(sender, peer, "edit_menu", {"msg_cmid": None})
        send_msg(peer, MAIN_CARD_TEXT, keyboard=card_edit_main_kb())

    elif cmd == "карта_дизайн":
        set_card_state(sender, peer, "design_main", {"msg_cmid": None})
        send_msg(peer, DESIGN_MAIN_TEXT, keyboard=design_main_kb())

    elif cmd == "карта_очистить":
        fld = None
        for a in args:
            if a.lower() in CARD_FIELD_MAP: fld = CARD_FIELD_MAP[a.lower()]
        targets = extract_targets(" ".join(args), 0)
        if targets:
            if not admin: send_msg(peer, "⛔ Только админы могут чистить чужие карты."); return
            target_id = targets[0]
        else:
            target_id = sender
        if fld:
            default = "[]" if fld in ("businesses", "realty") else ""
            set_card_field(target_id, **{fld: default})
            send_msg(peer, "✅ Очищено поле карточки: {} ({}).".format(fld, silent_mention_badge(target_id, peer)))
        else:
            with DB_LOCK:
                CONN.execute("DELETE FROM player_cards WHERE user_id=?", (target_id,)); CONN.commit()
            send_msg(peer, "✅ Карточка {} очищена полностью.".format(silent_mention_badge(target_id, peer)))

def timer_loop():
    while True:
        try:
            time.sleep(10)
            if VK is None: continue
            now_msk = get_msk_now()
            today_str = now_msk.strftime("%Y-%m-%d")
            now = int(time.time())
            # Авто-таймаут редакторов карты/дизайна
            with DB_LOCK:
                stale = CONN.execute("SELECT user_id, peer_id, step, context FROM card_edit_state").fetchall()
            for row in stale:
                try: ctx = json.loads(row["context"] or "{}")
                except Exception: ctx = {}
                if now - ctx.get("ts", 0) > 60:
                    uid, pid = row["user_id"], row["peer_id"]
                    cm = ctx.get("msg_cmid")
                    with DB_LOCK:
                        CONN.execute("DELETE FROM card_edit_state WHERE user_id=? AND peer_id=?", (uid, pid))
                    txt = "Время на редактирование вышло, {} вы бездействовали минуту⏳".format(mention(uid))
                    if cm:
                        try:
                            VK.messages.edit(peer_id=pid, conversation_message_id=cm, message=txt, keyboard=json.dumps({"inline": True, "buttons": []}))
                            continue
                        except Exception: pass
                    send_msg(pid, txt)
            with DB_LOCK:
                expired = CONN.execute("SELECT * FROM dice_games WHERE state='pending' AND created_at<=?", (now-60,)).fetchall()
                if expired:
                    CONN.execute("UPDATE dice_games SET state='expired' WHERE state='pending' AND created_at<=?", (now-60,)); CONN.commit()
                for g in expired:
                    edit_game_message(g["peer_id"], g["id"], "⏰ Время вышло! {} не успел принять вызов от {} 🕐".format(
                        silent_mention_badge(g["opponent"], g["peer_id"]), silent_mention_badge(g["initiator"], g["peer_id"])))
                stuck_dice = CONN.execute("SELECT * FROM dice_games WHERE state='playing' AND created_at<=?", (now-600,)).fetchall()
                if stuck_dice:
                    CONN.execute("UPDATE dice_games SET state='expired' WHERE state='playing' AND created_at<=?", (now-600,)); CONN.commit()
                for g in stuck_dice:
                    edit_game_message(g["peer_id"], g["id"], "⏰ Игра в кости закрыта из-за бездействия (10 минут).")
                exp_m = CONN.execute("SELECT * FROM dice_games WHERE state='marriage' AND created_at<=?", (now-60,)).fetchall()
                if exp_m:
                    CONN.execute("UPDATE dice_games SET state='marriage_expired' WHERE state='marriage' AND created_at<=?", (now-60,)); CONN.commit()
                for g in exp_m:
                    edit_game_message(g["peer_id"], g["id"], "⏰ Время предложения истекло! 💔")
                expired_kmb = CONN.execute("SELECT * FROM kmb_games WHERE state IN ('pending','choosing') AND created_at<=?", (now-60,)).fetchall()
                if expired_kmb:
                    CONN.execute("UPDATE kmb_games SET state='expired' WHERE state IN ('pending','choosing') AND created_at<=?", (now-60,)); CONN.commit()
                for g in expired_kmb:
                    if g["state"] == "pending":
                        edit_game_message(g["peer_id"], g["id"], "⏰ КНБ: время вышло!", table="kmb_games")
                    else:
                        send_msg(g["peer_id"], "⏰ КНБ: время вышло! Игра закончена из-за AFK.")
                stuck_kmb = CONN.execute("SELECT * FROM kmb_games WHERE state='choosing' AND created_at<=?", (now-300,)).fetchall()
                if stuck_kmb:
                    CONN.execute("UPDATE kmb_games SET state='expired' WHERE state='choosing' AND created_at<=?", (now-300,)); CONN.commit()
                for g in stuck_kmb:
                    edit_game_message(g["peer_id"], g["id"], "⏰ КНБ закрыта из-за бездействия (5 минут).", table="kmb_games")
                pend_rows = CONN.execute("SELECT peer_id, value FROM settings WHERE key='top_clean_pending'").fetchall()
            for pr in pend_rows:
                try: pend = json.loads(pr["value"])
                except: pend = None
                if not pend:
                    set_setting(pr["peer_id"], "top_clean_pending", ""); continue
                if int(time.time()) - pend.get("ts", 0) > 60:
                    set_setting(pr["peer_id"], "top_clean_pending", "")
                    send_msg(pr["peer_id"], "⏰ Время подтверждения очистки топа истекло. Отменено.")
            with DB_LOCK:
                due = CONN.execute("SELECT * FROM dice_mentions WHERE next_trigger<=? AND end_time>?", (now, now)).fetchall()
            for dm in due:
                send_msg(dm["peer_id"], "🎲 {}, {}".format(mention(dm["user_id"]), random.choice(DICE_PHRASES)))
                nt = now + dm["interval_minutes"] * 60
                with DB_LOCK:
                    if nt >= dm["end_time"]: CONN.execute("DELETE FROM dice_mentions WHERE id=?", (dm["id"],))
                    else: CONN.execute("UPDATE dice_mentions SET next_trigger=? WHERE id=?", (nt, dm["id"]))
                    CONN.commit()
            with DB_LOCK:
                peers = CONN.execute("SELECT DISTINCT peer_id FROM reminders").fetchall()
                bday_peers = CONN.execute("SELECT DISTINCT peer_id FROM members").fetchall()
                control_peers = CONN.execute("SELECT DISTINCT peer_id FROM settings WHERE key='control_active' AND value='1'").fetchall()
            for p in peers:
                peer = p["peer_id"]
                now_t = time.time()
                with DB_LOCK:
                    due_rem = CONN.execute("SELECT id, name, text, attachments, source_message_id, interval_minutes, repeat_count, enabled FROM reminders WHERE peer_id=? AND next_trigger<=?", (peer, now_t)).fetchall()
                for rem in due_rem:
                    if rem["enabled"] == 1:
                        for _ in range(rem["repeat_count"] or 1):
                            if rem["source_message_id"]:
                                try:
                                    fj = json.dumps({"peer_id": peer, "conversation_message_ids": [rem["source_message_id"]]})
                                    VK.messages.send(peer_id=peer, message="🔔 Напоминание: {}\n@all".format(rem['name']), forward=fj, random_id=random.getrandbits(31))
                                except:
                                    send_msg(peer, "🔔 Напоминание: {}\n{}\n@all".format(rem['name'], rem['text']), attachments=rem["attachments"] or None)
                            else:
                                send_msg(peer, "🔔 Напоминание: {}\n{}\n@all".format(rem['name'], rem['text']), attachments=rem["attachments"] or None)
                            time.sleep(0.5)
                        with DB_LOCK:
                            CONN.execute("UPDATE reminders SET next_trigger=? WHERE id=?", (now_t + rem["interval_minutes"]*60, rem["id"])); CONN.commit()
                last_poll_msg = get_setting(peer, "last_poll_msg_id", "")
                last_poll_time = int(get_setting(peer, "last_poll_time", "0") or "0")
                if last_poll_msg and last_poll_msg.isdigit() and (time.time() - last_poll_time) > 600:
                    try: VK.messages.delete(peer_id=peer, message_ids=[int(last_poll_msg)], delete_for_all=1)
                    except: pass
                    set_setting(peer, "last_poll_msg_id", ""); set_setting(peer, "last_poll_time", "0")
            if now_msk.hour == 0 and now_msk.minute == 0:
                for p in bday_peers: check_birthdays(p["peer_id"])
            if now_msk.minute == 0:
                peers_to_sync = list(set([p["peer_id"] for p in control_peers]))
                if peers_to_sync:
                    threading.Thread(target=sync_all_peers, args=(peers_to_sync,), daemon=True).start()
            for p in control_peers:
                peer = p["peer_id"]
                sh = int(get_setting(peer, "poll_start", "10")); eh = int(get_setting(peer, "poll_end", "22")); pm = int(get_setting(peer, "poll_minute", "25"))
                ch = now_msk.hour
                is_active = (sh <= ch <= eh) if sh <= eh else (ch >= sh or ch <= eh)
                if now_msk.minute == pm and is_active:
                    lpk = "last_poll_{}{}".format(ch, pm)
                    if get_setting(peer, lpk, "0") != "1":
                        pct = int(time.time())
                        kb = json.dumps({"inline": True, "buttons": [[{"action": {"type": "callback", "label": "✅ Проголосовать: Я", "payload": json.dumps({"cmd": "poll_vote", "time": pct})}, "color": "positive"}]]})
                        try:
                            mid = VK.messages.send(peer_id=peer, message="📊 Опрос: Кто заходит на этот кд? @all", keyboard=kb, random_id=random.getrandbits(31))
                            set_setting(peer, lpk, "1"); set_setting(peer, "last_poll_msg_id", str(mid)); set_setting(peer, "last_poll_time", str(pct))
                        except: pass
                check_time = now_msk.replace(hour=int(get_setting(peer, "check_hour", "23")), minute=int(get_setting(peer, "check_minute", "0")), second=0, microsecond=0)
                if now_msk >= check_time and get_setting(peer, "last_23_check", "") != today_str:
                    admins = set(get_users_with_min_role(peer, 2)); admins.add(CREATOR_ID); admins.add(LEADER_ID)
                    co = get_chat_owner(peer)
                    if co: admins.add(co)
                    with DB_LOCK:
                        members = CONN.execute("SELECT user_id FROM members WHERE peer_id=? AND poll_protected=0", (peer,)).fetchall()
                        voted = set(r["user_id"] for r in CONN.execute("SELECT user_id FROM poll_votes WHERE peer_id=? AND date=?", (peer, today_str)).fetchall())
                    mw = int(get_setting(peer, "max_warns", "3") or "3")
                    dd = int(get_setting(peer, "default_warn_days", "7") or "7")
                    expiry = time.time() + dd * 86400
                    inactive = [m["user_id"] for m in members if m["user_id"] not in voted and m["user_id"] not in admins]
                    if inactive:
                        lines = ["⚠️ Неактивные за день (+1 пред):\n"]
                        for uid in inactive:
                            with DB_LOCK:
                                row = CONN.execute("SELECT warnings, warn_durations FROM members WHERE user_id=? AND peer_id=?", (uid, peer)).fetchone()
                                cw = (row["warnings"] or 0) + 1 if row else 1
                                od = row["warn_durations"] if row and row["warn_durations"] else ""
                                ds = "∞" if dd >= 9999 else str(dd)
                                nd = "{}|{}".format(od, ds) if od else ds
                                CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=? WHERE user_id=? AND peer_id=?", (cw, nd, expiry, uid, peer)); CONN.commit()
                            lines.append("{} ({}/{})".format(silent_mention_badge(uid, peer), cw, mw))
                            if cw >= mw:
                                try:
                                    VK.messages.removeChatUser(chat_id=peer-2000000000, member_id=uid)
                                    with DB_LOCK:
                                        CONN.execute("UPDATE members SET warnings=0, warn_durations='', warn_expiry=0 WHERE user_id=? AND peer_id=?", (uid, peer)); CONN.commit()
                                except: pass
                        send_msg(peer, "\n".join(lines))
                    set_setting(peer, "last_23_check", today_str)
            if now_msk.minute == 0:
                for p in control_peers:
                    peer = p["peer_id"]
                    with DB_LOCK:
                        no_nicks = CONN.execute("SELECT user_id FROM members WHERE peer_id=? AND (nickname='' OR nickname IS NULL)", (peer,)).fetchall()
                    for u in no_nicks:
                        lr = int(get_setting(peer, "nick_rem_{}".format(u['user_id']), "0"))
                        if time.time() - lr > 3600:
                            send_msg(peer, "🔔 {}, установи ник: `Мд ник <ник>`!".format(mention(u['user_id'])))
                            set_setting(peer, "nick_rem_{}".format(u['user_id']), str(int(time.time())))
        except Exception as e:
            print("timer error:", e)
        time.sleep(10)

def main():
    global VK
    print("=== MD BOT starting ===")
    init_db()
    threading.Thread(target=timer_loop, daemon=True).start()
    if not VK_TOKEN:
        print("ERROR: VK_TOKEN not set!")
        while not VK_TOKEN: time.sleep(60)
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
                if event.type != VkBotEventType.MESSAGE_NEW: continue
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
