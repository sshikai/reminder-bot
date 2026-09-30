import os, re, io, glob, time, random, sqlite3, threading, json, datetime, urllib.request, requests
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except Exception: PIL_OK = False

VK_TOKEN = os.environ.get("VK_TOKEN", "").strip()
CREATOR_ID = 479753606
LEADER_ID = 639963159
MD_CHAT_PEER = 2000000004
MSK_TZ = datetime.timezone(datetime.timedelta(hours=3))
CLEAR_PENDING = {}
def get_msk_now(): return datetime.datetime.now(MSK_TZ)

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

DICE_PHRASES = ["Фортуна повернулась к тебе самым неприличным местом. 🍑", "Твой максимум — это бросать кости собакам. 🐕", "Удача сегодня посмотрела на тебя, посмеялась и ушла ко мне. 😏", "Кости любят смелых, а над наивными они просто ржут. 🦴", "Ты проиграл генератору случайных чисел. 🧬💀", "Пискоструй ты где? Не забыл? Ты проебал в кости. 📢", "Эй чепуха, твой проёб не забыли. 🤡", "Ты проиграл, но ты держись там. 😔", "Ну что, допизделся, фартовый? Кости легли раком. 🦀", "Удача сегодня посмотрела на твою рожу, плюнула и ушла. 🤮", "Твоя удача осталась где-то далеко. 😢", "Твоя удача сегодня ушла к кому-то с нормальными руками. 🖐️", "У тебя руки из задницы растут. 🍑🌱", "Это не просто проигрыш, это историческое унижение. 🧳", "Смирись, ты сегодня официально признан главным неудачником. 🏆", "Эй инопланетянин, ты помнишь как ты сыграл? 👽", "В мире есть три вещи которые не меняются: вращение земли, рассвет солнца и твои проёбы! 🌍️", "Прикинь как было бы хорошо если бы ты выиграл? Но нет.... 😭", "Я уверен что в параллельной вселенной ты бы смог выиграть. 🌌", "Я бот - ты человек, разница в том что я не умею проигрывать как ты! 🤖", "Ничего лишнего, просто напомню что ты проиграл! 📋", "Тебе говорили не играй в кости казино? 🎰", "Прикинь, пересматривал код и увидел твой проёб. 💻"]
LEADER_BDAY_TEXT = "Дорогой лидер Million Dollars🎉\nОт лица всего состава поздравляю тебя с днем рождения!\n\nСпасибо за твой огромный вклад в развитие Million Dollars и за то, что собрал под одним крылом таких крутых ребят.\n\nЖелаем тебе железобетонного терпения, преданных замов, огромного онлайна и чтобы никто не портил тебе настроение. Пусть наша семья гремит по всему серверу! 💰\n\n{mention}"
DEFAULT_BDAY_TEXT = "Поздравляем {mention}. У него сегодня день рождения!"

VALID_COMMANDS = ["команды","админы","участник","участники","ники","ник","парк","прем","чат","пред","снять_пред","лимит_предов","кд_предов","старт_контроль","стоп_контроль","время_опросов","защита","-защита","бан","разбан","баны","адмчат","admg","номер_чата","текст_др","создать","список","удалить","редактировать","включить","отключить","развернуть","назначить","снять","голоса","тишина","тишина_офф","проверка_опроса","бр","мут","снять_мут","муты","преды","предлист","статус","статусы","проверка","кости","объява","обьява","объявы","обьявы","объяв","обьяв","кд_объяв","кд_обьяв","топ","браки","брак","развод","онлайн","др","кто","кто_я","инфа","монетка","+правила","-правила","правила","+приветствие","-приветствие","приветствие","значок","удалить_значок","значки","кнб","чистка","айди","запретить_игры","разрешить_игры","очистить_топ","карта","карта_редактировать","редактор_карты","очистить_карту","запретить_редактор","разрешить_редактор"]
ROLE_NAMES = {0:"Участник", 1:"👮‍️ Модератор", 2:"🛡 Админ", 3:"🥷 Главный Админ", 4:"👑 Владелец"}
RU_MONTHS = ["янв","фев","мар","апр","мая","июн","июл","авг","сен","окт","ноя","дек"]
NUM_EMOJI = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]

_EM_BASE = "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\u2600-\u26FF\u2700-\u27BF\u2B00-\u2BFF\u2190-\u21FF\u2300-\u23FF\U0001F1E6-\U0001F1FF\u24C2\u2702-\u27B0\U0001F004\U0001F0CF\U0001F170-\U0001F251]"
_EM_ONE = _EM_BASE + "[\U0001F3FB-\U0001F3FF]?\uFE0F?"
EM_CLUSTER = re.compile("^" + _EM_ONE + "(?:\u200D" + _EM_ONE + ")*$")

BUS_TYPES_ORDER = ["АЗС","Амуниция","Одежда","Аксессуары","24/7","ТК БУС","ТК БАТ","СК","ПВЗ","Ларек","Закуска","Мотосалон","Выс. салон","Сред. салон","Низ. салон","Лод. салон","Такопарк","Шинка","Стайлинг","Тех. Центр"]
BUS_NO_NUM = {"Мотосалон","Выс. салон","Сред. салон","Низ. салон","Лод. салон","Такопарк","Шинка","Стайлинг","Тех. Центр"}
BUS_SLOT2 = ("ТК БУС","ТК БАТ","СК","Такопарк")
BUS_TAKO = "Такопарк"
BUS_PAGES = 4
BUS_PER_PAGE = 6

CARD_FIELD_MAP = {"бизнесы":"businesses","недвижимость":"realty","имущество":"property_val","гараж":"garage","телефон":"phone","имя":"name"}
CARD_DATA_KEYS = set(CARD_FIELD_MAP.values())
PARAM_MAP = {"бизнесы":"businesses","недвижимость":"realty","имущество":"property_val","гараж":"garage","телефон":"phone","имя":"name","фото":"photo"}
FIELD_DEFAULT = {"businesses":"[]","realty":"[]","property_val":"","garage":"","phone":"","name":""}
PARAM_HINT = "бизнесы, недвижимость, имущество, гараж, телефон, фото, имя"

COLORS_ORDER = [("red","Красный"),("red_full","Полностью красный"),("green","Зеленый"),("green_full","Полностью зеленый"),("blue","Синий"),("blue_full","Полностью синий"),("lblue","Голубой"),("lblue_full","Полностью голубой"),("yellow","Желтый"),("yellow_full","Полностью желтый"),("orange","Оранжевый"),("orange_full","Полностью оранжевый"),("pink","Розовый"),("pink_full","Полностью розовый"),("violet","Фиолетовый"),("violet_full","Полностью фиолетовый"),("gray","Серый"),("blackblue","Черно синий"),("blackviolet","Черно фиолетовый"),("blackpink","Черно розовый"),("blackred","Черно красный"),("blackorange","Черно оранжевый"),("blackyellow","Черно желтый"),("blackgreen","Черно зеленый"),("blacklblue","Черно голубой"),("blackgray","Черно серый")]
ALL_COLOR_KEYS = set(k for k, _ in COLORS_ORDER)
DESIGN_PER_PAGE = 6
def design_pages_count(): return max(1, -(-len(COLORS_ORDER) // DESIGN_PER_PAGE))

TEXT_COLOR_ORDER = [("blue","Синий"),("lblue","Голубой"),("pink","Розовый"),("violet","Фиолетовый"),("red","Красный"),("orange","Оранжевый"),("yellow","Желтый"),("green","Зеленый"),("gray","Серый"),("white","Белый"),("black","Черный")]
TEXT_COLORS = {"blue":(0,0,255),"lblue":(0,191,255),"pink":(255,20,147),"violet":(138,43,226),"red":(255,0,0),"orange":(255,140,0),"yellow":(255,215,0),"green":(0,150,0),"gray":(128,128,128),"white":(255,255,255),"black":(0,0,0)}
TEXT_PER_PAGE = 6
def text_color_pages(): return max(1, -(-len(TEXT_COLOR_ORDER) // TEXT_PER_PAGE))

POS_FIELDS = {"biz":"Бизнесы","realty":"Недвижимость","prop":"Имущество","garage":"Гараж","phone":"Телефон","name":"Имя"}
POS_STEP = 0.0025
FRAME_BOX = (0.070, 0.190, 0.280, 0.605)
FRAME_BOXES_FILE = os.path.join(DATA_DIR, "frame_boxes.json")
_FRAME_BOXES_CACHE = {"data": None, "ts": 0.0}

WHO_ADJ = ("тайный безумный сонный хитрый гордый дерзкий мудрый лютый ленивый грустный честный добрый грозный дикий верный робкий нежный бойкий строгий упрямый мирный жуткий милый чудной скромный хмурый бодрый хладнокровный растерянный уставший вдохновленный хвастливый мнительный отчаянный наивный суровый ласковый скрытный ревнивый азартный космический призрачный огненный ледяной грозовой звездный теневой лунный солнечный ветреный болотный подземный небесный морской туманный радиоактивный токсичный квантовый магический мистический цифровой виртуальный неоновый пиксельный кибернетический древний вечный проклятый святой потусторонний железный золотой алмазный плюшевый деревянный каменный стеклянный бархатный шелковый ватный бумажный картонный пластиковый резиновый ржавый глянцевый матовый колючий пушистый гладкий липкий скользкий твердый мягкий хрупкий жидкий газообразный порошковый шершавый летучий гигантский крошечный круглый квадратный плоский кривой прямой бесконечный микроскопический массивный тонкий толстый узкий широкий вытянутый раздутый сжатый угловатый симметричный безразмерный кислый сладкий горький соленый острый пряный мятный шоколадный ванильный чесночный сырный карамельный лимонный имбирный медовый жареный вареный сырой копченый тушеный четкий хайповый кринжовый рофляный легендарный эпический дефолтный душный имбовый читерский забивной суетной пафосный блатной козырной фартовый люксовый бюджетный запрещенный заряженный базированный гигачадский мемный флексящий вайбовый чилловый попкорновый пельменный чебуречный красный синий зеленый желтый фиолетовый оранжевый розовый черный белый серый бордовый бирюзовый золотистый серебряный изумрудный яркий тусклый светящийся бледный разноцветный богатый бедный успешный потерянный сломанный починенный забытый популярный секретный опасный безопасный редкий обычный элитный финальный начальный главный запасной невидимый неуязвимый серверный региональный деловой бригадный гаражный трассовый премиальный дрифтовый").split()
WHO_NOUN = ("енот кот пес лис волк медведь лев тигр панда хомяк суслик выдра бобр заяц еж крот олень лось кабан слон жираф бегемот носорог обезьяна ленивец коала кенгуру утконос пингвин фламинго сова орел ворон попугай голубь лебедь акула дельфин кит краб кальмар осьминог креветка рак медуза ящерица змея хамелеон лягушка жаба дракон феникс единорог грифон пегас кентавр минотавр сфинкс гарпия сирена эльф гном орк гоблин тролль огр маг чародей шаман некромант ведьма колдун алхимик рыцарь паладин самурай ниндзя викинг пират призрак вампир оборотень зомби мумия демон ангел титан голем джинн леший шпион детектив хакер программист геймер стример блогер админ модератор босс директор шеф повар официант доктор хирург ученый профессор космонавт пилот капитан штурман водитель гонщик каскадер строитель инженер архитектор художник музыкант актер режиссер писатель поэт фотограф дизайнер модель стилист учитель тренер синяк крекер торетто стрипуха робот киборг андроид дрон процессор чип сервер ноут комп телефон плеер калькулятор лазер бластер ракета спутник телескоп микроскоп радар компас фонарик проектор экран монитор джойстик геймпад кабель провод переходник флешка пельмень чебурек хинкали блин вареник пирожок пончик круассан кекс торт пицца бургер хотдог суши ролл картофан огурец помидор баклажан кабачок арбуз дыня ананас банан яблоко груша лимон апельсин орех гриб суп борщ майонез кетчуп соус горчица сухарик чипс попкорн зефир кактус фикус баобаб дуб цветок роза лотос кристалл алмаз изумруд рубин янтарь метеорит астероид комета планета звезда галактика космос атом ларгус приора бустер мент бандит бизнесмен шахтер дрифтер регион бизнес").split()
WHO_GENDER_EXCEPTIONS = {"торетто":"m","кофе":"m"}
_WHO_FEM_SOFT = {"модель","ночь","мышь","тень","дверь","кровать","площадь","пыль","соль","ткань","кровь","любовь","морковь","грязь","шерсть","смерть"}
_HARD_ENDINGS = set("гкхжчшщ")
def noun_gender(n):
    if n in WHO_GENDER_EXCEPTIONS: return WHO_GENDER_EXCEPTIONS[n]
    if n.endswith(("а","я")): return "f"
    if n.endswith(("о","е")): return "n"
    if n.endswith("ь"): return "f" if n in _WHO_FEM_SOFT else "m"
    return "m"
def adj_form(adj, gender):
    if gender == "m": return adj
    if adj.endswith("ой"): stem = adj[:-2]; fem, neu = stem + "ая", stem + "ое"
    elif adj.endswith("ый"): stem = adj[:-2]; fem, neu = stem + "ая", stem + "ое"
    elif adj.endswith("ий"):
        stem = adj[:-2]
        if stem and stem[-1] in _HARD_ENDINGS: fem, neu = stem + "ая", stem + "ое"
        else: fem, neu = stem + "яя", stem + "ее"
    else: return adj
    return fem if gender == "f" else neu

def fmt_join_date(ts):
    dt = datetime.datetime.fromtimestamp(ts, MSK_TZ)
    return "{} {} {}".format(dt.day, RU_MONTHS[dt.month - 1], dt.year)
def days_since(ts): return max(0, int((time.time() - ts) // 86400))
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
    if user_id in (CREATOR_ID, LEADER_ID, get_chat_owner(peer)): return 4
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
    with DB_LOCK: return [int(r["user_id"]) for r in CONN.execute("SELECT user_id FROM roles WHERE peer_id=? AND role>=?", (peer, min_role)).fetchall()]
def get_badge(user_id, peer_id):
    with DB_LOCK:
        row = CONN.execute("SELECT emoji FROM badges WHERE user_id=? AND peer_id=?", (user_id, peer_id)).fetchone()
        return row["emoji"] if row else ""
def silent_mention_badge(user_id, peer_id):
    badge = get_badge(user_id, peer_id)
    name = get_user_name(user_id)
    return "[https://vk.com/id{}|{}{}]".format(user_id, name, " " + badge if badge else "")
def can_punish(sender, target, peer):
    if sender in (CREATOR_ID, LEADER_ID): return True
    if target in (CREATOR_ID, LEADER_ID): return False
    sender_role, target_role = get_user_role(peer, sender), get_user_role(peer, target)
    if sender == get_chat_owner(peer): return target_role < 4 or target != get_chat_owner(peer)
    if target == get_chat_owner(peer): return False
    return target_role < sender_role
def add_punishment(peer, user_id, p_type, reason, message_id, message_text, issued_by, duration_minutes=0):
    with DB_LOCK:
        CONN.execute("""INSERT INTO punishment_history(peer_id, user_id, type, reason, message_id, message_text, issued_by, issued_at, duration_minutes) VALUES(?,?,?,?,?,?,?,?,?)""", (peer, user_id, p_type, reason, message_id or 0, message_text or "", issued_by, int(time.time()), duration_minutes))
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
BR_COLOR_EMOJI = {"RED":"🟥","GREEN":"🟩","BLUE":"🟦","YELLOW":"🟨","ORANGE":"🟧","PURPLE":"🟪","VIOLET":"🟪","BLACK":"⬛","WHITE":"⬜","PINK":"🌸","CYAN":"🟦","TURQUOISE":"🟦","LIME":"🟩","CHERRY":"🍒","INDIGO":"🦋","MAGENTA":"🎀","CRIMSON":"🌺","GOLD":"⭐️","AZURE":"🧿","PLATINUM":"💍","AQUA":"🐟","GRAY":"🐰","GREY":"🐰","ICE":"🧊"}
def fetch_br_servers():
    now = time.time()
    if BR_CACHE["data"] is not None and (now - BR_CACHE["time"]) < 300: return BR_CACHE["data"]
    try:
        req = urllib.request.Request(BR_API_URL, headers={"User-Agent": "Mozilla/5.0 (MD BOT)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list): BR_CACHE["time"] = now; BR_CACHE["data"] = data; return data
            return BR_CACHE["data"]
    except Exception as e: print("BR API error:", e); return BR_CACHE["data"]
def build_br_page(page):
    servers = fetch_br_servers()
    if not servers: return None, None, 1
    total = len(servers); total_pages = max(1, (total + BR_PER_PAGE - 1) // BR_PER_PAGE)
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
    lines = ["📱 Общий онлайн проекта BlackRussia: {}".format(total_online), "🏆 Общий рекордный онлайн за день: {}\n".format(total_record)]
    start_idx = (page - 1) * BR_PER_PAGE
    for i, s in enumerate(chunk, start_idx + 1):
        fname = str(s.get("firstname", "  ") or s.get("name", "  ")).strip()
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
    if user_id in (CREATOR_ID, LEADER_ID): return True
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

def is_inspector(user_id): return get_setting(0, "inspector_{}".format(user_id), "0") == "1"
def is_auctioneer(user_id): return get_setting(0, "auctioneer_{}".format(user_id), "0") == "1"
def get_all_auctioneers():
    with DB_LOCK: return [int(r["key"].replace("auctioneer_", "")) for r in CONN.execute("SELECT key FROM settings WHERE key LIKE 'auctioneer_%' AND value='1'").fetchall()]
def get_all_inspectors():
    with DB_LOCK: return [int(r["key"].replace("inspector_", "")) for r in CONN.execute("SELECT key FROM settings WHERE key LIKE 'inspector_%' AND value='1'").fetchall()]
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
def chat_exists(pid):
    try: r = VK.messages.getConversationsById(peer_ids=[pid]); return bool(r.get("items"))
    except: return False

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
        if is_sticker: CONN.execute("UPDATE message_stats SET msg_count=msg_count+1, sticker_count=sticker_count+1, char_count=char_count+? WHERE user_id=? AND peer_id=?", (chars, user_id, peer))
        else: CONN.execute("UPDATE message_stats SET msg_count=msg_count+1, char_count=char_count+? WHERE user_id=? AND peer_id=?", (chars, user_id, peer))
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

# ===== ЭКСКЛЮЗИВНЫЕ КАРТЫ =====
def strict_template(name):
    if not name: return None
    nm = name.strip()
    if nm.lower().endswith((".png", ".jpg", ".jpeg")): nm = nm.rsplit(".", 1)[0]
    for base in (nm, "card_male_{}".format(nm)):
        for ext in (".png", ".jpg", ".jpeg"):
            p = os.path.join(DATA_DIR, base + ext)
            if os.path.isfile(p): return p
    return None
def get_excards(uid):
    try: return json.loads(get_setting(0, "excards_{}".format(uid), "[]") or "[]")
    except: return []
def set_excards(uid, lst): set_setting(0, "excards_{}".format(uid), json.dumps(lst, ensure_ascii=False))
def grant_excard(uid, name, apply=True):
    lst = get_excards(uid)
    if name not in lst: lst.append(name); set_excards(uid, lst)
    if apply: set_design(uid, exclusive=name)
def revoke_excard(uid, name):
    lst = [x for x in get_excards(uid) if x != name]; set_excards(uid, lst)
    d = get_design(uid)
    if d.get("exclusive") == name: set_design(uid, exclusive="")

# ===== КАРТОЧКА =====
def get_card(user_id):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM player_cards WHERE user_id=?", (user_id,)).fetchone()
        if row:
            d = dict(row); d.setdefault("design", "{}"); d.setdefault("verified", 0); return d
    return {"user_id": user_id, "name": "", "businesses": "[]", "realty": "[]", "property_val": "", "garage": "", "phone": "", "updated_at": 0, "design": "{}", "verified": 0}
def set_card_field(user_id, **kw):
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO player_cards(user_id) VALUES(?)", (user_id,))
        for k, v in kw.items(): CONN.execute("UPDATE player_cards SET {}=? WHERE user_id=?".format(k), (v, user_id))
        if set(kw.keys()) & CARD_DATA_KEYS: CONN.execute("UPDATE player_cards SET verified=0 WHERE user_id=?", (user_id,))
        CONN.execute("UPDATE player_cards SET updated_at=? WHERE user_id=?", (int(time.time()), user_id))
        CONN.commit()
def get_design(user_id):
    try: return json.loads(get_card(user_id).get("design") or "{}")
    except: return {}
def set_design(user_id, **kw):
    design = get_design(user_id); design.update(kw)
    set_card_field(user_id, design=json.dumps(design, ensure_ascii=False))
def get_pos(user_id, field):
    d = get_design(user_id); p = (d.get("pos") or {}).get(field) or [0.0, 0.0]
    try: return float(p[0]), float(p[1])
    except: return 0.0, 0.0
def set_pos(user_id, field, dx, dy):
    d = get_design(user_id); pos = d.get("pos") or {}; pos[field] = [round(dx, 5), round(dy, 5)]; d["pos"] = pos
    set_card_field(user_id, design=json.dumps(d, ensure_ascii=False))
def pos_adjust_text(user_id, f):
    dx, dy = get_pos(user_id, f)
    return "🎯 Положение «{}»:\nСмещение X: {:+.4f} | Y: {:+.4f}\nКаждое нажатие сдвигает текст на маленький шаг.".format(POS_FIELDS.get(f, f), dx, dy)
def clear_card_data(user_id):
    set_card_field(user_id, name="", businesses="[]", realty="[]", property_val="", garage="", phone="")
    set_design(user_id, photo="")

def format_businesses(blist): return " | ".join("{} #{}".format(b["t"], b["n"]) if b.get("n") else b["t"] for b in blist)
def format_realty(rlist): return " | ".join("{} #{}".format(r["t"], r["n"]) for r in rlist)
def format_property(val):
    if not val: return "Неизвестно"
    return "{:,}".format(int(val)).replace(",", ".")
def format_phone(phone):
    if not phone: return "Неизвестно"
    return "-".join([phone[i:i+2] for i in range(0, len(phone), 2)])

def bus_slots_info(blist):
    types = [b["t"] for b in blist]; has_azs = "АЗС" in types
    slot2 = next((t for t in types if t in BUS_SLOT2), None)
    others = [t for t in types if t != "АЗС" and t not in BUS_SLOT2]
    has_tako = (slot2 == BUS_TAKO); used_other = len(others) + (1 if has_tako else 0)
    return has_azs, slot2, others, has_tako, used_other
def can_add_business(blist, biz_type):
    has_azs, slot2, others, has_tako, used_other = bus_slots_info(blist)
    if biz_type == "АЗС": return (True, "replace") if has_azs else (True, "add")
    if biz_type in BUS_SLOT2:
        if slot2 == biz_type:
            if biz_type in BUS_NO_NUM: return False, "exists"
            return True, "replace"
    if biz_type == BUS_TAKO:
        if len(others) + 1 > 2: return False, "full"
        return True, "add"
    count_same = others.count(biz_type)
    if count_same >= 2: return False, "max2"
    if used_other >= 2: return False, "full"
    return True, "add"
def add_business(user_id, biz_type, num=None):
    card = get_card(user_id); blist = json.loads(card["businesses"] or "[]")
    if biz_type == "АЗС":
        for b in blist:
            if b["t"] == biz_type: b["n"] = num
        set_card_field(user_id, businesses=json.dumps(blist, ensure_ascii=False)); return
    if biz_type in BUS_SLOT2:
        same = [b for b in blist if b["t"] == biz_type]
        if same: same[0]["n"] = num; set_card_field(user_id, businesses=json.dumps(blist, ensure_ascii=False)); return
        blist = [b for b in blist if b["t"] not in BUS_SLOT2]
    entry = {"t": biz_type}
    if num: entry["n"] = num
    blist.append(entry); set_card_field(user_id, businesses=json.dumps(blist, ensure_ascii=False))
def add_realty(user_id, realty_type, num):
    card = get_card(user_id); rlist = json.loads(card["realty"] or "[]")
    rlist.append({"t": realty_type, "n": num}); set_card_field(user_id, realty=json.dumps(rlist, ensure_ascii=False))

def get_card_state(user_id, peer_id):
    with DB_LOCK:
        row = CONN.execute("SELECT step, context FROM card_edit_state WHERE user_id=? AND peer_id=?", (user_id, peer_id)).fetchone()
        if row: return {"step": row["step"], "context": json.loads(row["context"]) if row["context"] else {}}
    return None
def set_card_state(user_id, peer_id, step, context=None):
    if context is None: context = {}
    context["ts"] = int(time.time())
    with DB_LOCK:
        CONN.execute("INSERT OR REPLACE INTO card_edit_state(user_id, peer_id, step, context) VALUES(?,?,?,?)", (user_id, peer_id, step, json.dumps(context, ensure_ascii=False)))
        CONN.commit()
def clear_card_state(user_id, peer_id):
    with DB_LOCK: CONN.execute("DELETE FROM card_edit_state WHERE user_id=? AND peer_id=?", (user_id, peer_id)); CONN.commit()

def resolve_cmid_retry(peer, sent_id, tries=3):
    for i in range(tries):
        try:
            resp = VK.messages.getById(message_ids=[sent_id]); items = resp.get("items", [])
            if items:
                cm = items[0].get("conversation_message_id")
                if cm: return int(cm)
        except: pass
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
        try: VK.messages.delete(peer_id=peer, **a); send_msg(peer, txt); return True
        except: continue
    edits = []
    if cm: edits.append({"conversation_message_id": cm})
    if mid: edits.append({"message_id": mid})
    if cm: edits.append({"message_id": cm})
    if mid: edits.append({"conversation_message_id": mid})
    for kw in edits:
        try: VK.messages.edit(peer_id=peer, message=txt, keyboard=json.dumps({"inline": True, "buttons": []}), **kw); return True
        except: continue
    print("card close FAIL peer={} ctx={}".format(peer, ctx)); send_msg(peer, txt); return False

def delete_user_msg(peer, cmid, mid=None):
    if cmid:
        try: VK.messages.delete(peer_id=peer, conversation_message_ids=[cmid], delete_for_all=1); return
        except Exception as e: print("delete_user_msg conv fail peer={} cmid={} err={}".format(peer, cmid, e))
    if mid:
        try: VK.messages.delete(peer_id=peer, message_ids=[mid], delete_for_all=1); return
        except Exception as e: print("delete_user_msg mid fail peer={} mid={} err={}".format(peer, mid, e))

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
            except: pass
            path = os.path.join(PHOTO_DIR, "{}.jpg".format(user_id))
            with open(path, "wb") as f: f.write(data)
            return True
    except Exception as e: print("save_design_photo error:", e); return False

# ===== ХЕЛПЕРЫ АВТОЗАКРЫТИЯ РЕДАКТОРОВ =====
def _silent_delete_msg(peer, cmid=None, mid=None):
    for kw in (({"conversation_message_ids": [cmid]} if cmid else None), ({"message_ids": [mid]} if mid else None)):
        if not kw: continue
        try: VK.messages.delete(peer_id=peer, delete_for_all=1, **kw); return True
        except: continue
    return False

def _silent_edit_msg(peer, text, cmid=None, mid=None):
    kb = json.dumps({"inline": True, "buttons": []})
    for kw in (({"conversation_message_id": cmid} if cmid else None), ({"message_id": mid} if mid else None)):
        if not kw: continue
        try: VK.messages.edit(peer_id=peer, message=text, keyboard=kb, **kw); return True
        except: continue
    return False

def close_existing_editors(peer, sender):
    """Тихо закрывает все активные редакторы (карта + аукцион/промо/войс), удаляя их сообщения."""
    try:
        cs = get_card_state(sender, peer)
        if cs:
            ctx = cs.get("context", {}) or {}
            _silent_delete_msg(peer, ctx.get("msg_cmid"), ctx.get("msg_id"))
            clear_card_state(sender, peer)
    except Exception as e: print("close card editor err:", e)
    try:
        ast = get_auction_state(sender, peer)
        if ast:
            actx = ast.get("context", {}) or {}
            _silent_delete_msg(peer, actx.get("msg_cmid"), actx.get("msg_id"))
            clear_auction_state(sender, peer)
    except Exception as e: print("close auction editor err:", e)
# ============================================

def handle_card_input(sender, peer, text, cmid=None, attachments=None):
    state = get_card_state(sender, peer)
    if not state: return False
    step = state["step"]; ctx = state.get("context", {})
    prompt_cmid = ctx.get("msg_cmid") or cmid
    if time.time() - ctx.get("ts", 0) > 60:
        clear_card_state(sender, peer)
        close_card_session(peer, ctx, "Время на редактирование вышло, {} вы бездействовали минуту⏳".format(mention(sender)))
        return True
    
    def reply(msg):
        if prompt_cmid:
            try: VK.messages.edit(peer_id=peer, conversation_message_id=prompt_cmid, message=msg, keyboard=json.dumps({"inline": True, "buttons": []})); return
            except: pass
        send_msg(peer, msg)
    def reply_kb(msg, back_payload, menu_step, menu_ctx=None):
        kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps(back_payload)}, "color": "primary"}, {"action": {"type": "callback", "label": "✅ Готово", "payload": json.dumps({"cmd": "card_finish"})}, "color": "positive"}]]}
        c = dict(menu_ctx or {}); c["msg_cmid"] = prompt_cmid; set_card_state(sender, peer, menu_step, c)
        if prompt_cmid:
            try: VK.messages.edit(peer_id=peer, conversation_message_id=prompt_cmid, message=msg, keyboard=json.dumps(kb)); return
            except: pass
        send_msg(peer, msg, keyboard=kb)

    if text.lower() in ["отмена", "отменить"]:
        clear_card_state(sender, peer); reply("❌ Редактирование отменено."); return True

    # --- Обработка ввода своего цвета ---
    if step == "custom_color_input":
        target = ctx.get("target")
        if text.lower() in ["отмена", "отменить"]:
            clear_card_state(sender, peer); reply("❌ Отменено."); return True
        rgb = parse_custom_color(text)
        if not rgb:
            reply("❌ Неверный формат. Примеры: #FF0000 или 255,0,0"); return True
        set_design(sender, **{target: list(rgb)})
        clear_card_state(sender, peer)
        reply_kb(f"✅ Цвет для {target} установлен!", {"cmd": "card_custom_color_menu"}, "edit_menu", {"p": 2})
        return True

    if step == "design_photo_wait":
        if get_design(sender).get("exclusive"):
            reply("❌ Сначала снимите эксклюзивную карту, чтобы менять фото."); return True
        if text.strip().lower() in ["дефолт", "default"]:
            set_design(sender, photo=""); reply_kb("✅ Возвращена дефолтная фотография карточки.", {"cmd": "card_edit_menu", "p": 2}, "edit_menu", {"p": 2}); return True
        url = extract_photo_url({"attachments": attachments}) if attachments else None
        if not url:
            reply("❌ Прикрепи фото к сообщению (или напиши «дефолт»)."); return True
        if save_design_photo(sender, url):
            set_design(sender, photo="custom"); reply_kb("✅ Твоя фотография установлена на карточку!", {"cmd": "card_edit_menu", "p": 2}, "edit_menu", {"p": 2})
        else:
            reply("❌ Не удалось скачать фото, попробуй другое.")
        return True

    if step == "biz_input":
        biz_type = ctx.get("t", "")
        if not re.match(r"^[1-9]\d{0,2}$", text.strip()): reply("❌ Неверный номер: максимум 3 цифры, без нуля в начале."); return True
        card = get_card(sender); blist = json.loads(card["businesses"] or "[]")
        ok, mode = can_add_business(blist, biz_type)
        if not ok: reply("❌ Нет свободных слотов под этот бизнес."); return True
        add_business(sender, biz_type, text.strip())
        p = ctx.get("p", 1); reply_kb("✅ Бизнес {} #{} успешно добавлен!".format(biz_type, text.strip()), {"cmd": "card_bus_menu", "p": p}, "bus_menu", {"p": p}); return True

    if step == "realty_input":
        realty_type = ctx.get("t", "")
        if not re.match(r"^[1-9]\d{0,3}$", text.strip()): reply("❌ Неверный номер: максимум 4 цифры."); return True
        add_realty(sender, realty_type, text.strip())
        reply_kb("✅ Недвижимость {} #{} успешно добавлена!".format(realty_type, text.strip()), {"cmd": "card_realty_menu"}, "realty_menu"); return True

    if step == "garage_input":
        if not re.match(r"^[1-9]\d{0,3}$", text.strip()): reply("❌ Неверный номер гаража."); return True
        set_card_field(sender, garage=text.strip())
        reply_kb("✅ Гараж #{} успешно добавлен!".format(text.strip()), {"cmd": "card_edit_menu", "p": 1}, "edit_menu", {"p": 1}); return True

    if step == "phone_input":
        if not re.match(r"^[1-9]\d{3,6}$", text.strip()): reply("❌ Неверный телефон: 4–7 цифр."); return True
        set_card_field(sender, phone=text.strip())
        reply_kb("✅ Телефон {} успешно добавлен!".format(format_phone(text.strip())), {"cmd": "card_edit_menu", "p": 1}, "edit_menu", {"p": 1}); return True

    if step == "name_input":
        if not re.match(r"^[A-Za-z]{1,15}_[A-Za-z]{1,15}$", text.strip()): reply("❌ Неверный формат: Имя_Фамилия, только английские буквы."); return True
        set_card_field(sender, name=text.strip())
        reply_kb("✅ Имя {} успешно установлено!".format(text.strip()), {"cmd": "card_edit_menu", "p": 1}, "edit_menu", {"p": 1}); return True

    if step == "property_input":
        if not re.match(r"^\d+$", text.strip()): reply("❌ Введите сумму цифрами."); return True
        set_card_field(sender, property_val=text.strip())
        reply_kb("✅ Имущество оценено в {}!".format(format_property(text.strip())), {"cmd": "card_edit_menu", "p": 1}, "edit_menu", {"p": 1}); return True
    return False

# ===== АУКЦИОНЫ: ДАННЫЕ =====
def get_auction_state(user_id, peer_id):
    with DB_LOCK:
        row = CONN.execute("SELECT step, context FROM auction_state WHERE user_id=? AND peer_id=?", (user_id, peer_id)).fetchone()
        if row: return {"step": row["step"], "context": json.loads(row["context"]) if row["context"] else {}}
    return None
def set_auction_state(user_id, peer_id, step, context=None):
    if context is None: context = {}
    context["ts"] = int(time.time())
    with DB_LOCK:
        CONN.execute("INSERT OR REPLACE INTO auction_state(user_id, peer_id, step, context) VALUES(?,?,?,?)", (user_id, peer_id, step, json.dumps(context, ensure_ascii=False)))
        CONN.commit()
def clear_auction_state(user_id, peer_id):
    with DB_LOCK: CONN.execute("DELETE FROM auction_state WHERE user_id=? AND peer_id=?", (user_id, peer_id)); CONN.commit()

def parse_auction_dt(s):
    for fmt in ("%d.%m.%y %H:%M", "%d.%m.%Y %H:%M"):
        try: dt = datetime.datetime.strptime(s.strip(), fmt); return dt.replace(tzinfo=MSK_TZ)
        except: continue
    return None
def fmt_rub(amount):
    n = int(round(amount)); return "{:,}р".format(n).replace(",", ".")
def min_step_m(m):
    if m < 50: return 1
    if m < 100: return 3
    if m < 200: return 5
    if m < 400: return 7
    if m < 1000: return 15
    return 30
def parse_money(text):
    s = (text or " ").strip().replace("  ", " ").replace("\u00a0", " ")
    if not s: return None
    if "," in s:
        if re.match(r"^\d+,\d{1,2}$", s):
            v = float(s.replace(",", "."))
            if 1 <= v < 1000: return v * 1000000.0
            return None
    if re.match(r"^\d{1,3}(\.\d{3})+$", s): return float(int(s.replace(".", "")))
    if re.match(r"^\d+$", s):
        n = int(s)
        if n >= 1000000: return float(n)
        if 1 <= n <= 999: return n * 1000000.0
        return float(n)
    if re.match(r"^\d+\.\d{1,2}$", s):
        v = float(s)
        if 1 <= v < 1000: return v * 1000000.0
        if v >= 1000000: return v
        return None
    return None
def parse_bid(text): return parse_money(text)

def create_auction(peer_id, name, datetime_str, created_by):
    with DB_LOCK:
        cur = CONN.execute("INSERT INTO auctions(peer_id, name, datetime_str, created_by, created_at, state) VALUES(?,?,?,?,?,'scheduled')", (peer_id, name, datetime_str, created_by, int(time.time())))
        aid = cur.lastrowid; CONN.commit(); return aid
def get_auction(auction_id):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM auctions WHERE id=?", (auction_id,)).fetchone()
        return dict(row) if row else None
def get_auctions_for_peer(peer_id):
    with DB_LOCK:
        rows = CONN.execute("SELECT * FROM auctions WHERE peer_id=? AND state IN ('scheduled','running') ORDER BY id", (peer_id,)).fetchall()
        return [dict(r) for r in rows]
def get_running_auction(peer_id):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM auctions WHERE peer_id=? AND state='running'", (peer_id,)).fetchone()
        return dict(row) if row else None
def delete_auction(auction_id):
    with DB_LOCK:
        CONN.execute("DELETE FROM auction_bids WHERE lot_id IN (SELECT id FROM auction_lots WHERE auction_id=?)", (auction_id,))
        CONN.execute("DELETE FROM auction_lots WHERE auction_id=?", (auction_id,))
        CONN.execute("DELETE FROM auctions WHERE id=?", (auction_id,)); CONN.commit()
def add_lot(auction_id, num, name, min_price, seller, photo_path, photo_att):
    with DB_LOCK:
        CONN.execute("INSERT INTO auction_lots(auction_id, lot_number, name, min_price, seller, photo_path, photo_att) VALUES(?,?,?,?,?,?,?)", (auction_id, num, name, min_price, seller, photo_path, photo_att))
        CONN.commit()
def get_lots(auction_id):
    with DB_LOCK:
        rows = CONN.execute("SELECT * FROM auction_lots WHERE auction_id=? ORDER BY lot_number", (auction_id,)).fetchall()
        return [dict(r) for r in rows]
def get_lot(lot_id):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM auction_lots WHERE id=?", (lot_id,)).fetchone()
        return dict(row) if row else None
def delete_lot(lot_id):
    with DB_LOCK:
        CONN.execute("DELETE FROM auction_bids WHERE lot_id=?", (lot_id,))
        CONN.execute("DELETE FROM auction_lots WHERE id=?", (lot_id,)); CONN.commit()
def get_best_bid(lot_id):
    with DB_LOCK:
        row = CONN.execute("SELECT id, user_id, amount FROM auction_bids WHERE lot_id=? ORDER BY amount DESC LIMIT 1", (lot_id,)).fetchone()
        if row: return row["id"], row["user_id"], row["amount"]
    return None, None, None
def add_bid(lot_id, user_id, amount):
    with DB_LOCK:
        CONN.execute("INSERT INTO auction_bids(lot_id, user_id, amount, bid_time) VALUES(?,?,?,?)", (lot_id, user_id, amount, int(time.time())))
        CONN.commit()
def delete_bid(bid_id):
    with DB_LOCK: CONN.execute("DELETE FROM auction_bids WHERE id=?", (bid_id,)); CONN.commit()

def save_auction_photo_file(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MD BOT)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            if len(data) < 1000: return None
            try: os.makedirs(AUCTION_PHOTO_DIR, exist_ok=True)
            except: pass
            path = os.path.join(AUCTION_PHOTO_DIR, "lot_{}.jpg".format(int(time.time() * 1000)))
            with open(path, "wb") as f: f.write(data); return path
    except Exception as e: print("save_auction_photo_file error:", e); return None
def upload_photo_file(peer, path):
    try:
        with open(path, "rb") as f: raw = f.read()
        server = VK.photos.getMessagesUploadServer(peer_id=peer)
        resp = requests.post(server["upload_url"], files={"photo": ("lot.jpg", raw, "image/jpeg")}, timeout=30)
        data = resp.json()
        if not data.get("photo"): return None
        saved = VK.photos.saveMessagesPhoto(photo=data["photo"], hash=data["hash"], server=data["server"])
        if not saved: return None
        return "photo{}_{}".format(saved[0]["owner_id"], saved[0]["id"])
    except Exception as e: print("upload_photo_file error:", e); return None

def auction_main_kb():
    return {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "Активные", "payload": json.dumps({"cmd": "auction_active"})}, "color": "primary"}, {"action": {"type": "callback", "label": "Создать", "payload": json.dumps({"cmd": "auction_create"})}, "color": "positive"}],
        [{"action": {"type": "callback", "label": "Удалить", "payload": json.dumps({"cmd": "auction_delete"})}, "color": "negative"}, {"action": {"type": "callback", "label": "Редактировать", "payload": json.dumps({"cmd": "auction_edit"})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Анонс", "payload": json.dumps({"cmd": "auction_announce"})}, "color": "positive"}, {"action": {"type": "callback", "label": "Контроль", "payload": json.dumps({"cmd": "auction_control"})}, "color": "secondary"}],
        [{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "auction_cancel"})}, "color": "negative"}]]}
def auction_step_kb(back_to, with_skip=False):
    rows = []
    if with_skip: rows.append([{"action": {"type": "callback", "label": "Пропустить", "payload": json.dumps({"cmd": "auction_skip_photo"})}, "color": "secondary"}])
    rows.append([{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "auction_back", "to": back_to})}, "color": "primary"}, {"action": {"type": "callback", "label": "❌ Отмена", "payload": json.dumps({"cmd": "auction_cancel"})}, "color": "negative"}])
    return {"inline": True, "buttons": rows}
def auction_list_kb(auctions, cmd):
    rows = []; line = []
    for i, a in enumerate(auctions[:8]):
        lab = NUM_EMOJI[i] if i < len(NUM_EMOJI) else str(i + 1)
        line.append({"action": {"type": "callback", "label": lab, "payload": json.dumps({"cmd": cmd, "id": a["id"]})}, "color": "secondary"})
        if len(line) == 4: rows.append(line); line = []
    if line: rows.append(line)
    rows.append([{"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "auction_menu_show"})}, "color": "primary"}, {"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "auction_cancel"})}, "color": "negative"}])
    return {"inline": True, "buttons": rows}
def auction_lots_kb(lots, back_cmd, back_id=None):
    rows = []; line = []
    for i, l in enumerate(lots[:8]):
        lab = NUM_EMOJI[i] if i < len(NUM_EMOJI) else str(i + 1)
        line.append({"action": {"type": "callback", "label": lab, "payload": json.dumps({"cmd": "auction_lotphoto", "id": l["id"]})}, "color": "secondary"})
        if len(line) == 4: rows.append(line); line = []
    if line: rows.append(line)
    pay = {"cmd": back_cmd}
    if back_id: pay["id"] = back_id
    rows.append([{"action": {"type": "callback", "label": "Назад", "payload": json.dumps(pay)}, "color": "primary"}, {"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "auction_cancel"})}, "color": "negative"}])
    return {"inline": True, "buttons": rows}
def edit_menu_kb(aid):
    return {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "Дата и время", "payload": json.dumps({"cmd": "auction_edit_dt", "id": aid})}, "color": "primary"}, {"action": {"type": "callback", "label": "Название аукциона", "payload": json.dumps({"cmd": "auction_edit_name", "id": aid})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Лот", "payload": json.dumps({"cmd": "auction_edit_lot", "id": aid})}, "color": "primary"}, {"action": {"type": "callback", "label": "Добавить лот", "payload": json.dumps({"cmd": "auction_add_lot", "id": aid})}, "color": "positive"}],
        [{"action": {"type": "callback", "label": "Удалить аукцион", "payload": json.dumps({"cmd": "auction_del_auction", "id": aid})}, "color": "negative"}, {"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "auction_menu_show"})}, "color": "secondary"}]]}
def edit_menu_text(a):
    lots = get_lots(a["id"])
    lines = ["{} | {}".format(a["datetime_str"].replace(" ", " | "), a["name"]), "Лоты: "]
    for i, l in enumerate(lots, 1):
        seller = l.get("seller") or "не указан"
        lines.append("{}. {} (мин. {}, продавец: {})".format(i, l["name"], fmt_rub(l["min_price"]), seller))
    return "\n".join(lines)

LOT_PRICE_HINT = "цена: 300 = 300.000.000р, 99.5 = 99.500.000р, или полная сумма (300.000.000 / 300000000); свыше 1 млрд — только полной суммой"
AUCTION_STEPS = set(["create_peer","create_name","create_dt","create_count","create_lot","create_photo","delete_peer","edit_peer","edit_dt","edit_name","edit_lot_num","edit_lot_data","edit_lot_photo","add_lot_data","add_lot_photo","announce_peer","active_peer","control_peer","cancel_last_peer"])
def auction_prompt(step, ctx):
    lots = ctx.get("lots") or []
    if step == "create_peer": return "Введите номер чата для аукциона: ", auction_step_kb("menu")
    if step == "create_name": return "Введите название аукциона: ", auction_step_kb("create_peer")
    if step == "create_dt": return "Введите дату и время проведения (пример: 03.02.26 13:44): ", auction_step_kb("create_name")
    if step == "create_count": return "Сколько лотов желаете добавить? ", auction_step_kb("create_dt")
    if step == "create_lot":
        back = "create_count" if not lots else "create_photo"
        return "Введите лот {}, его минимальную цену, ссылку на продавца через запятую ({}): ".format(len(lots) + 1, LOT_PRICE_HINT), auction_step_kb(back)
    if step == "create_photo": return "Прикрепите фото лота {} (или нажмите «Пропустить»): ".format(len(lots)), auction_step_kb("create_lot_pop", with_skip=True)
    if step == "delete_peer": return "Введите номер чата, где удалить аукцион: ", auction_step_kb("menu")
    if step == "edit_peer": return "Введите номер чата, где редактировать аукцион: ", auction_step_kb("menu")
    if step == "edit_dt": return "Введите новые дату и время (пример: 04.06.26 15:00): ", auction_step_kb("edit_menu_show")
    if step == "edit_name": return "Введите новое название аукциона: ", auction_step_kb("edit_menu_show")
    if step == "edit_lot_num": return "Введите номер лота (число): ", auction_step_kb("edit_menu_show")
    if step == "edit_lot_data": return "Введите новые данные лота (название, мин. цена, ссылка на продавца через запятую; {}): ".format(LOT_PRICE_HINT), auction_step_kb("edit_lot_num")
    if step == "edit_lot_photo": return "Прикрепите новое фото лота (или «Пропустить» — останется старое): ", auction_step_kb("edit_lot_data", with_skip=True)
    if step == "add_lot_data": return "Введите новый лот: название, мин. цена, ссылка на продавца через запятую ({}): ".format(LOT_PRICE_HINT), auction_step_kb("edit_menu_show")
    if step == "add_lot_photo": return "Прикрепите фото нового лота (или «Пропустить»): ", auction_step_kb("add_lot_data", with_skip=True)
    if step == "announce_peer": return "Введите номер чата, куда сделать анонс: ", auction_step_kb("menu")
    if step == "active_peer": return "Введите номер чата, где посмотреть аукционы: ", auction_step_kb("menu")
    if step == "control_peer": return "Введите номер чата для настройки контроля: ", auction_step_kb("menu")
    if step == "cancel_last_peer": return "Введите номер чата, где отменить последнюю ставку: ", auction_step_kb("menu")
    return "Выберите действие: ", auction_main_kb()

def send_lot_message(peer, auction, lot):
    att = lot.get("photo_att") or ""
    if not att and lot.get("photo_path") and os.path.isfile(lot["photo_path"]):
        att = upload_photo_file(peer, lot["photo_path"]) or ""
    if att:
        with DB_LOCK: CONN.execute("UPDATE auction_lots SET photo_att=? WHERE id=?", (att, lot["id"])); CONN.commit()
    seller = lot.get("seller") or silent_mention_badge(auction["created_by"], peer)
    txt = ("@all\n🏆 ЛОТ НА АУКЦИОН 🏆\n🟦 Black Russia • BLUE 🟦\n\n━━━━━━━━━━━━━━━━━━━━\n\n📦 Наименование лота:\n{}\n\n💰 Стартовая цена:\n➡️ 20.000.000 рублей\n\n👤 Продавец:\n➡️ {}\n\n━━━━━━━━━━━━━━━━━━━━\n\n🔥 Лот выставлен! Ждём ставок! 🔥\n\n━━━━━━━━━━━━━━━━━━━━").format(lot["name"], seller)
    send_msg(peer, txt, attachments=att or None)

def start_lot(auction, idx):
    lots = get_lots(auction["id"])
    if idx >= len(lots): finish_auction_summary(auction["peer_id"], auction); return
    lot = lots[idx]; now_ts = int(time.time())
    with DB_LOCK:
        CONN.execute("UPDATE auctions SET current_lot_index=?, current_lot_id=?, lot_deadline=? WHERE id=?", (idx, lot["id"], now_ts + 300, auction["id"]))
        CONN.commit()
    set_setting(0, "auc_rem_{}".format(lot["id"]), str(now_ts))
    send_lot_message(auction["peer_id"], auction, lot)

def finish_lot(auction, lot):
    peer = auction["peer_id"]; bid_id, uid, amt = get_best_bid(lot["id"])
    if uid is None:
        send_msg(peer, "Лот «{}» не продан! Никто не поставил ставку.".format(lot["name"])); sold, w, fp = 0, 0, 0.0
    elif amt < lot["min_price"]:
        send_msg(peer, "Лот «{}» не продан! Цена не достигла минимальной. Последняя ставка была - {}.".format(lot["name"], fmt_rub(amt))); sold, w, fp = 0, 0, amt
    else:
        send_msg(peer, "Лот «{}» продан за {} {}. Поздравим победителя!".format(lot["name"], fmt_rub(amt), silent_mention_badge(uid, peer))); sold, w, fp = 1, uid, amt
    with DB_LOCK:
        CONN.execute("UPDATE auction_lots SET sold=?, winner_id=?, final_price=? WHERE id=?", (sold, w, fp, lot["id"])); CONN.commit()
    start_lot(auction, (auction["current_lot_index"] or 0) + 1)

def finish_auction_summary(peer, auction):
    lots = get_lots(auction["id"]); sold = [l for l in lots if l.get("sold")]
    lines = ["😉Спасибо всем за участие в аукционе! "]
    if sold:
        lines.append(" "); lines.append("Проданные лоты сегодня: ")
        for i, l in enumerate(sold, 1):
            seller = l.get("seller") or silent_mention_badge(auction["created_by"], peer)
            lines.append("{}) | Лот: {} | Продавец: {} | Покупатель: {} | {} |".format(i, l["name"], seller, silent_mention_badge(l["winner_id"], peer), fmt_rub(l["final_price"] or 0)))
        lines.append(" "); lines.append("ℹ️Если желаете поставить свой лот на следующий аукцион напишите в личные сообщения аукционеру.")
    send_msg(peer, "\n".join(lines))
    with DB_LOCK:
        CONN.execute("UPDATE auctions SET state='finished', current_lot_id=0, lot_deadline=0 WHERE id=?", (auction["id"],)); CONN.commit()

def open_auction_menu(peer, sender):
    close_existing_editors(peer, sender)
    try:
        msg_id = VK.messages.send(peer_id=peer, message="Выберите действие:", keyboard=json.dumps(auction_main_kb()), random_id=random.getrandbits(31))
        cmid = resolve_cmid_retry(peer, msg_id)
    except: msg_id = None; cmid = None
    set_auction_state(sender, peer, "menu", {"msg_cmid": cmid, "msg_id": msg_id})

def parse_lot_line(text):
    parts = text.rsplit(",", 2)
    if len(parts) == 3: name, price_s, seller = [p.strip() for p in parts]
    elif len(parts) == 2: name, price_s = [p.strip() for p in parts]; seller = ""
    else: return None
    min_price = parse_money(price_s)
    if not name or not min_price or min_price <= 0: return None
    return name, min_price, seller

def handle_stop_auction(peer, sender, raw):
    m = re.search(r"(2\d{9})", raw)
    if not m: send_msg(peer, "❌ Формат: /стопаукцион (номер чата)"); return
    pid = int(m.group(1))
    with DB_LOCK:
        rows = CONN.execute("SELECT id FROM auctions WHERE peer_id=? AND state IN ('scheduled','running')", (pid,)).fetchall()
        if rows: CONN.execute("UPDATE auctions SET state='stopped', current_lot_id=0, lot_deadline=0 WHERE peer_id=? AND state IN ('scheduled','running')", (pid,)); CONN.commit()
    if not rows: send_msg(peer, "❌ В этом чате нет активных аукционов."); return
    send_msg(peer, "✅ Аукцион(ы) в чате {} остановлены.".format(pid))
    send_msg(pid, "⛔ Аукцион принудительно остановлен аукционером.")

def handle_cancel_last_bid(peer, sender, raw):
    m = re.search(r"(2\d{9})", raw)
    if not m:
        set_auction_state(sender, peer, "cancel_last_peer", {}); txt, kb = auction_prompt("cancel_last_peer", {}); send_msg(peer, txt, keyboard=kb); return
    do_cancel_last_bid(peer, int(m.group(1)))
def do_cancel_last_bid(peer, pid):
    ra = get_running_auction(pid)
    if not ra or not ra["current_lot_id"]: send_msg(peer, "❌ В чате {} сейчас нет идущего аукциона с активным лотом.".format(pid)); return
    lot = get_lot(ra["current_lot_id"]); bid_id, uid, amt = get_best_bid(lot["id"])
    if bid_id is None: send_msg(peer, "❌ На лот «{}» ещё нет ставок.".format(lot["name"])); return
    delete_bid(bid_id); nid, nuid, namt = get_best_bid(lot["id"])
    info = "Теперь лучшая ставка: {} от {}.".format(fmt_rub(namt), silent_mention_badge(nuid, peer)) if nuid else "Теперь ставок нет."
    send_msg(peer, "✅ Верхняя ставка {} ({}) на лот «{}» отменена. {}".format(fmt_rub(amt), silent_mention_badge(uid, peer), lot["name"], info))
    send_msg(pid, "⚠️ Последняя ставка на лот «{}» отменена аукционером. {}".format(lot["name"], info))

def handle_next_lot(peer, sender, raw):
    m = re.search(r"(2\d{9})", raw)
    if not m: send_msg(peer, "❌ Формат: /некст лот (номер чата)"); return
    do_next_lot(peer, int(m.group(1)))
def do_next_lot(peer, pid):
    ra = get_running_auction(pid)
    if not ra or not ra["current_lot_id"]: send_msg(peer, "❌ В чате {} сейчас нет идущего аукциона с активным лотом.".format(pid)); return
    lot = get_lot(ra["current_lot_id"])
    if not lot: send_msg(peer, "❌ Активный лот не найден."); return
    bid_id, uid, amt = get_best_bid(lot["id"])
    if uid is None:
        with DB_LOCK: CONN.execute("UPDATE auction_lots SET sold=0, winner_id=0, final_price=0 WHERE id=?", (lot["id"],)); CONN.commit()
        send_msg(pid, "⏭️ Лот «{}» завершён аукционером: ставок не было.".format(lot["name"]))
    elif amt < lot["min_price"]:
        with DB_LOCK: CONN.execute("UPDATE auction_lots SET sold=0, winner_id=0, final_price=? WHERE id=?", (amt, lot["id"])); CONN.commit()
        send_msg(pid, "⏭️ Лот «{}» не продан (завершено аукционером): цена не достигла минимальной. Последняя ставка - {}.".format(lot["name"], fmt_rub(amt)))
    else:
        with DB_LOCK: CONN.execute("UPDATE auction_lots SET sold=1, winner_id=?, final_price=? WHERE id=?", (uid, amt, lot["id"])); CONN.commit()
        send_msg(pid, "⏭️ Лот «{}» продан за {} {} (завершено аукционером).".format(lot["name"], fmt_rub(amt), silent_mention_badge(uid, pid)))
    send_msg(peer, "✅ Лот «{}» принудительно завершён.".format(lot["name"]))
    start_lot(ra, (ra["current_lot_index"] or 0) + 1)

def handle_auctioneer_cmd(peer, sender, raw):
    targets = extract_targets(raw, 0)
    if not targets: send_msg(peer, "❌ Формат: /аукционер @юзер (повторно — снять роль)"); return
    t = targets[0]
    if t in (CREATOR_ID, LEADER_ID): send_msg(peer, "❌ У создателя и лидера доступ есть всегда."); return
    key = "auctioneer_{}".format(t)
    if get_setting(0, key, "0") == "1":
        set_setting(0, key, "0"); send_msg(peer, "✅ С {} снята роль аукционера.".format(silent_mention_badge(t, peer))); send_msg(t, "📈 Вас сняли с роли аукционера. Скрытые команды аукциона больше недоступны.")
    else:
        set_setting(0, key, "1"); send_msg(peer, "✅ {} назначен аукционером.".format(silent_mention_badge(t, peer))); send_msg(t, AUCTIONEER_WELCOME)
def handle_list_auctioneers(peer):
    lst = get_all_auctioneers()
    if not lst: send_msg(peer, "📈 Аукционеров нет."); return
    lines = ["📈 Список аукционеров:\n"]
    for i, uid in enumerate(lst, 1): lines.append("{}. | {} |".format(i, silent_mention_badge(uid, peer)))
    send_msg(peer, "\n".join(lines))
def handle_list_inspectors(peer):
    lst = get_all_inspectors()
    if not lst: send_msg(peer, "📋 Проверяющих нет."); return
    lines = ["📋 Список проверяющих:\n"]
    for i, uid in enumerate(lst, 1): lines.append("{}. | {} |".format(i, silent_mention_badge(uid, peer)))
    send_msg(peer, "\n".join(lines))

AUCTIONEER_WELCOME = ("Вас назначили аукционером📈\nТеперь вы можете использовать скрытые команды (только в личке со мной❗).\n/аукцион - редактор аукционов.\n/стопаукцион (номер чата) - принудительно отключает идущий аукцион в чате.\n/отменить ласт ставку (номер чата) - отменить верхнюю ставку активного лота.\n/некст лот (номер чата) - завершить текущий лот и перейти к следующему.")
INSPECTOR_WELCOME = ("Вас назначили проверяющим📋\nТеперь вы можете использовать скрытые команды (в личке со мной❗ и в чатах❗).\n/verify @ - подтвердить карту.\n/deny @ - отменить подтверждение.\n/card @ - посмотреть карту любого.\n/clearcard @ [праметр] - очистить любую карту.\n\nпараметры: бизнесы, недвижимость, имущество, гараж, телефон, фото, имя.\n(если не указать то очистит все кроме цвета)")

def _close_voice_menu(peer, ctx, txt):
    cm = ctx.get("msg_cmid"); mid = ctx.get("msg_id")
    for kw in (({"conversation_message_id": cm} if cm else None), ({"message_id": mid} if mid else None)):
        if not kw: continue
        try: VK.messages.edit(peer_id=peer, message=txt, keyboard=json.dumps({"inline": True, "buttons": []}), **kw); return True
        except: continue
    send_msg(peer, txt); return False

def handle_auction_input(sender, peer, text, cmid=None, attachments=None):
    state = get_auction_state(sender, peer)
    if not state: return False
    step = state["step"]
    if step.startswith("promo_"): return False
    # --- Обработка ввода номера чата для /voice ---
    if step == "voice_wait_peer":
        if text.strip().lower() in ("отмена", "отменить"):
            ctx = state.get("context", {})
            clear_auction_state(sender, peer)
            _close_voice_menu(peer, ctx, "❌ Рассылка отменена.")
            return True
        m = re.fullmatch(r"(2\d{9})", text.strip())
        if not m: send_msg(peer, "❌ Неверный формат. Введите 10 цифр (2xxxxxxxxx)."); return True
        pid = int(m.group(1))
        if not chat_exists(pid): send_msg(peer, "❌ Бот не состоит в этом чате."); return True
        ctx = state.get("context", {})
        clear_auction_state(sender, peer)
        try:
            if ctx.get("reply_att"): send_msg(pid, ctx.get("reply_text", ""), attachments=ctx.get("reply_att"))
            else: send_msg(pid, ctx.get("reply_text", ""))
            _close_voice_menu(peer, ctx, f"✅ Сообщение успешно отправлено в чат {pid}")
        except Exception as e: send_msg(peer, f"❌ Ошибка отправки: {e}")
        return True
    # ----------------------------------------------------
    
    ctx = state.get("context", {}); prompt_cmid = ctx.get("msg_cmid") or cmid
    if time.time() - ctx.get("ts", 0) > 300:
        clear_auction_state(sender, peer); send_msg(peer, "⏰ Время редактора аукционов вышло (5 минут бездействия)."); return True
    def reply(msg, kb=None):
        if prompt_cmid:
            try: VK.messages.edit(peer_id=peer, conversation_message_id=prompt_cmid, message=msg, keyboard=json.dumps(kb) if kb else json.dumps({"inline": True, "buttons": []})); return
            except: pass
        send_msg(peer, msg, keyboard=kb)
    def ask(next_step):
        set_auction_state(sender, peer, next_step, ctx); txt, kb = auction_prompt(next_step, ctx); reply(txt, kb)
    def back_to_menu(msg):
        set_auction_state(sender, peer, "menu", {"msg_cmid": prompt_cmid}); reply(msg + "\n\nВыберите действие:", auction_main_kb())
    def need_chat(cur_step):
        if not re.match(r"^2\d{9}$", text.strip()):
            txt, kb = auction_prompt(cur_step, ctx); reply("❌ Введите номер чата цифрами (2xxxxxxxxx).\n\n" + txt, kb); return None
        pid = int(text.strip())
        if not chat_exists(pid):
            txt, kb = auction_prompt(cur_step, ctx); reply("❌ Такого чата нет: {} — бот не состоит в нём или он не существует.\n\n".format(pid) + txt, kb); return None
        return pid
    def finish_photo_step(photo_path, photo_att):
        mode = ctx.get("photo_mode", "create")
        if mode == "create":
            ctx["lots"][-1]["photo_path"] = photo_path or ""; ctx["lots"][-1]["photo_att"] = photo_att or ""
            if len(ctx["lots"]) < ctx["count"]: ask("create_lot")
            else:
                aid = create_auction(ctx["peer_id"], ctx["name"], ctx["dt"], sender)
                for i, l in enumerate(ctx["lots"], 1): add_lot(aid, i, l["name"], l["min_price"], l.get("seller", ""), l.get("photo_path", ""), l.get("photo_att", ""))
                back_to_menu("✅ Аукцион «{}» создан в чате {}! Лотов: {}.".format(ctx["name"], ctx["peer_id"], len(ctx["lots"])))
        elif mode == "add":
            lots = get_lots(ctx["auction_id"]); num = (max([l["lot_number"] for l in lots]) + 1) if lots else 1
            add_lot(ctx["auction_id"], num, ctx["add_name"], ctx["add_price"], ctx.get("add_seller", ""), photo_path or "", photo_att or "")
            a = get_auction(ctx["auction_id"]); set_auction_state(sender, peer, "edit_menu", {"auction_id": a["id"], "msg_cmid": prompt_cmid})
            reply("✅ Лот добавлен.\n\n" + edit_menu_text(a) + "\n\nВыберите что хотите отредактировать:", edit_menu_kb(a["id"]))
        elif mode == "editlot":
            if photo_path:
                with DB_LOCK: CONN.execute("UPDATE auction_lots SET name=?, min_price=?, seller=?, photo_path=?, photo_att=? WHERE id=?", (ctx["edit_name"], ctx["edit_price"], ctx.get("edit_seller", ""), photo_path, photo_att or "", ctx["lot_id"])); CONN.commit()
            else:
                with DB_LOCK: CONN.execute("UPDATE auction_lots SET name=?, min_price=?, seller=? WHERE id=?", (ctx["edit_name"], ctx["edit_price"], ctx.get("edit_seller", ""), ctx["lot_id"])); CONN.commit()
            a = get_auction(ctx["auction_id"]); set_auction_state(sender, peer, "edit_menu", {"auction_id": ctx["auction_id"], "msg_cmid": prompt_cmid})
            if a: reply("✅ Лот отредактирован.\n\n" + edit_menu_text(a) + "\n\nВыберите что хотите отредактировать:", edit_menu_kb(a["id"]))
            else: reply("✅ Лот отредактирован.\n\nВыберите действие:", auction_main_kb())

    if text.lower() in ["отмена", "отменить"]: clear_auction_state(sender, peer); reply("❌ Редактор аукционов закрыт."); return True
    if step == "create_peer":
        pid = need_chat("create_peer")
        if pid is None: return True
        ctx["peer_id"] = pid; ask("create_name"); return True
    if step == "create_name": ctx["name"] = text.strip(); ask("create_dt"); return True
    if step == "create_dt":
        dt = parse_auction_dt(text)
        if not dt: txt, kb = auction_prompt("create_dt", ctx); reply("❌ Неверный формат. Пример: 03.02.26 13:44\n\n" + txt, kb); return True
        ctx["dt"] = text.strip(); ask("create_count"); return True
    if step == "create_count":
        if not text.strip().isdigit() or int(text.strip()) < 1 or int(text.strip()) > 10: txt, kb = auction_prompt("create_count", ctx); reply("❌ Введите число лотов от 1 до 10.\n\n" + txt, kb); return True
        ctx["count"] = int(text.strip()); ctx["lots"] = []; ask("create_lot"); return True
    if step == "create_lot":
        parsed = parse_lot_line(text)
        if not parsed: txt, kb = auction_prompt("create_lot", ctx); reply("❌ Формат: название, цена, ссылка на продавца (через запятую). {}\n\n".format(LOT_PRICE_HINT) + txt, kb); return True
        name, min_price, seller = parsed; ctx["lots"].append({"name": name, "min_price": min_price, "seller": seller}); ctx["photo_mode"] = "create"; ask("create_photo"); return True
    if step == "create_photo":
        url = extract_photo_url({"attachments": attachments}) if attachments else None
        if not url: txt, kb = auction_prompt("create_photo", ctx); reply("❌ Прикрепите фото лота или нажмите «Пропустить».\n\n" + txt, kb); return True
        path = save_auction_photo_file(url); att = None
        if path: att = upload_photo_file(peer, path) or upload_photo_file(peer, path)
        finish_photo_step(path, att); return True
    if step == "delete_peer":
        pid = need_chat("delete_peer")
        if pid is None: return True
        auctions = get_auctions_for_peer(pid)
        if not auctions: back_to_menu("❌ В чате {} нет аукционов.".format(pid)); return True
        set_auction_state(sender, peer, "menu", ctx); lines = ["Выберите аукцион для удаления:"]
        for i, a in enumerate(auctions, 1): lines.append("{}. {} ({})".format(i, a["name"], a["datetime_str"]))
        if len(auctions) > 8: lines.append("(кнопками показаны первые 8, всего: {})".format(len(auctions)))
        reply("\n".join(lines), auction_list_kb(auctions, "auction_del_sel")); return True
    if step == "edit_peer":
        pid = need_chat("edit_peer")
        if pid is None: return True
        auctions = get_auctions_for_peer(pid)
        if not auctions: back_to_menu("❌ В чате {} нет аукционов.".format(pid)); return True
        set_auction_state(sender, peer, "menu", ctx); lines = ["Выберите аукцион для редактирования:"]
        for i, a in enumerate(auctions, 1): lines.append("{}. {} ({})".format(i, a["name"], a["datetime_str"]))
        if len(auctions) > 8: lines.append("(кнопками показаны первые 8, всего: {})".format(len(auctions)))
        reply("\n".join(lines), auction_list_kb(auctions, "auction_edit_show")); return True
    if step == "edit_dt":
        dt = parse_auction_dt(text)
        if not dt: txt, kb = auction_prompt("edit_dt", ctx); reply("❌ Неверный формат. Пример: 04.06.26 15:00\n\n" + txt, kb); return True
        with DB_LOCK: CONN.execute("UPDATE auctions SET datetime_str=? WHERE id=?", (text.strip(), ctx["auction_id"])); CONN.commit()
        a = get_auction(ctx["auction_id"]); set_auction_state(sender, peer, "edit_menu", ctx)
        reply("✅ Дата и время обновлены.\n\n" + edit_menu_text(a) + "\n\nВыберите что хотите отредактировать:", edit_menu_kb(a["id"])); return True
    if step == "edit_name":
        with DB_LOCK: CONN.execute("UPDATE auctions SET name=? WHERE id=?", (text.strip(), ctx["auction_id"])); CONN.commit()
        a = get_auction(ctx["auction_id"]); set_auction_state(sender, peer, "edit_menu", ctx)
        reply("✅ Название обновлены.\n\n" + edit_menu_text(a) + "\n\nВыберите что хотите отредактировать:", edit_menu_kb(a["id"])); return True
    if step == "edit_lot_num":
        lots = get_lots(ctx["auction_id"])
        if not text.strip().isdigit() or int(text.strip()) < 1 or int(text.strip()) > len(lots): txt, kb = auction_prompt("edit_lot_num", ctx); reply("❌ Неверный номер лота.\n\n" + txt, kb); return True
        lot = lots[int(text.strip()) - 1]; ctx["lot_id"] = lot["id"]; set_auction_state(sender, peer, "edit_lot_menu", ctx)
        kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Удалить", "payload": json.dumps({"cmd": "auction_lot_del", "id": lot["id"]})}, "color": "negative"}, {"action": {"type": "callback", "label": "Редактировать", "payload": json.dumps({"cmd": "auction_lot_edit", "id": lot["id"]})}, "color": "primary"}], [{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "auction_back", "to": "edit_menu_show"})}, "color": "primary"}, {"action": {"type": "callback", "label": "❌ Отмена", "payload": json.dumps({"cmd": "auction_cancel"})}, "color": "negative"}]]}
        reply("Лот {}: «{}» (мин. {}, продавец: {}).\nЧто сделать с лотом?".format(lot["lot_number"], lot["name"], fmt_rub(lot["min_price"]), lot.get("seller") or "не указан"), kb); return True
    if step == "edit_lot_data":
        parsed = parse_lot_line(text)
        if not parsed: txt, kb = auction_prompt("edit_lot_data", ctx); reply("❌ Формат: название, цена, ссылка на продавца (через запятую). {}\n\n".format(LOT_PRICE_HINT) + txt, kb); return True
        name, min_price, seller = parsed; ctx["edit_name"] = name; ctx["edit_price"] = min_price; ctx["edit_seller"] = seller; ctx["photo_mode"] = "editlot"; ask("edit_lot_photo"); return True
    if step == "edit_lot_photo":
        url = extract_photo_url({"attachments": attachments}) if attachments else None
        if not url: txt, kb = auction_prompt("edit_lot_photo", ctx); reply("❌ Прикрепите фото или нажмите «Пропустить».\n\n" + txt, kb); return True
        path = save_auction_photo_file(url); att = None
        if path: att = upload_photo_file(peer, path) or upload_photo_file(peer, path)
        finish_photo_step(path, att); return True
    if step == "add_lot_data":
        parsed = parse_lot_line(text)
        if not parsed: txt, kb = auction_prompt("add_lot_data", ctx); reply("❌ Формат: название, цена, ссылка на продавца (через запятую). {}\n\n".format(LOT_PRICE_HINT) + txt, kb); return True
        name, min_price, seller = parsed; ctx["add_name"] = name; ctx["add_price"] = min_price; ctx["add_seller"] = seller; ctx["photo_mode"] = "add"; ask("add_lot_photo"); return True
    if step == "add_lot_photo":
        url = extract_photo_url({"attachments": attachments}) if attachments else None
        if not url: txt, kb = auction_prompt("add_lot_photo", ctx); reply("❌ Прикрепите фото или нажмите «Пропустить».\n\n" + txt, kb); return True
        path = save_auction_photo_file(url); att = None
        if path: att = upload_photo_file(peer, path) or upload_photo_file(peer, path)
        finish_photo_step(path, att); return True
    if step == "announce_peer":
        pid = need_chat("announce_peer")
        if pid is None: return True
        auctions = get_auctions_for_peer(pid)
        if not auctions: back_to_menu("❌ В чате {} нет аукционов.".format(pid)); return True
        set_auction_state(sender, peer, "menu", ctx); lines = ["Выберите аукцион для анонса:"]
        for i, a in enumerate(auctions, 1): lines.append("{}. {} ({})".format(i, a["name"], a["datetime_str"]))
        if len(auctions) > 8: lines.append("(кнопками показаны первые 8, всего: {})".format(len(auctions)))
        reply("\n".join(lines), auction_list_kb(auctions, "auction_ann_sel")); return True
    if step == "active_peer":
        pid = need_chat("active_peer")
        if pid is None: return True
        auctions = get_auctions_for_peer(pid)
        if not auctions: back_to_menu("❌ В чате {} нет аукционов.".format(pid)); return True
        set_auction_state(sender, peer, "menu", ctx); lines = ["Аукционы чата {}:".format(pid)]
        for i, a in enumerate(auctions, 1): lines.append("{}. {}".format(i, a["name"]))
        if len(auctions) > 8: lines.append("(кнопками показаны первые 8, всего: {})".format(len(auctions)))
        reply("\n".join(lines), auction_list_kb(auctions, "auction_view")); return True
    if step == "control_peer":
        pid = need_chat("control_peer")
        if pid is None: return True
        cur = get_setting(0, "auc_clean_{}".format(pid), "0"); set_auction_state(sender, peer, "menu", ctx)
        kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Да", "payload": json.dumps({"cmd": "auction_control_set", "peer": pid, "val": 1})}, "color": "positive"}, {"action": {"type": "callback", "label": "Нет", "payload": json.dumps({"cmd": "auction_control_set", "peer": pid, "val": 0})}, "color": "negative"}], [{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "auction_back", "to": "menu"})}, "color": "primary"}]]}
        reply("Вы хотите что бы во время аукциона в чате {} удалялись все сообщения кроме ставок?\n(Сейчас: {})".format(pid, "включено" if cur == "1" else "выключено"), kb); return True
    if step == "cancel_last_peer":
        pid = need_chat("cancel_last_peer")
        if pid is None: return True
        clear_auction_state(sender, peer); do_cancel_last_bid(peer, pid); return True
    return False

# ===== ПРОМОКОДЫ =====
def promo_menu_kb():
    return {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "Создать", "payload": json.dumps({"cmd": "promo_create"})}, "color": "positive"}, {"action": {"type": "callback", "label": "Удалить", "payload": json.dumps({"cmd": "promo_del_btn"})}, "color": "negative"}],
        [{"action": {"type": "callback", "label": "📊 Активные", "payload": json.dumps({"cmd": "promo_active_list"})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "promo_cancel"})}, "color": "negative"}]]}
def promo_kind_kb():
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Экс. карта", "payload": json.dumps({"cmd": "promo_kind_ex"})}, "color": "primary"}], [{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "promo_cancel"})}, "color": "negative"}]]}
def promo_type_kb():
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Активации", "payload": json.dumps({"cmd": "promo_type_act"})}, "color": "primary"}, {"action": {"type": "callback", "label": "По времени", "payload": json.dumps({"cmd": "promo_type_time"})}, "color": "primary"}], [{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "promo_cancel"})}, "color": "negative"}]]}
def promo_cancel_kb():
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "promo_cancel"})}, "color": "negative"}]]}
def get_promo(code):
    with DB_LOCK:
        row = CONN.execute("SELECT * FROM promos WHERE code=?", (code,)).fetchone()
        return dict(row) if row else None

def open_promo_menu(peer, sender):
    close_existing_editors(peer, sender)
    with DB_LOCK: count = CONN.execute("SELECT COUNT(*) FROM promos").fetchone()[0]
    set_auction_state(sender, peer, "promo_menu", {})
    send_msg(peer, f"📊 Всего активных промокодов: {count}\n\nВыберите действие:", keyboard=promo_menu_kb())

def build_promo_active_text():
    with DB_LOCK:
        rows = CONN.execute("SELECT code, kind, card_name, max_act, act, expire_ts FROM promos ORDER BY id").fetchall()
    if not rows: return None
    lines = ["📊 Активные промокоды:\n"]; now_ts = int(time.time())
    for r in rows:
        if r["kind"] == "activations":
            left = max(0, (r["max_act"] or 0) - (r["act"] or 0))
            lines.append("{} «{}» — осталось {} активаций".format(r["code"], r["card_name"], left))
        else:
            if r["expire_ts"] and now_ts > r["expire_ts"]:
                lines.append("{} «{}» — истёк".format(r["code"], r["card_name"]))
            else:
                dt = datetime.datetime.fromtimestamp(r["expire_ts"], MSK_TZ).strftime("%d.%m.%y %H:%M") if r["expire_ts"] else "—"
                lines.append("{} «{}» — до {}".format(r["code"], r["card_name"], dt))
    return "\n".join(lines)

def close_promo_session(peer, ctx, txt):
    cm = ctx.get("msg_cmid"); mid = ctx.get("msg_id")
    for kw in (({"conversation_message_ids": [cm]} if cm else None), ({"message_ids": [mid]} if mid else None)):
        if not kw: continue
        try: VK.messages.delete(peer_id=peer, delete_for_all=1, **kw); break
        except: continue
    send_msg(peer, txt)

def handle_promo_input(sender, peer, text, cmid=None, attachments=None):
    state = get_auction_state(sender, peer)
    if not state: return False
    step = state["step"]
    if not step.startswith("promo_"): return False
    if sender not in (CREATOR_ID, LEADER_ID): return False
    ctx = state.get("context", {})
    if time.time() - ctx.get("ts", 0) > 60:
        clear_auction_state(sender, peer); close_promo_session(peer, ctx, "⏰ Время редактора промокодов вышло, вы бездействовали минуту."); return True
    def reply(msg, kb=None): send_msg(peer, msg, keyboard=kb)
    if text.lower() in ["отмена", "отменить"]: clear_auction_state(sender, peer); reply("❌ Редактор промокодов закрыт."); return True
    if step == "promo_menu": reply("Выберите действие", promo_menu_kb()); return True
    if step == "promo_kind": reply("На что будет промокод?", promo_kind_kb()); return True
    if step == "promo_type": reply("Выберите тип промокода", promo_type_kb()); return True
    if step == "promo_card":
        name = text.strip()
        if name.lower().endswith((".png", ".jpg", ".jpeg")): name = name.rsplit(".", 1)[0]
        if not strict_template(name): reply("❌ Такого названия карты нет в папке бота ({}). Введите название карты:".format(name), promo_cancel_kb()); return True
        ctx["card_name"] = name; set_auction_state(sender, peer, "promo_code", ctx); reply("Придумайте промокод # (например #exclusive):", promo_cancel_kb()); return True
    if step == "promo_code":
        code = text.strip()
        if not code.startswith("#"): reply("❌ Промокод обязательно писать с #. Придумайте промокод #:", promo_cancel_kb()); return True
        if len(code) < 2: reply("❌ Слишком короткий промокод. Придумайте промокод #:", promo_cancel_kb()); return True
        if get_promo(code): reply("❌ Такой промокод уже существует. Придумайте промокод #:", promo_cancel_kb()); return True
        ctx["code"] = code; set_auction_state(sender, peer, "promo_type", ctx); reply("Выберите тип промокода", promo_type_kb()); return True
    if step == "promo_limit":
        if not text.strip().isdigit() or int(text.strip()) < 1: reply("❌ Введите число людей (цифрой):", promo_cancel_kb()); return True
        n = int(text.strip())
        with DB_LOCK: CONN.execute("INSERT INTO promos(code, kind, card_name, max_act, act, expire_ts, created_by, created_at) VALUES(?,?,?,?,0,0,?,?)", (ctx["code"], "activations", ctx["card_name"], n, sender, int(time.time()))); CONN.commit()
        clear_auction_state(sender, peer); reply("✅ Промокод {} создан: экс. карта «{}», лимит {} активаций.".format(ctx["code"], ctx["card_name"], n)); return True
    if step == "promo_expire":
        dt = parse_auction_dt(text)
        if not dt: reply("❌ Неверный формат. Пример: 26.06.25 11:23", promo_cancel_kb()); return True
        ts = int(dt.timestamp())
        with DB_LOCK: CONN.execute("INSERT INTO promos(code, kind, card_name, max_act, act, expire_ts, created_by, created_at) VALUES(?,?,?,?,0,?,?,?)", (ctx["code"], "time", ctx["card_name"], 0, ts, sender, int(time.time()))); CONN.commit()
        clear_auction_state(sender, peer); reply("✅ Промокод {} создан: экс. карта «{}», действует до {}.".format(ctx["code"], ctx["card_name"], text.strip())); return True
    if step == "promo_del":
        code = text.strip()
        if not code.startswith("#"): code = "#" + code
        row = get_promo(code)
        if not row: reply("❌ Промокод {} не найден. Введите название промокода который нужно удалить:".format(code), promo_cancel_kb()); return True
        with DB_LOCK: CONN.execute("DELETE FROM promo_used WHERE promo_id=?", (row["id"],)); CONN.execute("DELETE FROM promos WHERE id=?", (row["id"],)); CONN.commit()
        clear_auction_state(sender, peer); reply("✅ Промокод {} удалён.".format(code)); return True
    return False

def handle_promo_use(peer, sender, raw):
    code = raw.strip().split()[0] if raw.strip() else ""
    if not code: send_msg(peer, "❌ Формат: /promo #промокод"); return
    if not code.startswith("#"): code = "#" + code
    row = get_promo(code)
    if not row: send_msg(peer, "❌ Промокод {} не найден.".format(code)); return
    now = int(time.time())
    if row["kind"] == "time" and row["expire_ts"] and now > row["expire_ts"]: send_msg(peer, "❌ Промокод {} просрочен.".format(code)); return
    if row["kind"] == "activations" and row["act"] >= row["max_act"]: send_msg(peer, "❌ У промокода {} закончился лимит активаций.".format(code)); return

    card_name = row["card_name"]
    promo_ids = [r["id"] for r in CONN.execute("SELECT id FROM promos WHERE card_name=?", (card_name,)).fetchall()]
    if promo_ids:
        ph = ",".join(["?"] * len(promo_ids))
        query = f"SELECT 1 FROM promo_used WHERE user_id=? AND promo_id IN ({ph})"
        params = [sender] + promo_ids
        used_any = CONN.execute(query, params).fetchone()
        if used_any:
            send_msg(peer, f"❌ Вы уже получали карту «{card_name}» ранее по другому промокоду. Повторная активация невозможна.")
            return

    with DB_LOCK:
        used = CONN.execute("SELECT 1 FROM promo_used WHERE promo_id=? AND user_id=?", (row["id"], sender)).fetchone()
        if used: send_msg(peer, "❌ Вы уже активировали этот промокод."); return
        if not strict_template(row["card_name"]): send_msg(peer, "❌ Ошибка: карта промокода не найдена в папке бота."); return
        CONN.execute("INSERT OR IGNORE INTO promo_used(promo_id, user_id, used_at) VALUES(?,?,?)", (row["id"], sender, now))
        CONN.execute("UPDATE promos SET act=act+1 WHERE id=?", (row["id"],)); CONN.commit()
    grant_excard(sender, row["card_name"], apply=True)
    send_msg(peer, "✅ Промокод {} активирован! Эксклюзивная карта «{}» добавлена в раздел «Эксклюзив» и применена.".format(code, row["card_name"]))
    send_card_to(peer, sender)

def handle_ex_card(peer, sender, raw, grant):
    targets = extract_targets(raw, 0); name = raw
    name = re.sub(r"\[id\d+\|[^]]*\]", " ", name); name = re.sub(r"@id\d+", " ", name, flags=re.I)
    name = re.sub(r"https?://vk.(?:com|ru)/[a-zA-Z0-9._]+", " ", name); name = re.sub(r"\b\d{5,}\b", " ", name)
    name = " ".join(name.split())
    if name.lower().endswith((".png", ".jpg", ".jpeg")): name = name.rsplit(".", 1)[0]
    if not targets or not name: send_msg(peer, "❌ Формат: {} @юзер <название карты>".format("/экс карта" if grant else "/забрать карту")); return
    t = targets[0]
    if grant:
        if not strict_template(name): send_msg(peer, "❌ Такого названия карты нет в папке бота: {}.".format(name)); return
        grant_excard(t, name, apply=True); send_msg(peer, "✅ {} выдана эксклюзивная карта «{}».".format(silent_mention_badge(t, peer), name))
    else:
        revoke_excard(t, name); send_msg(peer, "✅ У {} забрана эксклюзивная карта «{}».".format(silent_mention_badge(t, peer), name))

# --- /voice с интерактивным меню ---
def handle_voice(peer, sender, msg_obj, raw):
    reply = msg_obj.get("reply_message") or {}
    if not reply.get("from_id"):
        send_msg(peer, "❌ Ответьте на сообщение: /voice"); return
    close_existing_editors(peer, sender)
    rtext = reply.get("text", "") or ""; att = None
    url = extract_photo_url(reply)
    if url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MD BOT)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                if len(data) > 1000: att = upload_photo(peer, io.BytesIO(data))
        except Exception as e: print("voice photo error:", e)
    if not rtext and not att: rtext = "📷"
    kb = {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "🌐 Во все чаты", "payload": json.dumps({"cmd": "voice_all_chats"})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "💬 Один чат", "payload": json.dumps({"cmd": "voice_one_chat"})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "👥 Всем пользователям (в ЛС)", "payload": json.dumps({"cmd": "voice_all_users"})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "❌ Отмена", "payload": json.dumps({"cmd": "voice_cancel"})}, "color": "negative"}]
    ]}
    sent_id = send_msg(peer, "📢 Куда отправить это сообщение?", keyboard=kb)
    cmid = None; msg_id = sent_id if isinstance(sent_id, int) else None
    if msg_id:
        try: cmid = resolve_cmid(peer, msg_id)
        except: pass
    set_auction_state(sender, peer, "voice_menu", {"reply_text": rtext, "reply_att": att, "msg_cmid": cmid, "msg_id": msg_id})
# -----------------------------------------

# ===== ШРИФТ =====
FONT_CACHE = os.path.join(DATA_DIR, "card_font_cyr.ttf")
_FONT_RESOLVED = {"path": None, "tried": False}
def ensure_font():
    old = os.path.join(DATA_DIR, "card_font.ttf")
    if os.path.isfile(old):
        try: os.remove(old)
        except: pass
    if os.path.isfile(FONT_CACHE): return FONT_CACHE
    candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/freesans.ttf"]
    for p in candidates:
        if os.path.isfile(p): return p
    try:
        hits = glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
        for h in hits:
            if any(k in h.lower() for k in ["dejavu", "liberation", "ptsans", "roboto", "noto", "freesans"]): return h
        if hits: return hits[0]
    except: pass
    urls = ["https://raw.githubusercontent.com/google/fonts/main/ofl/ptsans/PT_Sans-Web-Regular.ttf", "https://github.com/google/fonts/raw/main/ofl/ptsans/PT_Sans-Web-Regular.ttf", "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans.ttf"]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MD BOT)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                if len(data) > 100000:
                    with open(FONT_CACHE, "wb") as f: f.write(data); return FONT_CACHE
        except Exception as e: print("font download error:", e)
    return None
def get_font(size):
    if not _FONT_RESOLVED["tried"]: _FONT_RESOLVED["path"] = ensure_font(); _FONT_RESOLVED["tried"] = True
    p = _FONT_RESOLVED["path"]
    if p:
        try: return ImageFont.truetype(p, size)
        except: pass
    try: return ImageFont.load_default(size)
    except: return ImageFont.load_default()

# ===== ЗАГРУЗКА ФОТО В ВК + КЭШ =====
def upload_photo(peer, img_buf):
    try: img_buf.seek(0)
    except: pass
    raw = img_buf.getvalue()
    if not raw: raise RuntimeError("EMPTY_IMAGE: картинка пустая")
    if len(raw) > 4500000: raise RuntimeError("TOO_BIG: файл {} байт (лимит ~5 МБ)".format(len(raw)))
    data = None; last_resp = None
    for attempt in range(4):
        try:
            if attempt < 3: server = VK.photos.getMessagesUploadServer(peer_id=peer)
            else: server = VK.photos.getMessagesUploadServer()
            resp = requests.post(server["upload_url"], files={"photo": ("card.jpg", raw, "image/jpeg")}, timeout=30)
            data = resp.json(); last_resp = data
            if data.get("photo"): break
            data = None
        except Exception as e: last_resp = {"exception": str(e)}; data = None
        time.sleep(0.8 + attempt * 0.7)
    if not data or not data.get("photo") or not data.get("hash") or not data.get("server"):
        raise RuntimeError("UPLOAD_BAD_RESPONSE: {} (размер файла: {} байт)".format(str(last_resp)[:200], len(raw)))
    saved = VK.photos.saveMessagesPhoto(photo=data["photo"], hash=data["hash"], server=data["server"])
    if not saved: raise RuntimeError("SAVE_EMPTY: ВК не вернул фото после сохранения")
    return "photo{}_{}".format(saved[0]["owner_id"], saved[0]["id"])

def send_card_image(peer, user_id):
    card = get_card(user_id); key = "card_att_v4_{}".format(user_id)
    try: cached = json.loads(get_setting(0, key, "") or "{}")
    except: cached = {}
    if cached.get("ts") == card["updated_at"] and cached.get("att"): return cached["att"]
    img_buf = render_card(user_id)
    if not img_buf: return None
    att = upload_photo(peer, img_buf); set_setting(0, key, json.dumps({"ts": card["updated_at"], "att": att})); return att

def send_card_to(peer, target_id):
    err = ""; att = None
    try: att = send_card_image(peer, target_id)
    except Exception as e: err = str(e); print("card send error:", err)
    if not att:
        if err:
            if "[15]" in err or "scope" in err.lower(): send_msg(peer, "❌ У токена нет права «Фотографии»: Управление → Использование API → галочка «Фото» → пересоздать токен.")
            else: send_msg(peer, "❌ Ошибка отправки карточки: {}".format(err))
        else: send_msg(peer, "❌ Не найден шаблон карточки (card_male.jpg/png) или не установлен Pillow.")
        return
    card = get_card(target_id)
    txt = "🗃️ Личная карточка: {}".format(silent_mention_badge(target_id, peer))
    txt += " | Информация карточки подтверждена✅" if card.get("verified") else " | Информация карточки не подтверждена❌"
    send_msg(peer, txt, attachments=att)

# ===== ОТРИСОВКА КАРТОЧКИ =====
CARD_BOXES = {"name": (0.035, 0.800, 0.340, 0.080), "biz": (0.468, 0.215, 0.525, 0.085), "realty": (0.468, 0.378, 0.525, 0.085), "prop": (0.468, 0.520, 0.525, 0.085), "garage": (0.468, 0.680, 0.525, 0.085), "phone": (0.468, 0.825, 0.525, 0.085)}

def parse_custom_color(val):
    if not val: return None
    if isinstance(val, list) and len(val) == 3: return tuple(val)
    if isinstance(val, str):
        val = val.strip()
        if val.startswith('#') and len(val) == 7:
            try: return tuple(int(val[i:i+2], 16) for i in (1, 3, 5))
            except: pass
        parts = val.split(',')
        if len(parts) == 3:
            try:
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255: return (r, g, b)
            except: pass
    return None

# --- Идеальная обводка + жирный ---
def draw_text_advanced(draw, pos, text, font, fill, outline_color=None, outline_w=1, bold=False):
    x, y = pos
    bold_r = 1 if bold else 0
    # 1. Рисуем обводку. При bold — расширяем радиус, чтобы обводка не залезала под утолщённый текст.
    if outline_color and outline_w > 0:
        r = outline_w + bold_r
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx == 0 and dy == 0: continue
                if bold and abs(dx) <= 1 and abs(dy) <= 1: continue  # внутренняя зона — там будет bold-заливка
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    # 2. Рисуем основной текст (bold = 3x3 утолщение)
    if bold:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                draw.text((x + dx, y + dy), text, font=font, fill=fill)
    else:
        draw.text((x, y), text, font=font, fill=fill)

def get_frame_box(color_key):
    now = time.time()
    if _FRAME_BOXES_CACHE["data"] is None or now - _FRAME_BOXES_CACHE["ts"] > 60:
        try:
            with open(FRAME_BOXES_FILE) as f: _FRAME_BOXES_CACHE["data"] = json.load(f)
        except: _FRAME_BOXES_CACHE["data"] = {}
        _FRAME_BOXES_CACHE["ts"] = now
    data = _FRAME_BOXES_CACHE["data"] or {}
    for k in (color_key, "default"):
        v = data.get(k)
        if v and len(v) == 4:
            try: return tuple(float(x) for x in v)
            except: pass
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
        ph = Image.open(path).convert("RGB"); W, H = img.size
        rx, ry, rw, rh = box; fx, fy, fw, fh = int(rx * W), int(ry * H), int(rw * W), int(rh * H)
        target_ratio = fw / float(fh); pw, phh = ph.size; cur = pw / float(phh)
        if cur > target_ratio:
            new_w = int(phh * target_ratio); left = (pw - new_w) // 2; ph = ph.crop((left, 0, left + new_w, phh))
        else:
            new_h = int(pw / target_ratio); top = (phh - new_h) // 2; ph = ph.crop((0, top, pw, top + new_h))
        ph = ph.resize((fw, fh), Image.LANCZOS if hasattr(Image, "LANCZOS") else Image.ANTIALIAS)
        mask = Image.new("L", (fw, fh), 0); md = ImageDraw.Draw(mask); r = max(6, int(min(fw, fh) * 0.05))
        try: md.rounded_rectangle((0, 0, fw - 1, fh - 1), radius=r, fill=255); img.paste(ph, (fx, fy), mask)
        except: img.paste(ph, (fx, fy))
    except Exception as e: print("paste_custom_photo error:", e)
    return img

def render_card(user_id):
    if not PIL_OK: return None
    card = get_card(user_id); design = get_design(user_id)
    template = None; ex = design.get("exclusive") or ""
    if ex: template = strict_template(ex)
    if not template: template = card_template_path(design.get("color", "red"))
    if not template: return None
    img = Image.open(template).convert("RGB"); W, H = img.size
    if W > 1600:
        ratio = 1600.0 / W; img = img.resize((1600, int(H * ratio)), Image.LANCZOS if hasattr(Image, "LANCZOS") else Image.ANTIALIAS); W, H = img.size
    
    if design.get("photo") and not ex:
        img = paste_custom_photo(img, user_id, get_frame_box(design.get("color", "red")))
        
    draw = ImageDraw.Draw(img)
    
    name_rgb = parse_custom_color(design.get("custom_name_color")) or TEXT_COLORS.get(design.get("name_color"), (255, 255, 255))
    fields_rgb = parse_custom_color(design.get("custom_fields_color")) or TEXT_COLORS.get(design.get("fields_color"), (30, 30, 30))
    stroke_name_rgb = parse_custom_color(design.get("custom_stroke_name")) or (TEXT_COLORS.get(design.get("stroke_name")) if design.get("stroke_name") else None)
    stroke_fields_rgb = parse_custom_color(design.get("custom_stroke_fields")) or (TEXT_COLORS.get(design.get("stroke_fields")) if design.get("stroke_fields") else None)
    
    bold_sw = design.get("bold") == "1"
    outline_w = int(design.get("outline_width", 1))
    font_scales = design.get("font_scale", {})
    
    biz = format_businesses(json.loads(card["businesses"] or "[]")) or "Неизвестно"
    realty = format_realty(json.loads(card["realty"] or "[]")) or "Неизвестно"
    prop = format_property(card["property_val"])
    garage = ("#" + card["garage"]) if card["garage"] else "Неизвестно"
    phone = format_phone(card["phone"]) if card["phone"] else "Неизвестно"
    name = card["name"] or "Неизвестно"

    def draw_box(key, text, color, center_x=False, pad=3, outline=None):
        rx, ry, rw, rh = CARD_BOXES[key]
        off = (design.get("pos") or {}).get(key) or [0.0, 0.0]
        try: ox, oy = float(off[0]), float(off[1])
        except: ox, oy = 0.0, 0.0
        x, y, w, h = (rx + ox) * W, (ry + oy) * H, rw * W, rh * H
        
        base_size = max(14, int(h * 0.48))
        scale = font_scales.get(key, 1.0)
        size = int(base_size * scale)
        size = max(10, min(size, int(h * 0.85)))
        
        f = get_font(size)
        def text_w(t, fnt):
            try: return draw.textlength(t, font=fnt)
            except:
                try: return fnt.getsize(t)[0]
                except: return len(t) * 10
        while text_w(text, f) > w - pad * 2 and size > 10: size -= 1; f = get_font(size)
        try: bb = draw.textbbox((0, 0), text, font=f); th = bb[3] - bb[1]; yoff = bb[1]
        except: th, yoff = size, 0
        ty = y + (h - th) / 2 - yoff; tw = text_w(text, f)
        tx = x + (w - tw) / 2 if center_x else x + pad
        
        draw_text_advanced(draw, (tx, ty), text, f, color, outline_color=outline, outline_w=outline_w, bold=bold_sw)

    draw_box("name", name, name_rgb, center_x=True, outline=stroke_name_rgb)
    draw_box("biz", biz, fields_rgb, pad=3, outline=stroke_fields_rgb)
    draw_box("realty", realty, fields_rgb, pad=3, outline=stroke_fields_rgb)
    draw_box("prop", prop, fields_rgb, pad=3, outline=stroke_fields_rgb)
    draw_box("garage", garage, fields_rgb, pad=3, outline=stroke_fields_rgb)
    draw_box("phone", phone, fields_rgb, pad=3, outline=stroke_fields_rgb)
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=88, optimize=True); buf.seek(0); return buf

def init_db():
    try: os.makedirs(PHOTO_DIR, exist_ok=True); os.makedirs(AUCTION_PHOTO_DIR, exist_ok=True)
    except: pass
    with DB_LOCK:
        CONN.execute("""CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, name TEXT, text TEXT, attachments TEXT, source_message_id INTEGER DEFAULT 0, interval_minutes INTEGER, repeat_count INTEGER DEFAULT 1, next_trigger REAL, enabled INTEGER DEFAULT 1, UNIQUE(peer_id, name))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS settings (peer_id INTEGER, key TEXT, value TEXT, UNIQUE(peer_id, key))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS birthdays (user_id INTEGER, peer_id INTEGER, bdate TEXT, updated_at INTEGER, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS birthday_congratulated (user_id INTEGER, peer_id INTEGER, year INTEGER, congratulated_at INTEGER, PRIMARY KEY(user_id, peer_id, year))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS members (user_id INTEGER, peer_id INTEGER, nickname TEXT DEFAULT '', warnings INTEGER DEFAULT 0, warn_durations TEXT DEFAULT '', warn_expiry INTEGER DEFAULT 0, last_active TEXT DEFAULT '', streak INTEGER DEFAULT 0, poll_protected INTEGER DEFAULT 0, join_time INTEGER DEFAULT 0, last_vote_time INTEGER DEFAULT 0, who_name TEXT DEFAULT '', who_ts INTEGER DEFAULT 0, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS roles (user_id INTEGER, peer_id INTEGER, role INTEGER DEFAULT 0, UNIQUE(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS statuses (id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, name TEXT, UNIQUE(peer_id, name))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS user_statuses (user_id INTEGER, peer_id INTEGER, status_id INTEGER, UNIQUE(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS punishment_history (id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, user_id INTEGER, type TEXT, reason TEXT, message_id INTEGER DEFAULT 0, message_text TEXT DEFAULT '', issued_by INTEGER, issued_at INTEGER, duration_minutes INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS dice_games (id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, initiator INTEGER, opponent INTEGER, state TEXT DEFAULT 'pending', message_id INTEGER DEFAULT 0, initiator_roll INTEGER DEFAULT 0, opponent_roll INTEGER DEFAULT 0, current_turn INTEGER DEFAULT 0, created_at INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS dice_mentions (id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, user_id INTEGER, next_trigger INTEGER DEFAULT 0, end_time INTEGER DEFAULT 0, interval_minutes INTEGER DEFAULT 60)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS poll_votes (vote_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, peer_id INTEGER, poll_time INTEGER, date TEXT)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS info_blocks (peer_id INTEGER, key TEXT, text TEXT, PRIMARY KEY(peer_id, key))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS marriages (id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, user1 INTEGER, user2 INTEGER, created_at INTEGER DEFAULT 0, UNIQUE(peer_id, user1), UNIQUE(peer_id, user2))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS message_stats (user_id INTEGER, peer_id INTEGER, msg_count INTEGER DEFAULT 0, sticker_count INTEGER DEFAULT 0, dice_wins INTEGER DEFAULT 0, kmb_wins INTEGER DEFAULT 0, char_count INTEGER DEFAULT 0, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS bans (user_id INTEGER, peer_id INTEGER, banned_by INTEGER, ban_until INTEGER DEFAULT 0, reason TEXT DEFAULT '', created_at INTEGER DEFAULT 0, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS kmb_games (id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, initiator INTEGER, opponent INTEGER, state TEXT DEFAULT 'pending', message_id INTEGER DEFAULT 0, init_choice TEXT DEFAULT '', opp_choice TEXT DEFAULT '', created_at INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS badges (user_id INTEGER, peer_id INTEGER, emoji TEXT DEFAULT '', PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS message_cache (id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, cmid INTEGER, from_id INTEGER, ts INTEGER)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS join_stats (user_id INTEGER, peer_id INTEGER, first_join INTEGER DEFAULT 0, in_top INTEGER DEFAULT 1, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS player_cards (user_id INTEGER PRIMARY KEY, name TEXT DEFAULT '', businesses TEXT DEFAULT '[]', realty TEXT DEFAULT '[]', property_val TEXT DEFAULT '', garage TEXT DEFAULT '', phone TEXT DEFAULT '', design TEXT DEFAULT '{}', verified INTEGER DEFAULT 0, updated_at INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS card_edit_state (user_id INTEGER, peer_id INTEGER, step TEXT, context TEXT, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS auctions (id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, name TEXT, datetime_str TEXT, created_by INTEGER, created_at INTEGER, state TEXT DEFAULT 'scheduled', current_lot_index INTEGER DEFAULT 0, current_lot_id INTEGER DEFAULT 0, lot_deadline INTEGER DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS auction_lots (id INTEGER PRIMARY KEY AUTOINCREMENT, auction_id INTEGER, lot_number INTEGER, name TEXT, min_price REAL DEFAULT 20000000, seller TEXT DEFAULT '', photo_path TEXT DEFAULT '', photo_att TEXT DEFAULT '', sold INTEGER DEFAULT 0, winner_id INTEGER DEFAULT 0, final_price REAL DEFAULT 0)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS auction_bids (id INTEGER PRIMARY KEY AUTOINCREMENT, lot_id INTEGER, user_id INTEGER, amount REAL, bid_time INTEGER)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS auction_state (user_id INTEGER, peer_id INTEGER, step TEXT, context TEXT, PRIMARY KEY(user_id, peer_id))""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS promos (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, kind TEXT, card_name TEXT, max_act INTEGER DEFAULT 0, act INTEGER DEFAULT 0, expire_ts INTEGER DEFAULT 0, created_by INTEGER, created_at INTEGER)""")
        CONN.execute("""CREATE TABLE IF NOT EXISTS promo_used (promo_id INTEGER, user_id INTEGER, used_at INTEGER, PRIMARY KEY(promo_id, user_id))""")
    migrations = ["ALTER TABLE members ADD COLUMN warn_durations TEXT DEFAULT ''", "ALTER TABLE members ADD COLUMN last_vote_time INTEGER DEFAULT 0", "ALTER TABLE members ADD COLUMN mute_until INTEGER DEFAULT 0", "ALTER TABLE members ADD COLUMN mute_reason TEXT DEFAULT ''", "ALTER TABLE members ADD COLUMN warn_reasons TEXT DEFAULT ''", "ALTER TABLE message_stats ADD COLUMN kmb_wins INTEGER DEFAULT 0", "ALTER TABLE message_stats ADD COLUMN char_count INTEGER DEFAULT 0", "ALTER TABLE members ADD COLUMN who_name TEXT DEFAULT ''", "ALTER TABLE members ADD COLUMN who_ts INTEGER DEFAULT 0", "ALTER TABLE player_cards ADD COLUMN design TEXT DEFAULT '{}'", "ALTER TABLE player_cards ADD COLUMN verified INTEGER DEFAULT 0", "ALTER TABLE auction_lots ADD COLUMN seller TEXT DEFAULT ''"]
    for sql in migrations:
        try: CONN.execute(sql)
        except: pass
    CONN.commit()

def get_setting(peer, key, default=""):
    with DB_LOCK:
        row = CONN.execute("SELECT value FROM settings WHERE peer_id=? AND key=?", (peer, key)).fetchone()
        return row["value"] if row else default
def set_setting(peer, key, value):
    with DB_LOCK: CONN.execute("INSERT OR REPLACE INTO settings(peer_id, key, value) VALUES(?,?,?)", (peer, key, value)); CONN.commit()

def get_chat_owner(peer):
    if VK is None: return OWNER_CACHE.get(peer, 0)
    if peer in OWNER_CACHE: return OWNER_CACHE[peer]
    oid = 0
    try:
        r = VK.messages.getConversationsById(peer_ids=peer); items = r.get("items", [])
        if items: oid = items[0].get("conversation", {}).get("chat_settings", {}).get("owner_id", 0) or 0
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
                if item.get("is_owner"): oid = int(item.get("member_id", 0)); break
        except: pass
    OWNER_CACHE[peer] = oid; return oid

def is_real_owner(sender, peer): return sender > 0 and (sender in (CREATOR_ID, LEADER_ID) or sender == get_chat_owner(peer))
def is_moderator(sender, peer):
    if sender <= 0: return False
    if sender in (CREATOR_ID, LEADER_ID) or sender == get_chat_owner(peer): return True
    return get_user_role(peer, sender) >= 1
def is_admin(sender, peer):
    if sender <= 0: return False
    if sender in (CREATOR_ID, LEADER_ID) or sender == get_chat_owner(peer): return True
    return get_user_role(peer, sender) >= 2
def is_main_admin(sender, peer):
    if sender <= 0: return False
    if sender in (CREATOR_ID, LEADER_ID) or sender == get_chat_owner(peer): return True
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
        return VK.messages.send(**params)
    except Exception as e: LAST_ERR["msg"] = str(e); print("send error:", e); return False

def resolve_cmid(peer, sent_id):
    try:
        resp = VK.messages.getById(message_ids=[sent_id]); items = resp.get("items", [])
        if items:
            cm = items[0].get("conversation_message_id")
            if cm: return int(cm)
    except: pass
    return sent_id

def edit_game_message(peer, game_id, text, keyboard_json=None, table="dice_games"):
    if keyboard_json is not None and not isinstance(keyboard_json, str): keyboard_json = json.dumps(keyboard_json)
    with DB_LOCK:
        row = CONN.execute("SELECT message_id FROM {} WHERE id=?".format(table), (game_id,)).fetchone()
        stored = row["message_id"] if row else 0
    kb = keyboard_json if keyboard_json else json.dumps({"inline": True, "buttons": []})
    try: VK.messages.edit(peer_id=peer, conversation_message_id=stored, message=text, keyboard=kb); return True
    except: pass
    try: VK.messages.edit(peer_id=peer, message_id=stored, message=text, keyboard=kb); return True
    except: pass
    try:
        new_id = VK.messages.send(peer_id=peer, message=text, keyboard=kb, random_id=random.getrandbits(31))
        cmid = resolve_cmid(peer, new_id)
        with DB_LOCK: CONN.execute("UPDATE {} SET message_id=? WHERE id=?".format(table), (cmid, game_id)); CONN.commit()
        return True
    except: return False

def get_user_name(user_id):
    if user_id in NAME_CACHE: return NAME_CACHE[user_id]
    name = "Пользователь"
    try:
        r = VK.users.get(user_ids=user_id)
        if r: name = "{} {}".format(r[0].get('first_name', ''), r[0].get('last_name', '')).strip() or "Пользователь"
    except: pass
    NAME_CACHE[user_id] = name; return name
def mention(user_id): return "[id{}|{}]".format(user_id, get_user_name(user_id))
def silent_mention(user_id): return "[https://vk.com/id{}|{}]".format(user_id, get_user_name(user_id))

def extract_targets(text, reply_from):
    ids = []
    for m in re.finditer(r"\[id(\d+)\|", text, re.I): ids.append(int(m.group(1)))
    for m in re.finditer(r"[@*]id(\d+)", text, re.I): ids.append(int(m.group(1)))
    for m in re.finditer(r"\b(\d{5,})\b", text): ids.append(int(m.group(1)))
    for m in re.finditer(r"https?://vk.(com|ru)/id(\d+)", text, re.I): ids.append(int(m.group(2)))
    for m in re.finditer(r"https?://vk.(com|ru)/([a-zA-Z0-9._]+)", text, re.I):
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
def _ls_segments(body): return [s.strip() for s in body.split(",") if s.strip()]
def _ls_date_ts(dstr):
    try: d, m, y = [int(x) for x in dstr.split(".")]; return int(datetime.datetime(y, m, d, 12, 0, 0, tzinfo=MSK_TZ).timestamp())
    except: return None
def _ls_user(seg):
    m = re.search(r"\[id(\d+)\|", seg)
    if m: return int(m.group(1)), re.sub(r"\[id\d+\|[^]]*\]", " ", seg)
    m = re.search(r"@id(\d+)", seg, re.I)
    if m: return int(m.group(1)), re.sub(r"@id\d+", " ", seg, flags=re.I)
    m = re.search(r"https?://vk.(?:com|ru)/id(\d+)", seg, re.I)
    if m: return int(m.group(1)), re.sub(r"https?://vk.(?:com|ru)/id\d+", " ", seg, flags=re.I)
    m = re.search(r"@(\d{6,})", seg)
    if m: return int(m.group(1)), re.sub(r"@\d{6,}", " ", seg)
    return None, seg
def _ls_peer(seg):
    m = re.search(r"\b(2\d{9})\b", seg); return int(m.group(1)) if m else None
def _ls_apply_firstlogin(body):
    out = []
    for seg in _ls_segments(body):
        uid, rest = _ls_user(seg); peer_id = _ls_peer(seg); md = re.search(r"\b(\d{1,2}.\d{1,2}.\d{4})\b", seg)
        ts = _ls_date_ts(md.group(1)) if md else None
        if not uid or not peer_id or ts is None: out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        with DB_LOCK:
            CONN.execute("INSERT OR IGNORE INTO join_stats(user_id, peer_id, first_join, in_top) VALUES(?,?,?,1)", (uid, peer_id, ts))
            CONN.execute("UPDATE join_stats SET first_join=?, in_top=1 WHERE user_id=? AND peer_id=?", (ts, uid, peer_id)); CONN.commit()
        out.append("✅ id{} → первый вход {} (чат {})".format(uid, md.group(1), peer_id))
    return "\n".join(out) or "✅ Готово"
def _ls_apply_lastlogin(body):
    out = []
    for seg in _ls_segments(body):
        uid, rest = _ls_user(seg); peer_id = _ls_peer(seg); md = re.search(r"\b(\d{1,2}.\d{1,2}.\d{4})\b", seg)
        ts = _ls_date_ts(md.group(1)) if md else None
        if not uid or not peer_id or ts is None: out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        with DB_LOCK:
            CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (uid, peer_id))
            CONN.execute("UPDATE members SET join_time=? WHERE user_id=? AND peer_id=?", (ts, uid, peer_id)); CONN.commit()
        out.append("✅ id{} → последний вход {} (чат {})".format(uid, md.group(1), peer_id))
    return "\n".join(out) or "✅ Готово"
def _ls_apply_topmsg(body):
    out = []
    for seg in _ls_segments(body):
        uid, rest = _ls_user(seg); peer_id = _ls_peer(seg); tmp = re.sub(r"\b2\d{9}\b", " ", rest)
        nums = [int(x) for x in re.findall(r"\b(\d+)\b", tmp)]
        if uid is None:
            if len(nums) >= 3: uid, chars, msgs = nums[0], nums[1], nums[2]
            else: out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        else:
            if len(nums) >= 2: chars, msgs = nums[0], nums[1]
            else: out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        if peer_id is None: out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        with DB_LOCK:
            CONN.execute("INSERT OR IGNORE INTO message_stats(user_id, peer_id, msg_count, sticker_count, dice_wins, kmb_wins, char_count) VALUES(?,?,0,0,0,0,0)", (uid, peer_id))
            CONN.execute("UPDATE message_stats SET char_count=?, msg_count=? WHERE user_id=? AND peer_id=?", (chars, msgs, uid, peer_id)); CONN.commit()
        out.append("✅ id{} → символы={}, сообщения={} (чат {})".format(uid, chars, msgs, peer_id))
    return "\n".join(out) or "✅ Готово"
def _ls_apply_top(body, field):
    out = []
    for seg in _ls_segments(body):
        uid, rest = _ls_user(seg); peer_id = _ls_peer(seg); tmp = re.sub(r"\b2\d{9}\b", " ", rest)
        nums = [int(x) for x in re.findall(r"\b(\d+)\b", tmp)]
        if uid is None:
            if len(nums) >= 2: uid, val = nums[0], nums[1]
            else: out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        else: val = nums[0] if nums else None
        if peer_id is None or val is None: out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        with DB_LOCK:
            CONN.execute("INSERT OR IGNORE INTO message_stats(user_id, peer_id, msg_count, sticker_count, dice_wins, kmb_wins, char_count) VALUES(?,?,0,0,0,0,0)", (uid, peer_id))
            CONN.execute("UPDATE message_stats SET {}=? WHERE user_id=? AND peer_id=?".format(field), (val, uid, peer_id)); CONN.commit()
        out.append("✅ id{} → {} = {} (чат {})".format(uid, field, val, peer_id))
    return "\n".join(out) or "✅ Готово"
def _ls_apply_rbrak(body):
    out = []; now_ts = int(time.time())
    for seg in _ls_segments(body):
        uid, rest = _ls_user(seg); peer_id = _ls_peer(seg); tmp = re.sub(r"\b2\d{9}\b", " ", rest)
        nums = [int(x) for x in re.findall(r"\b(\d+)\b", tmp)]
        if uid is None:
            if len(nums) >= 2: uid, days = nums[0], nums[1]
            else: out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        else: days = nums[0] if nums else None
        if peer_id is None or days is None: out.append("❌ Не понял сегмент: {}".format(seg[:50])); continue
        with DB_LOCK:
            row = CONN.execute("SELECT id FROM marriages WHERE peer_id=? AND (user1=? OR user2=?)", (peer_id, uid, uid)).fetchone()
            if not row: out.append("❌ id{} не состоит в браке в чате {}".format(uid, peer_id)); continue
            CONN.execute("UPDATE marriages SET created_at=? WHERE id=?", (now_ts - days * 86400, row["id"])); CONN.commit()
        out.append("✅ id{} → брак {} дн. (чат {})".format(uid, days, peer_id))
    return "\n".join(out) or "✅ Готово"
def handle_creator_ls(peer, text):
    t = text.strip(); low = t.lower()
    if low.startswith("/firstlogin"): send_msg(peer, _ls_apply_firstlogin(t[len("/firstlogin"):].strip()))
    elif low.startswith("/lastlogin"): send_msg(peer, _ls_apply_lastlogin(t[len("/lastlogin"):].strip()))
    elif low.startswith("/topmsg"): send_msg(peer, _ls_apply_topmsg(t[len("/topmsg"):].strip()))
    elif low.startswith("/topemj"): send_msg(peer, _ls_apply_top(t[len("/topemj"):].strip(), "sticker_count"))
    elif low.startswith("/rbrak"): send_msg(peer, _ls_apply_rbrak(t[len("/rbrak"):].strip()))
    else: send_msg(peer, "ℹ️ Неизвестная служебная команда.")

def sync_members(peer):
    now = time.time()
    if peer in MEMBER_SYNC_CACHE and (now - MEMBER_SYNC_CACHE[peer]) < 300: return
    try:
        members_resp = VK.messages.getConversationMembers(peer_id=peer); items = members_resp.get("items", [])
        today = get_msk_now().strftime("%Y-%m-%d"); current_members = set()
        for item in items:
            uid = int(item.get("member_id", 0))
            if uid > 0: current_members.add(uid)
        with DB_LOCK:
            for uid in current_members: CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (uid, peer))
            all_db = CONN.execute("SELECT user_id FROM members WHERE peer_id=?", (peer,)).fetchall()
            for row in all_db:
                if row["user_id"] not in current_members: CONN.execute("DELETE FROM members WHERE user_id=? AND peer_id=?", (row["user_id"], peer))
            now_ts = int(time.time())
            for uid in current_members: CONN.execute("INSERT OR IGNORE INTO join_stats(user_id, peer_id, first_join, in_top) VALUES(?,?,?,1)", (uid, peer, now_ts))
            CONN.execute("UPDATE members SET join_time=? WHERE peer_id=? AND (join_time IS NULL OR join_time=0)", (now_ts, peer)); CONN.commit()
        MEMBER_SYNC_CACHE[peer] = now
    except: pass
def sync_all_peers(peers_list):
    for peer in peers_list: sync_members(peer); time.sleep(1)

# --- ИСПРАВЛЕНО: безопасное обновление активности (без падения на duplicate PK) ---
def update_member_activity(peer, user_id):
    today = get_msk_now().strftime("%Y-%m-%d")
    yesterday = (get_msk_now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    with DB_LOCK:
        row = CONN.execute("SELECT last_active, streak FROM members WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
        if not row:
            CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id, last_active, streak) VALUES(?,?,?,?)", (user_id, peer, today, 1))
        else:
            last_active = row["last_active"] or ""
            streak = row["streak"] or 0
            if last_active != today:
                new_streak = (streak + 1) if last_active == yesterday else 1
                CONN.execute("UPDATE members SET last_active=?, streak=? WHERE user_id=? AND peer_id=?", (today, new_streak, user_id, peer))
        CONN.commit()
# ---------------------------------------------------------------------------------

def get_streak_emoji(streak):
    if streak >= 30: return "👑"
    if streak >= 25: return "🤑"
    if streak >= 20: return "😈"
    if streak >= 15: return "🤠"
    if streak >= 10: return "😇"
    if streak >= 5: return "😎"
    return "🤓"

def ls_help_text(user_id):
    lines = ["📖 Команды, доступные тебе в ЛС с ботом:", "1. Мд карта — посмотреть свою карту.", "2. Мд редактор карты — редактировать карту (данные, цвета, фото, текст, эксклюзив).", "3. Мд очистить карту [параметр] — очистить свою карту (параметры: бизнесы, недвижимость, имущество, гараж, телефон, фото, имя; без параметра — всё кроме цвета).", "4. /promo #промокод — активировать промокод.", "5. Мд команды — этот список."]
    if is_inspector(user_id) or user_id in (CREATOR_ID, LEADER_ID): lines += ["", "🕵 Скрытые команды проверяющего (работают и в чатах):", "/verify @ - подтвердить карту.", "/deny @ - отменить подтверждение.", "/card @ - посмотреть карту любого.", "/clearcard @ [параметр] - очистить любую карту."]
    if is_auctioneer(user_id) or user_id in (CREATOR_ID, LEADER_ID): lines += ["", "📈 Скрытые команды аукционера:", "/аукцион - редактор аукционов.", "/стопаукцион (номер чата) - отключить идущий аукцион.", "/отменить ласт ставку (номер чата) - отменить верхнюю ставку активного лота.", "/некст лот (номер чата) - завершить текущий лот и перейти к следующему."]
    if user_id in (CREATOR_ID, LEADER_ID): lines += ["", "👑 Скрытые команды создателя/лидера:", "/inspector @ - назначить/снять проверяющего.", "/проверяющие - список проверяющих.", "/аукционер @ - назначить/снять аукционера.", "/аукционеры - список аукционеров.", "/cpromo - редактор промокодов.", "/voice (ответом) - рассылка сообщения с фото.", "/экс карта @ <название> - выдать эксклюзивную карту.", "/забрать карту @ <название> - забрать эксклюзивную карту.", "/setkto @ <слова> <номер чата> - поставить статус «кто я».", "/чаты - список бесед бота.", "бр форум <ссылка> / бр админы <ссылка> - установить ссылки.", "/firstlogin, /lastlogin, /topmsg, /topemj, /rbrak - служебный занос данных."]
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
        except: users_data = []
        for u in users_data:
            bd = (u.get("bdate") or "").strip()
            if bd:
                bdate_map[u["id"]] = bd
                with DB_LOCK: CONN.execute("INSERT OR REPLACE INTO birthdays(user_id, peer_id, bdate, updated_at) VALUES(?,?,?,?)", (u["id"], peer, bd, int(time.time()))); CONN.commit()
def check_birthdays(peer):
    now_msk = get_msk_now(); today_str = now_msk.strftime("%Y-%m-%d"); current_year = now_msk.year
    if get_setting(peer, "last_bday_check_date", "") == today_str: return
    sync_members(peer)
    with DB_LOCK: member_ids = [r["user_id"] for r in CONN.execute("SELECT user_id FROM members WHERE peer_id=?", (peer,)).fetchall()]
    if not member_ids: set_setting(peer, "last_bday_check_date", today_str); return
    bdate_map = get_bdate_map(member_ids)
    for user_id in member_ids:
        bdate = bdate_map.get(user_id)
        if not bdate: continue
        parts = bdate.split(".")
        if len(parts) >= 2 and int(parts[0]) == now_msk.day and int(parts[1]) == now_msk.month:
            with DB_LOCK: row = CONN.execute("SELECT 1 FROM birthday_congratulated WHERE user_id=? AND peer_id=? AND year=?", (user_id, peer, current_year)).fetchone()
            if row: continue
            if user_id == LEADER_ID: text = LEADER_BDAY_TEXT.format(mention=mention(user_id))
            else:
                custom = get_setting(peer, "birthday_text", ""); text = (custom.rstrip() + "\n\n" + mention(user_id)) if custom else DEFAULT_BDAY_TEXT.format(mention=mention(user_id))
            send_msg(peer, text)
            with DB_LOCK: CONN.execute("INSERT OR REPLACE INTO birthday_congratulated(user_id, peer_id, year, congratulated_at) VALUES(?,?,?,?)", (user_id, peer, current_year, int(time.time()))); CONN.commit()
    set_setting(peer, "last_bday_check_date", today_str)

def execute_top_clean(peer, targets, top_types):
    with DB_LOCK:
        if targets:
            for t in targets:
                for field in top_types: CONN.execute("UPDATE message_stats SET {}=0 WHERE user_id=? AND peer_id=?".format(field), (t, peer))
        else:
            for field in top_types: CONN.execute("UPDATE message_stats SET {}=0 WHERE peer_id=?".format(field), (peer,))
        CONN.commit()

def get_help_main_buttons():
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Общие", "payload": json.dumps({"cmd": "help_general"})}, "color": "primary"}, {"action": {"type": "callback", "label": "Системы MD", "payload": json.dumps({"cmd": "help_systems"})}, "color": "negative"}], [{"action": {"type": "callback", "label": "BLACK RUSSIA", "payload": json.dumps({"cmd": "help_br"})}, "color": "positive"}, {"action": {"type": "callback", "label": "Управление", "payload": json.dumps({"cmd": "help_manage"})}, "color": "negative"}], [{"action": {"type": "callback", "label": "Игровые", "payload": json.dumps({"cmd": "help_games"})}, "color": "positive"}, {"action": {"type": "callback", "label": "MD", "payload": json.dumps({"cmd": "help_md"})}, "color": "negative"}]]}
def get_help_systems_buttons(): return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Напоминалка", "payload": json.dumps({"cmd": "help_remind"})}, "color": "primary"}, {"action": {"type": "callback", "label": "Опросы", "payload": json.dumps({"cmd": "help_polls"})}, "color": "primary"}], [{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_back"})}, "color": "secondary"}]]}
def get_help_manage_buttons(): return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Владелец", "payload": json.dumps({"cmd": "help_owner"})}, "color": "negative"}, {"action": {"type": "callback", "label": "Главный Админ", "payload": json.dumps({"cmd": "help_main_admin"})}, "color": "negative"}], [{"action": {"type": "callback", "label": "Администратор", "payload": json.dumps({"cmd": "help_admin"})}, "color": "negative"}, {"action": {"type": "callback", "label": "Модератор", "payload": json.dumps({"cmd": "help_moderator"})}, "color": "negative"}], [{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_back_main"})}, "color": "secondary"}]]}
def get_help_back_button(): return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_back"})}, "color": "secondary"}]]}
def get_help_back_to_manage(): return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_manage"})}, "color": "secondary"}]]}
def get_help_back_to_systems(): return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Назад🌀", "payload": json.dumps({"cmd": "help_systems"})}, "color": "secondary"}]]}

HELP_GENERAL_TEXT = ("👥 Общие:\n\nОсновные💻:\n1. Мд админы — список руководителей чата.\n2. Мд участник — твоя статистика.\n3. Мд ник — установить ник.\n4. Мд ники — список ников участников.\n5. Мд участники — список всех участников.\n6. Мд статусы — список статусов.\n7. Мд топ — топы чата.\n8. Мд онлайн — кто сейчас онлайн.\n9. Мд правила — правила чата.\n10. Мд редактор карты — редактор личной карточки.\n\nИнформационные💼:\n1. Мд парк — информация об автопарке.\n2. Мд прем — информация о премиях.\n3. Мд чат — ссылка на чат для отчетов.\n4. Мд бр форум — ссылка на форум BR.\n5. Мд бр админы — таблица администрации BR BLUE.\n\nРазвлекательные🎭:\n1. Мд браки — список браков.\n2. Мд др — ближайшие дни рождения.\n3. Мд кто <слово> — кто является словом.\n4. Мд кто я — кто ты сегодня.\n5. Мд инфа <текст> — рандомные проценты.\n6. Мд монетка — орёл или решка.\n7. Мд значки — список значков.\n8. Мд значок — установить/посмотреть значок.\n9. Мд удалить значок — удалить значок.")
HELP_ADMIN_TEXT = ("🛡 Команды Администратора:\n1. Мд ник [@юз] <имя> — установить ник другому.\n2. Мд номер чата — узнать ID чата.\n3. Мд проверка [@юз] — история наказаний.\n4. Мд тишина / тишина офф.\n5. Мд назначить @игрок <ранг> — ранг 1.\n6. Мд снять @игрок — снять роль.\n7. Мд чистка @игрок <число> — удалить сообщения (макс 50, КД 30 сек).\n8. Мд карта — своя карта (чужие смотрят только проверяющие через /card).\nИмеет возможности прошлых ролей.")
HELP_REMIND_TEXT = ("🔔 Напоминалка:\n1. Мд создать <название> <минуты> [кол-во]\n2. Мд список\n3. Мд удалить <название/номер>\n4. Мд редактировать <название/номер> <минуты>\n5. Мд отключить / включить\n6. Мд развернуть <название/номер>")
HELP_OWNER_TEXT = ("👑 Команды владельца:\n1. Мд адмчат <id> / удалить\n2. Мд лимит предов <число>\n3. Мд кд предов <дней>\n4. Мд текст др — текст поздравления.\n5. Мд назначить @игрок <1-4>\n6. Мд снять @игрок\nИмеет возможности прошлых ролей.")
HELP_POLLS_TEXT = ("📢 Система опросов:\n🛡️Админские:\n1. Мд голоса / голоса вчера\n2. Мд защита / -защита [@юз]\n🤴Владельца:\n1. Мд старт/стоп контроль\n2. Мд время опросов <ЧЧ:ММ> <ЧЧ:ММ>\n3. Мд проверка опроса <ЧЧ:ММ>")
HELP_BR_TEXT = ("🎮 BLACK RUSSIA:\n\nℹ️Информационные:\n1. Мд бр — список серверов и онлайн.\n2. Мд бр форум — ссылка на форум Black Russia🎮.\n3. Мд бр админы — актуальная таблица администрации BR BLUE🔹.\n\n🗃️Личная карточка:\n1. Мд карта — выводит фото карты.\n2. Мд редактор карты — редактирование: данные, цвет, фото, текст, эксклюзив.\n3. Мд очистить карту [параметр] — очистить свою карту.\n(параметры: бизнесы, недвижимость, имущество, гараж, телефон, фото, имя.\n(если не указать то очистит все кроме цвета).\n\nЖелательно использовать в лс бота, чтобы не засорять чат😉")
HELP_MODERATOR_TEXT = ("👮‍️ Команды Модератора:\n1. Мд пред [@юз] причина — выдать пред.\n2. Мд снять пред [@юз] — снять пред.\n3. Мд бан [@юз] [дни/навсегда] — забанить.\n4. Мд разбан [@юз] — разбанить.\n5. Мд баны — список забаненных.\n6. Мд мут [@юз] <минуты> причина — выдать мут.\n7. Мд снять мут [@юз] — снять мут.\n8. Мд муты — список замученных.\n9. Мд преды — список предупреждений.\n10. Мд айди [@юз] — настоящий айди страницы.\nНаказания только для участников ниже рангом.")
HELP_MAIN_ADMIN_TEXT = ("🥷 Команды Главного Админа:\n1. Мд статус @игрок <номер>\n2. Мд статус создать/удалить/редактировать/снять\n3. Мд +правила / -правила (ответом)\n4. Мд +приветствие / -приветствие (ответом)\n5. Мд запретить игры / разрешить игры\n6. Мд очистить топ [@игроки] [тип]\n7. Мд запретить редактор / разрешить редактор\nИмеет возможности прошлых ролей.")
HELP_GAMES_TEXT = ("🎯 Игровые команды:\n1. Мд кости @игрок — пригласить игрока бросить кости. 🎲\nПобедитель выбирает наказание проигравшему:\n• 🔇 Мут на 30 минут\n• 📢 Упоминать каждые 60 мин, 5 часов\n• 🕊 Помиловать\n2. Мд кнб @игрок — камень, ножницы, бумага ✊✌️✋\nЗа проигрыш в КНБ наказания нет.")
HELP_MD_TEXT = ("👊 Основной состав MD:\n1. Мд объява — объявление во все чаты.\n🛡️ Админские:\n1. Мд кд объяв <минуты>\n2. Мд объявы — вкл/выкл объявления.")

MAIN_CARD_TEXT = "Какую информацию вы хотите отредактировать в личной карточке?"
DESIGN_PHOTO_TEXT = ("Если хотите установить свою фотографию — отправьте её в чат.\nЕсли вернуть дефолтную — нажмите кнопку «Дефолт».")
CLEAR_CONFIRM_TEXT = "Вы уверены? Будет очищено все кроме цвета. Напишите «подтвердить» или «отказаться»."
def bus_menu_text(page=1): return ("Какой бизнес вы хотите добавить? (стр. {}/{})\n(Слоты: АЗС 1 | ТК БУС/ТК БАТ/СК/Такопарк 1 | остальные 2. Один бизнес макс. 2 шт., Такопарк занимает 2 слота!)").format(page, BUS_PAGES)
def design_colors_text(page=1): return "Выберите цвет карточки (стр. {}/{}):".format(page, design_pages_count())

def text_colors_kb(sel_cmd, menu_cmd, page=1, back_cmd="card_text_menu", none_target=None, sel_target=None):
    pages = text_color_pages(); page = max(1, min(page, pages)); chunk = TEXT_COLOR_ORDER[(page - 1) * TEXT_PER_PAGE: page * TEXT_PER_PAGE]
    rows = []; line = []
    for key, lab in chunk:
        pay = {"cmd": sel_cmd, "key": key, "p": page, "m": menu_cmd}
        if sel_target: pay["target"] = sel_target
        line.append({"action": {"type": "callback", "label": lab, "payload": json.dumps(pay)}, "color": "secondary"})
        if len(line) == 3: rows.append(line); line = []
    if line: rows.append(line)
    nav = []
    if page > 1: nav.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": menu_cmd, "p": page - 1})}, "color": "primary"})
    if page < pages: nav.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": menu_cmd, "p": page + 1})}, "color": "primary"})
    last = []
    if none_target: last.append({"action": {"type": "callback", "label": "Убрать", "payload": json.dumps({"cmd": "card_outline_clear", "target": none_target, "m": menu_cmd})}, "color": "negative"})
    last.append({"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": back_cmd})}, "color": "secondary"})
    rows.append(nav + last); return {"inline": True, "buttons": rows}

CARD_EDIT_ENTRIES = [("biz","Бизнесы"),("realty","Недвижимость"),("prop","Имущество"),("garage","Гараж"),("phone","Телефон"),("name","Имя"),("design_colors","Цвет карточки"),("design_photo","Фото карточки"),("text_format","Текст"),("exclusive","Эксклюзив")]
CARD_EDIT_PER_PAGE = 6
def card_edit_pages(): return max(1, -(-len(CARD_EDIT_ENTRIES) // CARD_EDIT_PER_PAGE))
def card_edit_page_kb(p=1):
    pages = card_edit_pages(); p = max(1, min(p, pages)); chunk = CARD_EDIT_ENTRIES[(p - 1) * CARD_EDIT_PER_PAGE: p * CARD_EDIT_PER_PAGE]
    rows = []
    for i in range(0, len(chunk), 2):
        pair = chunk[i:i+2]
        rows.append([{"action": {"type": "callback", "label": lab, "payload": json.dumps({"cmd": "card_edit_entry", "f": key, "p": p})}, "color": "primary"} for key, lab in pair])
    nav = []
    if p > 1: nav.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "card_edit_menu", "p": p - 1})}, "color": "secondary"})
    if p < pages: nav.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "card_edit_menu", "p": p + 1})}, "color": "secondary"})
    if nav: rows.append(nav)
    rows.append([{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"}])
    return {"inline": True, "buttons": rows}
def card_edit_main_kb(): return card_edit_page_kb(1)

def text_menu_kb():
    return {"inline": True, "buttons": [
        [{"action": {"type": "callback", "label": "Жирный шрифт", "payload": json.dumps({"cmd": "card_text_bold"})}, "color": "primary"}, {"action": {"type": "callback", "label": "Обычный шрифт", "payload": json.dumps({"cmd": "card_text_normal"})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Цвет имени", "payload": json.dumps({"cmd": "card_text_name_colors"})}, "color": "secondary"}, {"action": {"type": "callback", "label": "Цвет полей", "payload": json.dumps({"cmd": "card_text_field_colors"})}, "color": "secondary"}],
        [{"action": {"type": "callback", "label": "Обводка", "payload": json.dumps({"cmd": "card_text_outline"})}, "color": "secondary"}, {"action": {"type": "callback", "label": "Положение", "payload": json.dumps({"cmd": "card_text_pos"})}, "color": "secondary"}],
        [{"action": {"type": "callback", "label": "📏 Размер", "payload": json.dumps({"cmd": "card_text_size"})}, "color": "primary"}, {"action": {"type": "callback", "label": "🎨 Свой Цвет", "payload": json.dumps({"cmd": "card_custom_color_menu"})}, "color": "primary"}],
        [{"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_edit_menu", "p": 2})}, "color": "secondary"}]]}

def text_pos_menu_kb():
    items = [("biz","Бизнесы"),("realty","Недвижимость"),("prop","Имущество"),("garage","Гараж"),("phone","Телефон"),("name","Имя")]
    rows = []
    for i in range(0, len(items), 2): rows.append([{"action": {"type": "callback", "label": lab, "payload": json.dumps({"cmd": "card_pos_menu", "f": key})}, "color": "primary"} for key, lab in items[i:i+2]])
    rows.append([{"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_text_menu"})}, "color": "secondary"}])
    return {"inline": True, "buttons": rows}
def pos_adjust_kb(f):
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "⬆️ Вверх", "payload": json.dumps({"cmd": "card_pos_move", "f": f, "dir": "up"})}, "color": "primary"}, {"action": {"type": "callback", "label": "⬇️ Вниз", "payload": json.dumps({"cmd": "card_pos_move", "f": f, "dir": "down"})}, "color": "primary"}], [{"action": {"type": "callback", "label": "⬅️ Влево", "payload": json.dumps({"cmd": "card_pos_move", "f": f, "dir": "left"})}, "color": "primary"}, {"action": {"type": "callback", "label": "➡️ Вправо", "payload": json.dumps({"cmd": "card_pos_move", "f": f, "dir": "right"})}, "color": "primary"}], [{"action": {"type": "callback", "label": "Сброс", "payload": json.dumps({"cmd": "card_pos_reset", "f": f})}, "color": "negative"}, {"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_text_pos"})}, "color": "secondary"}]]}
def outline_target_kb():
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Имя", "payload": json.dumps({"cmd": "card_outline_name"})}, "color": "primary"}, {"action": {"type": "callback", "label": "Поля", "payload": json.dumps({"cmd": "card_outline_fields"})}, "color": "primary"}], [{"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_text_menu"})}, "color": "secondary"}]]}
def ex_back_kb(): return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_edit_menu", "p": 2})}, "color": "secondary"}]]}
def card_bus_kb(page=1):
    page = max(1, min(page, BUS_PAGES)); types = BUS_TYPES_ORDER[(page - 1) * BUS_PER_PAGE: page * BUS_PER_PAGE]; rows = []
    for i in range(0, len(types), 3): rows.append([{"action": {"type": "callback", "label": t, "payload": json.dumps({"cmd": "card_bus", "t": t, "type": t, "p": page})}, "color": "secondary"} for t in types[i:i+3]])
    nav = []
    if page > 1: nav.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "card_bus_menu", "p": page - 1})}, "color": "primary"})
    if page < BUS_PAGES: nav.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "card_bus_menu", "p": page + 1})}, "color": "primary"})
    nav.append({"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_edit_menu", "p": 1})}, "color": "primary"})
    nav.append({"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"})
    rows.append(nav); return {"inline": True, "buttons": rows}
def card_realty_kb():
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Дом", "payload": json.dumps({"cmd": "card_realty", "t": "Дом", "type": "Дом"})}, "color": "secondary"}, {"action": {"type": "callback", "label": "Квартира", "payload": json.dumps({"cmd": "card_realty", "t": "Квартира", "type": "Квартира"})}, "color": "secondary"}], [{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"}, {"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_edit_menu", "p": 1})}, "color": "primary"}]]}
def card_input_kb(back_cmd, back_page=None):
    back_payload = {"cmd": back_cmd}
    if back_page: back_payload["p"] = back_page
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"}, {"action": {"type": "callback", "label": "Назад", "payload": json.dumps(back_payload)}, "color": "primary"}]]}
def design_colors_kb(page=1):
    pages = design_pages_count(); page = max(1, min(page, pages)); chunk = COLORS_ORDER[(page - 1) * DESIGN_PER_PAGE: page * DESIGN_PER_PAGE]; rows = []
    for i in range(0, len(chunk), 2): rows.append([{"action": {"type": "callback", "label": lab, "payload": json.dumps({"cmd": "card_design_color", "key": key, "p": page})}, "color": "secondary"} for key, lab in chunk[i:i+2]])
    nav = []
    if page > 1: nav.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "card_design_colors", "p": page - 1})}, "color": "primary"})
    if page < pages: nav.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "card_design_colors", "p": page + 1})}, "color": "primary"})
    nav.append({"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_edit_menu", "p": 2})}, "color": "primary"})
    nav.append({"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"})
    rows.append(nav); return {"inline": True, "buttons": rows}
def design_photo_kb():
    return {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Дефолт", "payload": json.dumps({"cmd": "card_design_default"})}, "color": "primary"}, {"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_edit_menu", "p": 2})}, "color": "primary"}, {"action": {"type": "callback", "label": "Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"}]]}

def expire_stale_games(peer):
    now = int(time.time())
    with DB_LOCK:
        CONN.execute("UPDATE dice_games SET state='expired' WHERE peer_id=? AND state='pending' AND created_at<=?", (peer, now - 60))
        CONN.execute("UPDATE dice_games SET state='expired' WHERE peer_id=? AND state='playing' AND created_at<=?", (peer, now - 600))
        CONN.execute("UPDATE kmb_games SET state='expired' WHERE peer_id=? AND state IN ('pending','choosing') AND created_at<=?", (peer, now - 300))
        CONN.commit()

def open_edit_menu(peer, sender):
    close_existing_editors(peer, sender)
    msg_id = None
    try: msg_id = VK.messages.send(peer_id=peer, message="{} (стр. 1/{}):".format(MAIN_CARD_TEXT, card_edit_pages()), keyboard=json.dumps(card_edit_page_kb(1)), random_id=random.getrandbits(31))
    except Exception as e: print("open_edit_menu kb send fail:", e)
    if msg_id is None:
        try: msg_id = VK.messages.send(peer_id=peer, message=MAIN_CARD_TEXT, random_id=random.getrandbits(31))
        except Exception as e: print("open_edit_menu plain send fail:", e)
    if msg_id is None: send_msg(peer, "❌ Не удалось открыть редактор карты (VK отклонил сообщение)."); return
    cmid = resolve_cmid_retry(peer, msg_id); set_card_state(sender, peer, "edit_menu", {"msg_cmid": cmid, "msg_id": msg_id, "p": 1})

def handle_event(event):
    try:
        obj = event.object if hasattr(event, 'object') else event.obj
        if not isinstance(obj, dict): return
        event_id = obj.get("event_id"); user_id = int(obj.get("user_id", 0)); peer_id = int(obj.get("peer_id", 0))
        payload = obj.get("payload", "{}")
        if isinstance(payload, str):
            try: payload = json.loads(payload)
            except: payload = {}
        cmd = payload.get("cmd", ""); cmid = obj.get("conversation_message_id")
        def snackbar(text):
            try: VK.messages.sendMessageEventAnswer(event_id=event_id, user_id=user_id, peer_id=peer_id, event_data=json.dumps({"type": "show_snackbar", "text": text}))
            except: pass
        def edit_msg(text, kb=None):
            kbj = json.dumps(kb) if kb else json.dumps({"inline": True, "buttons": []})
            if cmid:
                try: VK.messages.edit(peer_id=peer_id, conversation_message_id=cmid, message=text, keyboard=kbj); return True
                except Exception as e: LAST_ERR["msg"] = str(e)
            return send_msg(peer_id, text, keyboard=kb)
        def show(text, kb):
            ok = edit_msg(text, kb)
            if not ok: snackbar("❌ VK: {}".format(LAST_ERR["msg"][:70]))
            return ok
        def set_state(step, extra=None):
            c = dict(extra or {}); c["msg_cmid"] = cmid; set_card_state(user_id, peer_id, step, c)

        # ===== CALLBACK ДЛЯ /voice =====
        if cmd.startswith("voice_"):
            state = get_auction_state(user_id, peer_id)
            if cmd == "voice_cancel":
                if state: clear_auction_state(user_id, peer_id)
                show("❌ Рассылка отменена.", None); snackbar("❌ Отменено"); return
            if not state or state["step"] not in ("voice_menu", "voice_wait_peer"):
                snackbar("⛔ Меню рассылки устарело, напишите /voice заново"); return
            ctx = state.get("context", {}); rtext = ctx.get("reply_text", ""); att = ctx.get("reply_att", "")
            if cmd == "voice_all_chats":
                clear_auction_state(user_id, peer_id); show("⏳ Начинаю рассылку по чатам...", None)
                chats = get_all_bot_chats(); ok = 0
                for t in chats:
                    try:
                        if att: send_msg(t, rtext, attachments=att)
                        else: send_msg(t, rtext)
                        ok += 1; time.sleep(0.3)
                    except: pass
                send_msg(peer_id, f"✅ Рассылка по чатам завершена. Успешно: {ok}/{len(chats)}"); return
            elif cmd == "voice_one_chat":
                set_auction_state(user_id, peer_id, "voice_wait_peer", ctx)
                show("📝 Введите номер чата (2xxxxxxxxx):", {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "❌ Отмена", "payload": json.dumps({"cmd": "voice_cancel"})}, "color": "negative"}]]}); snackbar("📝 Жду номер чата"); return
            elif cmd == "voice_all_users":
                clear_auction_state(user_id, peer_id); show("⏳ Начинаю рассылку в ЛС пользователям...", None)
                user_ids = set()
                with DB_LOCK:
                    for row in CONN.execute("SELECT from_id FROM message_cache WHERE from_id > 0").fetchall(): user_ids.add(row["from_id"])
                    for row in CONN.execute("SELECT user_id FROM members WHERE user_id > 0").fetchall(): user_ids.add(row["user_id"])
                ok = 0
                for uid in user_ids:
                    try:
                        if att: send_msg(uid, rtext, attachments=att)
                        else: send_msg(uid, rtext)
                        ok += 1; time.sleep(0.2)
                    except: pass
                send_msg(peer_id, f"✅ Рассылка в ЛС завершена. Успешно: {ok}/{len(user_ids)} (VK не дает писать тем, кто ни разу не писал боту)"); return
        # ===================================

        # ===== ПРОМОКОДЫ: КОЛБЭКИ =====
        if cmd.startswith("promo_"):
            if user_id not in (CREATOR_ID, LEADER_ID): snackbar("⛔ Недоступно!"); return
            state = get_auction_state(user_id, peer_id)
            if cmd == "promo_cancel":
                if state: clear_auction_state(user_id, peer_id)
                show("❌ Редактор промокодов закрыт.", None); snackbar("❌ Закрыто"); return
            if cmd == "promo_active_list":
                txt = build_promo_active_text()
                if txt is None:
                    show("📊 Активных промокодов нет.", promo_menu_kb()); snackbar("📊 Пусто")
                else:
                    show(txt, promo_menu_kb()); snackbar("📊 Готово")
                return
            if cmd == "promo_create":
                set_auction_state(user_id, peer_id, "promo_kind", {"msg_cmid": cmid}); show("На что будет промокод?", promo_kind_kb()); snackbar("✅ Выберите"); return
            if cmd == "promo_del_btn":
                set_auction_state(user_id, peer_id, "promo_del", {"msg_cmid": cmid}); show("Введите название промокода который нужно удалить:", promo_cancel_kb()); snackbar("✅ Введите"); return
            if cmd == "promo_kind_ex":
                if not state: snackbar("⛔ Редактор не открыт"); return
                ctx = state.get("context", {}); ctx["kind"] = "excard"; ctx["msg_cmid"] = cmid
                set_auction_state(user_id, peer_id, "promo_card", ctx); show("Введите название карты:", promo_cancel_kb()); snackbar("✅ Введите"); return
            if cmd == "promo_type_act":
                if not state: snackbar("⛔ Редактор не открыт"); return
                ctx = state.get("context", {}); ctx["msg_cmid"] = cmid
                set_auction_state(user_id, peer_id, "promo_limit", ctx); show("Введите число: сколько людей смогут использовать промокод:", promo_cancel_kb()); snackbar("✅ Введите"); return
            if cmd == "promo_type_time":
                if not state: snackbar("⛔ Редактор не открыт"); return
                ctx = state.get("context", {}); ctx["msg_cmid"] = cmid
                set_auction_state(user_id, peer_id, "promo_expire", ctx); show("Введите дату и время до окончания действия промокода (пример: 26.06.25 11:23):", promo_cancel_kb()); snackbar("✅ Введите"); return
            snackbar("❌ Неизвестная кнопка промо"); return

        # ===== АУКЦИОНЫ: КОЛБЭКИ =====
        if cmd.startswith("auction_"):
            if not (is_auctioneer(user_id) or user_id in (CREATOR_ID, LEADER_ID)): snackbar("⛔ Вы не аукционер!"); return
            state = get_auction_state(user_id, peer_id)
            if cmd == "auction_cancel":
                if state: clear_auction_state(user_id, peer_id)
                show("❌ Редактор аукционов закрыт.", None); snackbar("❌ Закрыто"); return
            if cmd == "auction_skip_photo":
                if not state or state["step"] not in ("create_photo", "add_lot_photo", "edit_lot_photo"): snackbar("⛔ Сейчас не ожидается фото!"); return
                ctx = state.get("context", {})
                if time.time() - ctx.get("ts", 0) > 300: clear_auction_state(user_id, peer_id); snackbar("⏳ Время вышло"); return
                mode = ctx.get("photo_mode", "create")
                if mode == "create":
                    ctx["lots"][-1]["photo_path"] = ""; ctx["lots"][-1]["photo_att"] = ""
                    if len(ctx["lots"]) < ctx["count"]:
                        ctx["msg_cmid"] = cmid; set_auction_state(user_id, peer_id, "create_lot", ctx); txt, kb = auction_prompt("create_lot", ctx); show(txt, kb)
                    else:
                        aid = create_auction(ctx["peer_id"], ctx["name"], ctx["dt"], user_id)
                        for i, l in enumerate(ctx["lots"], 1): add_lot(aid, i, l["name"], l["min_price"], l.get("seller", ""), l.get("photo_path", ""), l.get("photo_att", ""))
                        clear_auction_state(user_id, peer_id); show("✅ Аукцион «{}» создан в чате {}! Лотов: {}.\n\nВыберите действие:".format(ctx["name"], ctx["peer_id"], len(ctx["lots"])), auction_main_kb())
                elif mode == "add":
                    lots = get_lots(ctx["auction_id"]); num = (max([l["lot_number"] for l in lots]) + 1) if lots else 1
                    add_lot(ctx["auction_id"], num, ctx["add_name"], ctx["add_price"], ctx.get("add_seller", ""), "", "")
                    a = get_auction(ctx["auction_id"]); set_auction_state(user_id, peer_id, "edit_menu", {"auction_id": a["id"], "msg_cmid": cmid})
                    show("✅ Лот добавлен.\n\n" + edit_menu_text(a) + "\n\nВыберите что хотите отредактировать:", edit_menu_kb(a["id"]))
                else:
                    with DB_LOCK: CONN.execute("UPDATE auction_lots SET name=?, min_price=?, seller=? WHERE id=?", (ctx["edit_name"], ctx["edit_price"], ctx.get("edit_seller", ""), ctx["lot_id"])); CONN.commit()
                    a = get_auction(ctx["auction_id"]); set_auction_state(user_id, peer_id, "edit_menu", {"auction_id": ctx["auction_id"], "msg_cmid": cmid})
                    if a: show("✅ Лот отредактирован (фото осталось старое).\n\n" + edit_menu_text(a) + "\n\nВыберите что хотите отредактировать:", edit_menu_kb(a["id"]))
                    else: show("✅ Лот отредактирован.\n\nВыберите действие:", auction_main_kb())
                snackbar("✅ Пропущено"); return
            if not state: snackbar("⛔ Редактор не открыт или время вышло! Напишите /аукцион"); return
            ctx = state.get("context", {})
            if time.time() - ctx.get("ts", 0) > 300: clear_auction_state(user_id, peer_id); snackbar("⏳ Время редактора вышло (5 мин)"); return
            def aset(step, extra=None):
                c = dict(extra or {}); c["msg_cmid"] = cmid; set_auction_state(user_id, peer_id, step, c)
            try:
                if cmd == "auction_menu_show": aset("menu"); show("Выберите действие:", auction_main_kb()); snackbar("✅ Меню")
                elif cmd == "auction_back":
                    to = payload.get("to", "")
                    if to == "menu": aset("menu"); show("Выберите действие:", auction_main_kb()); snackbar("⬅️ Назад"); return
                    if to == "create_lot_pop":
                        if ctx.get("lots"): ctx["lots"].pop()
                        to = "create_lot"
                    if to == "edit_menu_show":
                        a = get_auction(ctx.get("auction_id", 0))
                        if not a: snackbar("❌ Аукцион не найден"); return
                        aset("edit_menu", {"auction_id": a["id"]}); show(edit_menu_text(a) + "\n\nВыберите что хотите отредактировать:", edit_menu_kb(a["id"])); snackbar("⬅️ Назад"); return
                    if to in AUCTION_STEPS: aset(to, ctx); txt, kb = auction_prompt(to, ctx); show(txt, kb); snackbar("⬅️ Назад"); return
                    snackbar("❌ Неизвестный шаг")
                elif cmd == "auction_active": aset("active_peer"); txt, kb = auction_prompt("active_peer", ctx); show(txt, kb); snackbar("✅ Введите чат")
                elif cmd == "auction_create": aset("create_peer"); txt, kb = auction_prompt("create_peer", ctx); show(txt, kb); snackbar("✅ Введите чат")
                elif cmd == "auction_delete": aset("delete_peer"); txt, kb = auction_prompt("delete_peer", ctx); show(txt, kb); snackbar("✅ Введите чат")
                elif cmd == "auction_edit": aset("edit_peer"); txt, kb = auction_prompt("edit_peer", ctx); show(txt, kb); snackbar("✅ Введите чат")
                elif cmd == "auction_announce": aset("announce_peer"); txt, kb = auction_prompt("announce_peer", ctx); show(txt, kb); snackbar("✅ Введите чат")
                elif cmd == "auction_control": aset("control_peer"); txt, kb = auction_prompt("control_peer", ctx); show(txt, kb); snackbar("✅ Введите чат")
                elif cmd == "auction_control_set":
                    pid = int(payload.get("peer", 0)); val = int(payload.get("val", 0)); cur = get_setting(0, "auc_clean_{}".format(pid), "0"); want = "1" if val else "0"
                    if cur == want: show("ℹ️ В чате {} уже {}.".format(pid, "включено" if want == "1" else "выключено"), auction_main_kb()); snackbar("ℹ️ Уже так"); return
                    set_setting(0, "auc_clean_{}".format(pid), want); aset("menu"); show("✅ Контроль в чате {} теперь {}.\n\nВыберите действие:".format(pid, "включен" if want == "1" else "выключен"), auction_main_kb()); snackbar("✅ Готово")
                elif cmd == "auction_view":
                    a = get_auction(payload.get("id", 0))
                    if not a: snackbar("❌ Аукцион не найден"); return
                    lots = get_lots(a["id"]); lines = ["{} | {}".format(a["datetime_str"].replace(" ", " | "), a["name"]), "Лоты:"]
                    for i, l in enumerate(lots, 1): lines.append("{}. {} (мин. {}, продавец: {})".format(i, l["name"], fmt_rub(l["min_price"]), l.get("seller") or "не указан"))
                    if len(lots) > 8: lines.append("(фото кнопками — первые 8 лотов)")
                    show("\n".join(lines), auction_lots_kb(lots, "auction_menu_show")); snackbar("✅ Аукцион")
                elif cmd == "auction_lotphoto":
                    lot = get_lot(payload.get("id", 0))
                    if not lot: snackbar("❌ Лот не найден"); return
                    att = lot.get("photo_att") or ""
                    if not att and lot.get("photo_path") and os.path.isfile(lot["photo_path"]):
                        att = upload_photo_file(peer_id, lot["photo_path"]) or ""
                        if att:
                            with DB_LOCK: CONN.execute("UPDATE auction_lots SET photo_att=? WHERE id=?", (att, lot["id"])); CONN.commit()
                    if not att: snackbar("❌ Фото лота нет"); return
                    send_msg(peer_id, "📷 Фото лота «{}»:".format(lot["name"]), attachments=att); snackbar("📷 Фото отправлено")
                elif cmd in ("auction_del_sel", "auction_del_auction"):
                    a = get_auction(payload.get("id", 0))
                    if not a: snackbar("❌ Аукцион не найден"); return
                    delete_auction(a["id"]); aset("menu"); show("✅ Аукцион «{}» удалён.\n\nВыберите действие:".format(a["name"]), auction_main_kb()); snackbar("✅ Удалён")
                elif cmd == "auction_edit_show":
                    a = get_auction(payload.get("id", 0))
                    if not a: snackbar("❌ Аукцион не найден"); return
                    aset("edit_menu", {"auction_id": a["id"]}); show(edit_menu_text(a) + "\n\nВыберите что хотите отредактировать:", edit_menu_kb(a["id"])); snackbar("✅ Редактор")
                elif cmd == "auction_edit_dt":
                    c = {"auction_id": payload.get("id", 0)}; aset("edit_dt", c); txt, kb = auction_prompt("edit_dt", c); show(txt, kb); snackbar("✅ Введите дату")
                elif cmd == "auction_edit_name":
                    c = {"auction_id": payload.get("id", 0)}; aset("edit_name", c); txt, kb = auction_prompt("edit_name", c); show(txt, kb); snackbar("✅ Введите название")
                elif cmd == "auction_edit_lot":
                    c = {"auction_id": payload.get("id", 0)}; aset("edit_lot_num", c); txt, kb = auction_prompt("edit_lot_num", c); show(txt, kb); snackbar("✅ Введите номер")
                elif cmd == "auction_lot_del":
                    lot = get_lot(payload.get("id", 0))
                    if not lot: snackbar("❌ Лот не найден"); return
                    delete_lot(lot["id"]); a = get_auction(lot["auction_id"])
                    if a: aset("edit_menu", {"auction_id": a["id"]}); show("✅ Лот удалён.\n\n" + edit_menu_text(a) + "\n\nВыберите что хотите отредактировать:", edit_menu_kb(a["id"]))
                    else: aset("menu"); show("✅ Лот удалён.\n\nВыберите действие:", auction_main_kb())
                    snackbar("✅ Лот удалён")
                elif cmd == "auction_lot_edit":
                    lot = get_lot(payload.get("id", 0))
                    if not lot: snackbar("❌ Лот не найден"); return
                    c = {"auction_id": lot["auction_id"], "lot_id": lot["id"]}; aset("edit_lot_data", c); txt, kb = auction_prompt("edit_lot_data", c); show(txt, kb); snackbar("✅ Введите данные")
                elif cmd == "auction_add_lot":
                    c = {"auction_id": payload.get("id", 0), "photo_mode": "add"}; aset("add_lot_data", c); txt, kb = auction_prompt("add_lot_data", c); show(txt, kb); snackbar("✅ Введите лот")
                elif cmd == "auction_ann_sel":
                    a = get_auction(payload.get("id", 0))
                    if not a: snackbar("❌ Аукцион не найден"); return
                    lots = get_lots(a["id"]); lines = ["@all Лоты на аукцион {}.\n".format(a["datetime_str"])]
                    for i, l in enumerate(lots, 1): lines.append("{}) {}".format(i, l["name"]))
                    send_msg(a["peer_id"], "\n".join(lines)); aset("menu"); show("✅ Анонс отправлен в чат {}.\n\nВыберите действие:".format(a["peer_id"]), auction_main_kb()); snackbar("✅ Анонс")
                else: snackbar("❌ Неизвестная кнопка аукциона")
            except Exception as e: print("auction callback error:", e); snackbar("❌ Ошибка аукциона")
            return

        # ===== КАРТОЧКА: КОЛБЭКИ =====
        if cmd.startswith("card_"):
            state = get_card_state(user_id, peer_id)
            if not state: snackbar("⛔ Это не ваше меню или время вышло!"); return
            if cmd == "card_cancel": clear_card_state(user_id, peer_id); show("❌ Редактирование карточки отменено.", None); snackbar("❌ Отменено"); return
            if cmd == "card_finish": clear_card_state(user_id, peer_id); show("✅ Редактирование завершено.", None); snackbar("✅ Готово"); return
            ctx = state.get("context", {})
            if time.time() - ctx.get("ts", 0) > 60:
                clear_card_state(user_id, peer_id); close_card_session(peer_id, ctx, "Время на редактирование вышло, {} вы бездействовали минуту⏳".format(mention(user_id))); snackbar("⏳ Время вышло"); return
            try:
                if cmd in ("card_main", "card_edit_menu", "card_back_main", "card_design_main"):
                    p = int(payload.get("p", 1) or 1); set_state("edit_menu", {"p": p}); pages = card_edit_pages(); p = max(1, min(p, pages)); show("{} (стр. {}/{}):".format(MAIN_CARD_TEXT, p, pages), card_edit_page_kb(p)); snackbar("✅ Меню")
                elif cmd in ("card_edit_entry", "card_edit", "card_field"):
                    f = payload.get("f") or payload.get("field") or ""
                    if f == "biz": set_state("bus_menu", {"p": 1}); show(bus_menu_text(1), card_bus_kb(1))
                    elif f == "realty": set_state("realty_menu"); show("Что вы хотите добавить? (макс. 2 недвижимости)", card_realty_kb())
                    elif f == "prop": set_state("property_input"); show("Введите сумму, в которую оцениваете имущество (только цифры):", card_input_kb("card_edit_menu", 1))
                    elif f == "garage": set_state("garage_input"); show("Введите номер гаража (макс. 4 цифры, без нуля в начале):", card_input_kb("card_edit_menu", 1))
                    elif f == "phone": set_state("phone_input"); show("Введите номер телефона (4–7 цифр, без нуля в начале):", card_input_kb("card_edit_menu", 1))
                    elif f == "name": set_state("name_input"); show("Введите имя формата Имя_Фамилия (англ. буквы, макс. 15+15):", card_input_kb("card_edit_menu", 1))
                    elif f == "design_colors": set_state("design_color", {"p": 1}); show(design_colors_text(1), design_colors_kb(1))
                    elif f == "design_photo": set_state("design_photo_wait"); show(DESIGN_PHOTO_TEXT, design_photo_kb())
                    elif f == "text_format": set_state("edit_menu", {"p": 2}); show("Выберите действия с текстом", text_menu_kb())
                    elif f == "exclusive":
                        set_state("edit_menu", {"p": 2})
                        try: lst = get_excards(user_id)
                        except Exception as _e: print("excards load err:", _e); lst = []
                        if not isinstance(lst, list): lst = []
                        lst = [str(x) for x in lst if x]
                        if not lst:
                            show("У вас пока нет эксклюзивных карт.\nИх можно получить по промокоду: /promo #код.", ex_back_kb())
                        else:
                            per_page = 6
                            try: page = int(payload.get("p", 1))
                            except Exception: page = 1
                            total_pages = max(1, (len(lst) + per_page - 1) // per_page)
                            page = max(1, min(page, total_pages))
                            chunk = lst[(page-1)*per_page : page*per_page]
                            rows = []; line = []
                            for nm in chunk:
                                lab = nm[:18]
                                pay = json.dumps({"cmd": "card_ex_apply", "name": nm})
                                line.append({"action": {"type": "callback", "label": lab, "payload": pay}, "color": "primary"})
                                if len(line) == 2:
                                    rows.append(line); line = []
                            if line: rows.append(line)
                            nav = []
                            if page > 1: nav.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "card_exclusive", "p": page-1})}, "color": "secondary"})
                            nav.append({"action": {"type": "callback", "label": f"{page}/{total_pages}", "payload": json.dumps({"cmd": "page_info"})}, "color": "default"})
                            if page < total_pages: nav.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "card_exclusive", "p": page+1})}, "color": "secondary"})
                            if nav: rows.append(nav)
                            rows.append([{"action": {"type": "callback", "label": "Снять эксклюзив", "payload": json.dumps({"cmd": "card_ex_clear"})}, "color": "negative"}, {"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_edit_menu", "p": 2})}, "color": "secondary"}])
                            show(f"🎩 Ваши эксклюзивные карты (стр. {page}/{total_pages}):", {"inline": True, "buttons": rows})
                    else: snackbar("⚠️ debug payload: {}".format(str(payload)[:80])); return
                    snackbar("✅ Выполнено")
                elif cmd in ("card_bus_menu", "card_back_bus"):
                    p = int(payload.get("p", 1) or 1); set_state("bus_menu", {"p": p}); show(bus_menu_text(p), card_bus_kb(p)); snackbar("✅ Бизнесы")
                elif cmd in ("card_bus", "card_biz_select"):
                    t = payload.get("t") or payload.get("type") or ""; p = int(payload.get("p", 1) or 1); card = get_card(user_id); blist = json.loads(card["businesses"] or "[]")
                    ok, mode = can_add_business(blist, t)
                    if not ok:
                        if mode == "exists": snackbar("ℹ️ «{}» уже есть в карточке".format(t))
                        elif mode == "max2": snackbar("⛔ Максимум 2 одинаковых бизнеса!")
                        else: snackbar("⛔ Нет слотов! Макс 4 бизнеса, Такопарк занимает 2 слота")
                        return
                    if t in BUS_NO_NUM: add_business(user_id, t, None); set_state("bus_menu", {"p": p}); show("✅ Бизнес «{}» добавлен!\n".format(t) + bus_menu_text(p), card_bus_kb(p)); snackbar("✅ Добавлено")
                    else: set_state("biz_input", {"t": t, "p": p}); show("Введите номер для «{}» (макс. 3 цифры, без нуля в начале, напр. 33):".format(t), card_input_kb("card_bus_menu", p)); snackbar("✅ Введите номер")
                elif cmd in ("card_realty_menu", "card_back_realty"): set_state("realty_menu"); show("Что вы хотите добавить? (макс. 2 недвижимости)", card_realty_kb()); snackbar("✅ Недвижимость")
                elif cmd in ("card_realty", "card_realty_select"):
                    t = payload.get("t") or payload.get("type") or ""; card = get_card(user_id); rlist = json.loads(card["realty"] or "[]")
                    if len(rlist) >= 2: snackbar("⛔ Максимум 2 недвижимости!"); return
                    set_state("realty_input", {"t": t}); show("Введите номер для «{}» (макс. 4 цифры, без нуля в начале):".format(t), card_input_kb("card_realty_menu")); snackbar("✅ Введите номер")
                elif cmd == "card_garage": set_state("garage_input"); show("Введите номер гаража (макс. 4 цифры, без нуля в начале):", card_input_kb("card_edit_menu", 1)); snackbar("✅ Введите номер")
                elif cmd == "card_phone": set_state("phone_input"); show("Введите номер телефона (4–7 цифр, без нуля в начале):", card_input_kb("card_edit_menu", 1)); snackbar("✅ Введите номер")
                elif cmd == "card_name": set_state("name_input"); show("Введите имя формата Имя_Фамилия (англ. буквы, макс. 15+15):", card_input_kb("card_edit_menu", 1)); snackbar("✅ Введите имя")
                elif cmd in ("card_prop", "card_property"): set_state("property_input"); show("Введите сумму, в которую оцениваете имущество (только цифры):", card_input_kb("card_edit_menu", 1)); snackbar("✅ Введите сумму")
                elif cmd == "card_design_colors":
                    p = int(payload.get("p", 1) or 1); set_state("design_color", {"p": p}); show(design_colors_text(p), design_colors_kb(p)); snackbar("✅ Цвета")
                elif cmd == "card_design_color":
                    key = payload.get("key", "")
                    if key not in ALL_COLOR_KEYS: snackbar("❌ Неизвестный цвет"); return
                    p = int(payload.get("p", 1) or 1); set_design(user_id, color=key, exclusive=""); set_state("design_color", {"p": p}); show("✅ Цвет применён!\n" + design_colors_text(p), design_colors_kb(p)); snackbar("✅ Цвет применён")
                elif cmd == "card_text_menu": set_state("edit_menu", {"p": 2}); show("Выберите действия с текстом", text_menu_kb()); snackbar("✅ Текст")
                elif cmd == "card_text_bold": set_design(user_id, bold="1"); set_state("edit_menu", {"p": 2}); show("✅ Жирный шрифт включён!\nВыберите действия с текстом", text_menu_kb()); snackbar("✅ Жирный")
                elif cmd == "card_text_normal": set_design(user_id, bold="0"); set_state("edit_menu", {"p": 2}); show("✅ Обычный шрифт включён!\nВыберите действия с текстом", text_menu_kb()); snackbar("✅ Обычный")
                elif cmd in ("card_text_name_colors", "card_name_colors"):
                    p = int(payload.get("p", 1) or 1); set_state("edit_menu", {"p": 2}); show("Выберите цвет имени (стр. {}/{}):".format(p, text_color_pages()), text_colors_kb("card_name_color", "card_text_name_colors", p, "card_text_menu")); snackbar("✅ Цвет имени")
                elif cmd == "card_name_color":
                    key = payload.get("key", ""); p = int(payload.get("p", 1) or 1)
                    if key not in TEXT_COLORS: snackbar("❌ Неизвестный цвет"); return
                    set_design(user_id, name_color=key); set_state("edit_menu", {"p": 2}); show("✅ Цвет имени применён!\nВыберите цвет имени (стр. {}/{}):".format(p, text_color_pages()), text_colors_kb("card_name_color", "card_text_name_colors", p, "card_text_menu")); snackbar("✅ Применено")
                elif cmd in ("card_text_field_colors", "card_field_colors"):
                    p = int(payload.get("p", 1) or 1); set_state("edit_menu", {"p": 2}); show("Выберите цвет полей (стр. {}/{}):".format(p, text_color_pages()), text_colors_kb("card_field_color", "card_text_field_colors", p, "card_text_menu")); snackbar("✅ Цвет полей")
                elif cmd == "card_field_color":
                    key = payload.get("key", ""); p = int(payload.get("p", 1) or 1)
                    if key not in TEXT_COLORS: snackbar("❌ Неизвестный цвет"); return
                    set_design(user_id, fields_color=key); set_state("edit_menu", {"p": 2}); show("✅ Цвет полей применён!\nВыберите цвет полей (стр. {}/{}):".format(p, text_color_pages()), text_colors_kb("card_field_color", "card_text_field_colors", p, "card_text_menu")); snackbar("✅ Применено")
                elif cmd == "card_text_outline": set_state("edit_menu", {"p": 2}); show("Какой текст хотите обвести?", outline_target_kb()); snackbar("✅ Обводка")
                elif cmd == "card_outline_name":
                    p = int(payload.get("p", 1) or 1); set_state("edit_menu", {"p": 2}); show("Выберите цвет обводки ИМЕНИ (стр. {}/{}):".format(p, text_color_pages()), text_colors_kb("card_outline_set", "card_outline_name", p, "card_text_outline", none_target="name", sel_target="name")); snackbar("✅ Обводка имени")
                elif cmd == "card_outline_fields":
                    p = int(payload.get("p", 1) or 1); set_state("edit_menu", {"p": 2}); show("Выберите цвет обводки ПОЛЕЙ (стр. {}/{}):".format(p, text_color_pages()), text_colors_kb("card_outline_set", "card_outline_fields", p, "card_text_outline", none_target="fields", sel_target="fields")); snackbar("✅ Обводка полей")
                elif cmd == "card_outline_set":
                    key = payload.get("key", ""); tgt = payload.get("target", ""); p = int(payload.get("p", 1) or 1); mcmd = payload.get("m") or ("card_outline_name" if tgt == "name" else "card_outline_fields")
                    if key not in TEXT_COLORS or tgt not in ("name", "fields"): snackbar("❌ Неизвестный цвет"); return
                    set_design(user_id, **{"stroke_{}".format(tgt): key}); set_state("edit_menu", {"p": 2}); show("✅ Обводка ({}) применена!\n".format("имя" if tgt == "name" else "поля") + "Выберите цвет обводки (стр. {}/{}):".format(p, text_color_pages()), text_colors_kb("card_outline_set", mcmd, p, "card_text_outline", none_target=tgt, sel_target=tgt)); snackbar("✅ Обводка")
                elif cmd == "card_outline_clear":
                    tgt = payload.get("target", ""); mcmd = payload.get("m") or ("card_outline_name" if tgt == "name" else "card_outline_fields")
                    if tgt not in ("name", "fields"): snackbar("❌ Ошибка"); return
                    set_design(user_id, **{"stroke_{}".format(tgt): ""}); set_state("edit_menu", {"p": 2}); show("✅ Обводка ({}) убрана!\n".format("имя" if tgt == "name" else "поля") + "Выберите цвет обводки:", text_colors_kb("card_outline_set", mcmd, 1, "card_text_outline", none_target=tgt, sel_target=tgt)); snackbar("✅ Убрано")
                elif cmd == "card_text_pos": set_state("edit_menu", {"p": 2}); show("🎯 Положение текста: выберите поле для настройки:", text_pos_menu_kb()); snackbar("✅ Положение")
                elif cmd == "card_pos_menu":
                    f = payload.get("f", "")
                    if f not in POS_FIELDS: snackbar("❌ Неизвестное поле"); return
                    set_state("edit_menu", {"p": 2}); show(pos_adjust_text(user_id, f), pos_adjust_kb(f)); snackbar("✅ Настройка")
                elif cmd == "card_pos_move":
                    f = payload.get("f", ""); d = payload.get("dir", "")
                    if f not in POS_FIELDS or d not in ("up", "down", "left", "right"): snackbar("❌ Ошибка"); return
                    dx, dy = get_pos(user_id, f)
                    if d == "up": dy -= POS_STEP
                    elif d == "down": dy += POS_STEP
                    elif d == "left": dx -= POS_STEP
                    elif d == "right": dx += POS_STEP
                    set_pos(user_id, f, dx, dy); set_state("edit_menu", {"p": 2}); show(pos_adjust_text(user_id, f), pos_adjust_kb(f)); snackbar("✅ Сдвинуто")
                elif cmd == "card_pos_reset":
                    f = payload.get("f", "")
                    if f not in POS_FIELDS: snackbar("❌ Ошибка"); return
                    set_pos(user_id, f, 0.0, 0.0); set_state("edit_menu", {"p": 2}); show("✅ Положение «{}» сброшено.\n".format(POS_FIELDS[f]) + pos_adjust_text(user_id, f), pos_adjust_kb(f)); snackbar("✅ Сброс")

                elif cmd == "card_text_size":
                    fields = [("biz", "Бизнесы"), ("realty", "Недвижимость"), ("prop", "Имущество"), ("garage", "Гараж"), ("phone", "Телефон"), ("name", "Имя")]
                    rows = []
                    for i in range(0, len(fields), 2):
                        chunk = fields[i:i+2]
                        rows.append([{"action": {"type": "callback", "label": f"📏 {l}", "payload": json.dumps({"cmd": "card_size_field", "f": k})}, "color": "primary"} for k, l in chunk])
                    rows.append([{"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_text_menu"})}, "color": "secondary"}])
                    show("📏 Выберите поле для изменения размера:", {"inline": True, "buttons": rows})
                elif cmd == "card_size_field":
                    f = payload.get("f"); scale = get_design(user_id).get("font_scale", {}).get(f, 1.0)
                    kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "➕ Больше", "payload": json.dumps({"cmd": "card_size_up", "f": f})}, "color": "positive"}, {"action": {"type": "callback", "label": "➖ Меньше", "payload": json.dumps({"cmd": "card_size_down", "f": f})}, "color": "negative"}], [{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "card_text_size"})}, "color": "secondary"}]]}
                    show(f"📏 {POS_FIELDS.get(f, f)}\nТекущий масштаб: {scale:.1f}x", kb)
                elif cmd in ("card_size_up", "card_size_down"):
                    f = payload.get("f"); d = get_design(user_id); scales = d.get("font_scale", {}); cur = scales.get(f, 1.0)
                    cur += 0.1 if cmd == "card_size_up" else -0.1; cur = max(0.5, min(cur, 2.0)); scales[f] = round(cur, 1); set_design(user_id, font_scale=scales)
                    snackbar(f"Масштаб: {cur:.1f}x")
                    kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "➕ Больше", "payload": json.dumps({"cmd": "card_size_up", "f": f})}, "color": "positive"}, {"action": {"type": "callback", "label": "➖ Меньше", "payload": json.dumps({"cmd": "card_size_down", "f": f})}, "color": "negative"}], [{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "card_text_size"})}, "color": "secondary"}]]}
                    edit_msg(f"📏 {POS_FIELDS.get(f, f)}\nТекущий масштаб: {cur:.1f}x", kb)

                # --- СВОЙ ЦВЕТ ---
                elif cmd == "card_custom_color_menu":
                    set_state("edit_menu", {"p": 2})
                    kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "Цвет Имени", "payload": json.dumps({"cmd": "card_custom_wait", "t": "custom_name_color"})}, "color": "primary"}, {"action": {"type": "callback", "label": "Цвет Полей", "payload": json.dumps({"cmd": "card_custom_wait", "t": "custom_fields_color"})}, "color": "primary"}], [{"action": {"type": "callback", "label": "Обводка Имени", "payload": json.dumps({"cmd": "card_custom_wait", "t": "custom_stroke_name"})}, "color": "secondary"}, {"action": {"type": "callback", "label": "Обводка Полей", "payload": json.dumps({"cmd": "card_custom_wait", "t": "custom_stroke_fields"})}, "color": "secondary"}], [{"action": {"type": "callback", "label": "Сбросить свои цвета", "payload": json.dumps({"cmd": "card_custom_clear"})}, "color": "negative"}, {"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_text_menu"})}, "color": "secondary"}]]}
                    show("Выберите цвет чего хотите изменить:", kb)
                elif cmd == "card_custom_wait":
                    t = payload.get("t"); set_state("custom_color_input", {"target": t})
                    kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "card_custom_color_menu"})}, "color": "primary"}, {"action": {"type": "callback", "label": "❌ Отмена", "payload": json.dumps({"cmd": "card_cancel"})}, "color": "negative"}]]}
                    show("🎨 Отправьте сообщением код цвета:\n(Формат: #RRGGBB или R,G,B)\n\nНажмите «назад» для выхода.", kb)
                elif cmd == "card_custom_clear":
                    d = get_design(user_id)
                    for k in ["custom_name_color", "custom_fields_color", "custom_stroke_name", "custom_stroke_fields"]: d.pop(k, None)
                    set_card_field(user_id, design=json.dumps(d, ensure_ascii=False)); snackbar("✅ Свои цвета сброшены")

                # --- РАЗМЕР ОБВОДКИ ---
                elif cmd == "card_outline_width_menu":
                    w = int(get_design(user_id).get("outline_width", 1))
                    kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "➕ Больше", "payload": json.dumps({"cmd": "card_outline_width_up"})}, "color": "positive"}, {"action": {"type": "callback", "label": "➖ Меньше", "payload": json.dumps({"cmd": "card_outline_width_down"})}, "color": "negative"}], [{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "card_text_outline"})}, "color": "secondary"}]]}
                    show(f"📏 Размер обводки: {w}px", kb)
                elif cmd in ("card_outline_width_up", "card_outline_width_down"):
                    d = get_design(user_id); cur = int(d.get("outline_width", 1))
                    cur += 1 if cmd == "card_outline_width_up" else -1; cur = max(1, min(cur, 5)); set_design(user_id, outline_width=cur); snackbar(f"Размер: {cur}px")
                    kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "➕ Больше", "payload": json.dumps({"cmd": "card_outline_width_up"})}, "color": "positive"}, {"action": {"type": "callback", "label": "➖ Меньше", "payload": json.dumps({"cmd": "card_outline_width_down"})}, "color": "negative"}], [{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "card_text_outline"})}, "color": "secondary"}]]}
                    edit_msg(f"📏 Размер обводки: {cur}px", kb)

                elif cmd == "card_exclusive":
                    set_state("edit_menu", {"p": 2})
                    try: lst = get_excards(user_id)
                    except Exception as _e: print("excards load err:", _e); lst = []
                    if not isinstance(lst, list): lst = []
                    lst = [str(x) for x in lst if x]
                    if not lst:
                        show("У вас пока нет эксклюзивных карт.\nИх можно получить по промокоду: /promo #код.", ex_back_kb())
                    else:
                        per_page = 6
                        try: page = int(payload.get("p", 1))
                        except Exception: page = 1
                        total_pages = max(1, (len(lst) + per_page - 1) // per_page)
                        page = max(1, min(page, total_pages))
                        chunk = lst[(page-1)*per_page : page*per_page]
                        rows = []; line = []
                        for nm in chunk:
                            lab = nm[:18]
                            pay = json.dumps({"cmd": "card_ex_apply", "name": nm})
                            line.append({"action": {"type": "callback", "label": lab, "payload": pay}, "color": "primary"})
                            if len(line) == 2:
                                rows.append(line); line = []
                        if line: rows.append(line)
                        nav = []
                        if page > 1: nav.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "card_exclusive", "p": page-1})}, "color": "secondary"})
                        nav.append({"action": {"type": "callback", "label": f"{page}/{total_pages}", "payload": json.dumps({"cmd": "page_info"})}, "color": "default"})
                        if page < total_pages: nav.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "card_exclusive", "p": page+1})}, "color": "secondary"})
                        if nav: rows.append(nav)
                        rows.append([{"action": {"type": "callback", "label": "Снять эксклюзив", "payload": json.dumps({"cmd": "card_ex_clear"})}, "color": "negative"}, {"action": {"type": "callback", "label": "Назад", "payload": json.dumps({"cmd": "card_edit_menu", "p": 2})}, "color": "secondary"}])
                        show(f"🎩 Ваши эксклюзивные карты (стр. {page}/{total_pages}):", {"inline": True, "buttons": rows})
                    snackbar("✅ Эксклюзив")
                
                elif cmd == "card_ex_apply":
                    nm = payload.get("name", "")
                    if not strict_template(nm) or nm not in get_excards(user_id): snackbar("❌ Карта недоступна"); return
                    set_design(user_id, exclusive=nm); set_state("edit_menu", {"p": 2}); show("✅ Эксклюзивная карта «{}» применена!".format(nm), ex_back_kb()); snackbar("✅ Применено")
                elif cmd == "card_ex_clear":
                    set_design(user_id, exclusive=""); set_state("edit_menu", {"p": 2}); show("✅ Эксклюзив снят, вернулась обычная карта.", ex_back_kb()); snackbar("✅ Снято")
                elif cmd == "card_design_photo": set_state("design_photo_wait"); show(DESIGN_PHOTO_TEXT, design_photo_kb()); snackbar("✅ Жду фото")
                elif cmd == "card_design_default":
                    set_design(user_id, photo=""); set_state("edit_menu", {"p": 2}); show("✅ Возвращена дефолтная фотография.\nВыберите действие:", card_edit_page_kb(2)); snackbar("✅ Дефолт")
                else: snackbar("❌ Неизвестная кнопка карточки")
            except Exception as e: print("card callback error:", e); snackbar("❌ Ошибка карточки")
            return

        if cmd in ["check_warns", "check_mutes", "check_back"]:
            target_id = int(payload.get("target", 0))
            if not target_id: snackbar("❌ Ошибка"); return
            target_name = silent_mention_badge(target_id, peer_id); month_ago = int(time.time()) - 30 * 86400
            if cmd == "check_back":
                kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "⚠️ Предупреждения", "payload": json.dumps({"cmd": "check_warns", "target": target_id})}, "color": "negative"}, {"action": {"type": "callback", "label": "🔇 Муты", "payload": json.dumps({"cmd": "check_mutes", "target": target_id})}, "color": "primary"}]]}
                edit_msg("📜 История наказаний {} за месяц:".format(target_name), kb); snackbar("✅ Выполнено"); return
            if cmd == "check_warns":
                with DB_LOCK: rows = CONN.execute("SELECT reason, message_text, issued_by, issued_at, duration_minutes FROM punishment_history WHERE peer_id=? AND user_id=? AND type='warn' AND issued_at>=? ORDER BY issued_at DESC", (peer_id, target_id, month_ago)).fetchall()
                lines = ["📜 История предупреждений {} за месяц:\n".format(target_name)]
                if not rows: lines.append("Предупреждений нет.")
                else:
                    for idx, r in enumerate(rows, 1):
                        dt = datetime.datetime.fromtimestamp(r["issued_at"], MSK_TZ).strftime("%d.%m %H:%M"); issuer = silent_mention_badge(r["issued_by"], peer_id) if r["issued_by"] else "Неизвестно"; reason = r["reason"] or "Не указана"
                        if r["message_text"]: reason += ' - "{}"'.format(r["message_text"][:100])
                        lines.append("{}. | {} | {} | Причина: {} | Выдал: {}|".format(idx, dt, fmt_warn_duration(r["duration_minutes"]), reason, issuer))
                edit_msg("\n".join(lines), {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "check_back", "target": target_id})}, "color": "secondary"}]]}); snackbar("✅ Выполнено"); return
            if cmd == "check_mutes":
                with DB_LOCK: rows = CONN.execute("SELECT reason, message_text, issued_by, issued_at, duration_minutes FROM punishment_history WHERE peer_id=? AND user_id=? AND type='mute' AND issued_at>=? ORDER BY issued_at DESC", (peer_id, target_id, month_ago)).fetchall()
                lines = ["📜 История мутов {} за месяц:\n".format(target_name)]
                if not rows: lines.append("Мутов нет.")
                else:
                    for idx, r in enumerate(rows, 1):
                        dt = datetime.datetime.fromtimestamp(r["issued_at"], MSK_TZ).strftime("%d.%m %H:%M"); issuer = silent_mention_badge(r["issued_by"], peer_id) if r["issued_by"] else "Неизвестно"; reason = r["reason"] or "Не указана"
                        if r["message_text"]: reason += ' - "{}"'.format(r["message_text"][:100])
                        lines.append("{}. | {} | {} | Причина: {} | Выдал: {}|".format(idx, dt, fmt_mute_duration(r["duration_minutes"]), reason, issuer))
                edit_msg("\n".join(lines), {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "⬅️ Назад", "payload": json.dumps({"cmd": "check_back", "target": target_id})}, "color": "secondary"}]]}); snackbar("✅ Выполнено"); return

        if cmd in ["dice_accept", "dice_decline", "dice_roll", "dice_punish_mute", "dice_punish_mention", "dice_punish_pardon"]:
            game_id = payload.get("game_id", 0)
            with DB_LOCK: game = CONN.execute("SELECT * FROM dice_games WHERE id=?", (game_id,)).fetchone()
            if not game: snackbar("❌ Игра не найдена"); return
            now = int(time.time())
            if game["state"] == "pending" and (now - game["created_at"]) > 60:
                with DB_LOCK: CONN.execute("UPDATE dice_games SET state='expired' WHERE id=?", (game_id,)); CONN.commit()
                edit_game_message(peer_id, game_id, "⏰ Время вышло! {} не успел принять вызов от {} 🕐".format(silent_mention_badge(game["opponent"], peer_id), silent_mention_badge(game["initiator"], peer_id))); snackbar("⏰ Время вышло"); return
            if cmd == "dice_accept":
                if user_id != game["opponent"]: snackbar("⛔ Это не твой вызов"); return
                if game["state"] != "pending": snackbar("⚠️ Игра уже неактивна"); return
                with DB_LOCK: CONN.execute("UPDATE dice_games SET state='playing', current_turn=? WHERE id=?", (game["initiator"], game_id)); CONN.commit()
                edit_game_message(peer_id, game_id, "✅ {} принял вызов! Начинаем! 🎲\n{}, твоя очередь!".format(silent_mention_badge(game["opponent"], peer_id), silent_mention_badge(game["initiator"], peer_id)), {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "🎲 Бросить кость", "payload": json.dumps({"cmd": "dice_roll", "game_id": game_id})}, "color": "positive"}]]}); snackbar("🎲 Игра началась!"); return
            elif cmd == "dice_decline":
                if user_id != game["opponent"]: snackbar("⛔ Не твой вызов"); return
                if game["state"] != "pending": snackbar("⚠️ Игра уже неактивна"); return
                with DB_LOCK: CONN.execute("UPDATE dice_games SET state='declined' WHERE id=?", (game_id,)); CONN.commit()
                edit_game_message(peer_id, game_id, "😞 {} отказался от игры с {}. 💔".format(silent_mention_badge(game["opponent"], peer_id), silent_mention_badge(game["initiator"], peer_id))); snackbar("❌ Отменено"); return
            elif cmd == "dice_roll":
                if game["state"] != "playing": snackbar("⚠️ Игра уже неактивна"); return
                if user_id != game["current_turn"]: snackbar("⛔ Не твоя очередь"); return
                roll = random.randint(1, 6); ini, opp = game["initiator"], game["opponent"]
                if user_id == ini: ni, no, nt = roll, game["opponent_roll"], opp
                else: ni, no, nt = game["initiator_roll"], roll, ini
                with DB_LOCK: CONN.execute("UPDATE dice_games SET initiator_roll=?, opponent_roll=?, current_turn=? WHERE id=?", (ni, no, nt, game_id)); CONN.commit()
                if ni > 0 and no > 0:
                    if ni == no:
                        with DB_LOCK: CONN.execute("UPDATE dice_games SET initiator_roll=0, opponent_roll=0, current_turn=? WHERE id=?", (ini, game_id)); CONN.commit()
                        edit_game_message(peer_id, game_id, "🤝 Ничья! Перекидываем! 🔄\n{}, бросай снова!".format(silent_mention_badge(ini, peer_id)), {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "🎲 Бросить кость", "payload": json.dumps({"cmd": "dice_roll", "game_id": game_id})}, "color": "positive"}]]})
                    else:
                        winner = ini if ni > no else opp; loser = opp if ni > no else ini
                        with DB_LOCK: CONN.execute("UPDATE dice_games SET state='finished' WHERE id=?", (game_id,)); CONN.commit()
                        increment_dice_win(peer_id, winner)
                        edit_game_message(peer_id, game_id, "🎉 {} побеждает! 🏆\n{}, выбирай наказание для {}:".format(silent_mention_badge(winner, peer_id), silent_mention_badge(winner, peer_id), silent_mention_badge(loser, peer_id)), {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "🔇 Мут 30 мин", "payload": json.dumps({"cmd": "dice_punish_mute", "game_id": game_id})}, "color": "negative"}], [{"action": {"type": "callback", "label": "📢 Упоминать 60м/5ч", "payload": json.dumps({"cmd": "dice_punish_mention", "game_id": game_id})}, "color": "primary"}], [{"action": {"type": "callback", "label": "🕊 Помиловать", "payload": json.dumps({"cmd": "dice_punish_pardon", "game_id": game_id})}, "color": "positive"}]]})
                else:
                    edit_game_message(peer_id, game_id, "🎲 {} выбросил {}!\n{}, твоя очередь!".format(silent_mention_badge(user_id, peer_id), roll, silent_mention_badge(nt, peer_id)), {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "🎲 Бросить кость", "payload": json.dumps({"cmd": "dice_roll", "game_id": game_id})}, "color": "positive"}]]})
                snackbar("🎲 Выпало: {}".format(roll)); return
            elif cmd == "dice_punish_mute":
                if game["state"] != "finished": snackbar("⚠️ Игра уже неактивна"); return
                ini, opp = game["initiator"], game["opponent"]; winner = ini if game["initiator_roll"] > game["opponent_roll"] else opp; loser = opp if game["initiator_roll"] > game["opponent_roll"] else ini
                if user_id != winner: snackbar("⛔ Только победитель"); return
                muted_now, _ = has_active_dice_punishments(peer_id, loser)
                if muted_now: snackbar("⚠️ Уже замучен!"); return
                mute_until = int(time.time()) + 30 * 60
                with DB_LOCK:
                    CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (loser, peer_id))
                    CONN.execute("UPDATE members SET mute_until=?, mute_reason=? WHERE user_id=? AND peer_id=?", (mute_until, "Проиграл в кости 🎲", loser, peer_id)); CONN.commit()
                add_punishment(peer_id, loser, "mute", "Проиграл в кости 🎲", 0, "", winner, 30)
                edit_game_message(peer_id, game_id, "🔇 {} выдал мут на 30 минут для {}! 🎲".format(silent_mention_badge(winner, peer_id), silent_mention_badge(loser, peer_id))); snackbar("🔇 Мут выдан!"); return
            elif cmd == "dice_punish_mention":
                if game["state"] != "finished": snackbar("⚠️ Игра уже неактивна"); return
                ini, opp = game["initiator"], game["opponent"]; winner = ini if game["initiator_roll"] > game["opponent_roll"] else opp; loser = opp if game["initiator_roll"] > game["opponent_roll"] else ini
                if user_id != winner: snackbar("⛔ Только победитель"); return
                _, ment_now = has_active_dice_punishments(peer_id, loser)
                if ment_now: snackbar("⚠️ Уже упоминается!"); return
                now_ts = int(time.time())
                with DB_LOCK:
                    CONN.execute("DELETE FROM dice_mentions WHERE peer_id=? AND user_id=?", (peer_id, loser))
                    CONN.execute("INSERT INTO dice_mentions(peer_id, user_id, next_trigger, end_time, interval_minutes) VALUES(?,?,?,?,?)", (peer_id, loser, now_ts + 3600, now_ts + 5*3600, 60)); CONN.commit()
                edit_game_message(peer_id, game_id, "📢 {} будет упоминать {} каждые 60 мин / 5 часов! 🎲".format(silent_mention_badge(winner, peer_id), silent_mention_badge(loser, peer_id))); snackbar("📢 Упоминания запущены!"); return
            elif cmd == "dice_punish_pardon":
                if game["state"] != "finished": snackbar("⚠️ Игра уже неактивна"); return
                ini, opp = game["initiator"], game["opponent"]; winner = ini if game["initiator_roll"] > game["opponent_roll"] else opp; loser = opp if game["initiator_roll"] > game["opponent_roll"] else ini
                if user_id != winner: snackbar("⛔ Только победитель"); return
                edit_game_message(peer_id, game_id, "🕊 {} помиловал {}! 🎲❤️".format(silent_mention_badge(winner, peer_id), silent_mention_badge(loser, peer_id))); snackbar("🕊 Помилован!"); return

        if cmd in ["kmb_accept", "kmb_decline", "kmb_choice"]:
            game_id = payload.get("game_id", 0)
            with DB_LOCK: game = CONN.execute("SELECT * FROM kmb_games WHERE id=?", (game_id,)).fetchone()
            if not game: snackbar("❌ Игра не найдена"); return
            chat_peer = game["peer_id"]; now = int(time.time())
            if game["state"] == "pending" and (now - game["created_at"]) > 60:
                with DB_LOCK: CONN.execute("UPDATE kmb_games SET state='expired' WHERE id=?", (game_id,)); CONN.commit()
                edit_game_message(chat_peer, game_id, "⏰ КНБ: время вышло!", table="kmb_games"); snackbar("⏰ Время вышло"); return
            kmb_kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "👊 Камень", "payload": json.dumps({"cmd": "kmb_choice", "game_id": game_id, "choice": "rock"})}, "color": "primary"}, {"action": {"type": "callback", "label": "✌️ Ножницы", "payload": json.dumps({"cmd": "kmb_choice", "game_id": game_id, "choice": "scissors"})}, "color": "primary"}, {"action": {"type": "callback", "label": "✋ Бумага", "payload": json.dumps({"cmd": "kmb_choice", "game_id": game_id, "choice": "paper"})}, "color": "primary"}]]}
            if cmd == "kmb_accept":
                if user_id != game["opponent"]: snackbar("⛔ Не твой вызов"); return
                if game["state"] != "pending": snackbar("⚠️ Игра уже неактивна"); return
                with DB_LOCK: CONN.execute("UPDATE kmb_games SET state='choosing', created_at=? WHERE id=?", (int(time.time()), game_id)); CONN.commit()
                edit_game_message(chat_peer, game_id, "✅ {} принял вызов КНБ! ✊✌️✋ Кнопки в ЛС!".format(silent_mention_badge(game["opponent"], chat_peer)), table="kmb_games")
                send_msg(game["initiator"], "🎮 КНБ: выбери ход!", keyboard=kmb_kb); send_msg(game["opponent"], "🎮 КНБ: выбери ход!", keyboard=kmb_kb); snackbar("✅ Проверь ЛС!"); return
            elif cmd == "kmb_decline":
                if user_id != game["opponent"]: snackbar("⛔ Не твой вызов"); return
                if game["state"] != "pending": snackbar("⚠️ Игра уже неактивна"); return
                with DB_LOCK: CONN.execute("UPDATE kmb_games SET state='declined' WHERE id=?", (game_id,)); CONN.commit()
                edit_game_message(chat_peer, game_id, "😞 {} отказался от КНБ. 💔".format(silent_mention_badge(game["opponent"], chat_peer)), table="kmb_games"); snackbar("❌ Отменено"); return
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
                    CONN.commit(); game = CONN.execute("SELECT * FROM kmb_games WHERE id=?", (game_id,)).fetchone()
                snackbar("✅ Выбор сохранён!")
                if game["init_choice"] and game["opp_choice"]:
                    ic, oc = game["init_choice"], game["opp_choice"]; beats = {"rock": "scissors", "scissors": "paper", "paper": "rock"}; emojis = {"rock": "👊", "scissors": "✌️", "paper": "✋"}
                    if ic == oc:
                        with DB_LOCK: CONN.execute("UPDATE kmb_games SET init_choice='', opp_choice='', created_at=? WHERE id=?", (int(time.time()), game_id)); CONN.commit()
                        send_msg(chat_peer, "🤝 Ничья! Оба выбрали {}\nПереигрываем! Проверьте ЛС.".format(emojis[ic]))
                        send_msg(game["initiator"], "🎮 КНБ: переигровка!", keyboard=kmb_kb); send_msg(game["opponent"], "🎮 КНБ: переигровка!", keyboard=kmb_kb)
                    else:
                        winner = game["initiator"] if beats[ic] == oc else game["opponent"]; wc = ic if winner == game["initiator"] else oc
                        with DB_LOCK: CONN.execute("UPDATE kmb_games SET state='finished' WHERE id=?", (game_id,)); CONN.commit()
                        increment_kmb_win(chat_peer, winner)
                        send_msg(chat_peer, "✊✌️✋ Результат КМБ:\n{} {}  vs {} {}\n\n🏆 {} {} побеждает!".format(silent_mention_badge(game["initiator"], chat_peer), emojis[ic], silent_mention_badge(game["opponent"], chat_peer), emojis[oc], silent_mention_badge(winner, chat_peer), emojis[wc]))
                return

        if cmd in ["marriage_accept", "marriage_decline"]:
            proposer = payload.get("proposer", 0); target = payload.get("target", 0)
            if user_id != target: snackbar("⛔ Не тебе предложение!"); return
            with DB_LOCK: prop = CONN.execute("SELECT * FROM dice_games WHERE state='marriage' AND peer_id=? AND initiator=? AND opponent=? ORDER BY id DESC LIMIT 1", (peer_id, proposer, target)).fetchone()
            if not prop or (int(time.time()) - prop["created_at"]) > 60: snackbar("⏰ Время предложения истекло!"); return
            if cmd == "marriage_accept":
                if get_marriage(peer_id, proposer) or get_marriage(peer_id, target): snackbar("⚠️ Кто-то уже в браке!"); return
                with DB_LOCK:
                    try:
                        CONN.execute("INSERT INTO marriages(peer_id, user1, user2, created_at) VALUES(?,?,?,?)", (peer_id, proposer, target, int(time.time())))
                        CONN.execute("UPDATE dice_games SET state='married' WHERE id=?", (prop["id"],)); CONN.commit()
                    except: snackbar("❌ Ошибка"); return
                try:
                    users_info = VK.users.get(user_ids="{},{}".format(proposer, target), fields='sex'); sex_map = {u['id']: u.get('sex', 0) for u in users_info}
                    if sex_map.get(proposer) == 2 and sex_map.get(target) == 2: send_msg(peer_id, "Мужики вы что геи что ли? А я не гей..")
                except: pass
                edit_game_message(peer_id, prop["id"], "💕️ Поздравляю, теперь {} и {} в счастливом браке!".format(silent_mention_badge(proposer, peer_id), silent_mention_badge(target, peer_id))); snackbar("💍 Вы в браке!"); return
            else:
                with DB_LOCK: CONN.execute("UPDATE dice_games SET state='declined' WHERE id=?", (prop["id"],)); CONN.commit()
                edit_game_message(peer_id, prop["id"], "💔 {} отказал(а) {}... Не судьба. 😢".format(silent_mention_badge(target, peer_id), silent_mention_badge(proposer, peer_id))); snackbar("❌ Отказ"); return

        if cmd == "poll_vote":
            now_ts = int(time.time()); today_str = get_msk_now().strftime("%Y-%m-%d"); payload_time = payload.get("time", 0)
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
                            CONN.execute("UPDATE members SET last_vote_time=? WHERE user_id=? AND peer_id=?", (now_ts, user_id, peer_id)); CONN.commit()
                            send_msg(peer_id, "✅ {} Зайдет на этот кд!".format(silent_mention_badge(user_id, peer_id))); snackbar("✅ Отметился!")
            except: snackbar("❌ Ошибка"); return

        if cmd == "page_info": snackbar("📄 Стр. {} из {}".format(payload.get("page",1), payload.get("total",1))); return
        if cmd in ["niki_prev", "niki_next"]:
            page = int(payload.get("page", 1))
            with DB_LOCK:
                rows = CONN.execute("SELECT user_id, nickname FROM members WHERE peer_id=? AND nickname!='' AND nickname IS NOT NULL ORDER BY user_id LIMIT 40 OFFSET ?", (peer_id, (page-1)*40)).fetchall()
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND nickname!='' AND nickname IS NOT NULL", (peer_id,)).fetchone()[0]
            per_page = 40; total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages)); lines = ["📝 Ники (стр. {}/{}):\n".format(page, total_pages)]
            for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append('{}. {} — "{}"'.format(idx, silent_mention_badge(r["user_id"], peer_id), r["nickname"]))
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "niki_prev", "page": page-1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "niki_next", "page": page+1})}, "color": "secondary"})
            edit_msg("\n".join(lines), {"inline": True, "buttons": [buttons]}); snackbar("📄 Стр. {}".format(page)); return
        if cmd in ["participants_prev", "participants_next"]:
            page = int(payload.get("page", 1))
            with DB_LOCK:
                rows = CONN.execute("SELECT user_id, nickname FROM members WHERE peer_id=? ORDER BY user_id LIMIT 40 OFFSET ?", (peer_id, (page-1)*40)).fetchall()
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=?", (peer_id,)).fetchone()[0]
            per_page = 40; total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages)); lines = ["👥 Участники (стр. {}/{}):\n".format(page, total_pages)]
            for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append('{}. {} — "{}"'.format(idx, silent_mention_badge(r["user_id"], peer_id), r["nickname"] or "Не установлен"))
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "participants_prev", "page": page-1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "participants_next", "page": page+1})}, "color": "secondary"})
            edit_msg("\n".join(lines), {"inline": True, "buttons": [buttons]}); snackbar("📄 Стр. {}".format(page)); return
        if cmd in ["predy_prev", "predy_next"]:
            page = int(payload.get("page", 1)); per_page = 20
            with DB_LOCK:
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND warnings>0", (peer_id,)).fetchone()[0]
                rows = CONN.execute("SELECT user_id, warnings, warn_durations FROM members WHERE peer_id=? AND warnings>0 ORDER BY warnings DESC LIMIT ? OFFSET ?", (peer_id, per_page, (page-1)*per_page)).fetchall()
            total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages)); lines = ["⚠️ Предупреждения (стр. {}/{}):\n".format(page, total_pages)]
            for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append("{}. {} — {} пред. ({} дн.)".format(idx, silent_mention_badge(r["user_id"], peer_id), r["warnings"], r["warn_durations"] or "0"))
            buttons = []
            if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "predy_prev", "page": page-1})}, "color": "secondary"})
            buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "predy_next", "page": page+1})}, "color": "secondary"})
            edit_msg("\n".join(lines), {"inline": True, "buttons": [buttons]}); snackbar("📄 Стр. {}".format(page)); return
        if cmd in ["br_prev", "br_next"]:
            page = int(payload.get("page", 1)); text, keyboardJson, _ = build_br_page(page)
            if text is None: snackbar("❌ Нет данных"); return
            edit_msg(text, json.loads(keyboardJson)); snackbar("📄 Стр. {}".format(page)); return
        if cmd in ["status_prev", "status_next"]:
            page = int(payload.get("page", 1)); text, keyboardJson, _ = build_status_page(peer_id, page)
            if text is None: snackbar("❌ Статусов нет"); return
            edit_msg(text, json.loads(keyboardJson)); snackbar("📄 Стр. {}".format(page)); return
        if cmd in ["top_messages", "top_stickers", "top_dice", "top_marriages", "top_kmb", "top_days", "top_streaks"]:
            top_type = cmd.replace("top_", ""); page = int(payload.get("page", 1)); per_page = 50; total = 0; lines = []
            if top_type == "messages":
                with DB_LOCK:
                    total = CONN.execute("SELECT COUNT(*) FROM message_stats WHERE peer_id=? AND (msg_count>0 OR char_count>0)", (peer_id,)).fetchone()[0]
                    rows = CONN.execute("SELECT user_id, msg_count, char_count FROM message_stats WHERE peer_id=? AND (msg_count>0 OR char_count>0) ORDER BY char_count DESC LIMIT ? OFFSET ?", (peer_id, per_page, (page-1)*per_page)).fetchall()
                lines = ["🏆 Топ пользователей", "[💬 символы | ✉ сообщения]\n"]
                for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append("{}. {} — {} | {}".format(idx, silent_mention_badge(r["user_id"], peer_id), r["char_count"], r["msg_count"]))
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
                    rows_all = CONN.execute("SELECT user1, user2, created_at FROM marriages WHERE peer_id=? ORDER BY created_at ASC", (peer_id,)).fetchall(); active_rows = []
                    for r in rows_all:
                        m1 = CONN.execute("SELECT 1 FROM members WHERE user_id=? AND peer_id=?", (r["user1"], peer_id)).fetchone()
                        m2 = CONN.execute("SELECT 1 FROM members WHERE user_id=? AND peer_id=?", (r["user2"], peer_id)).fetchone()
                        if m1 or m2: active_rows.append(r)
                    total = len(active_rows); start = (page-1)*per_page; rows_page = active_rows[start:start+per_page]
                lines = ["💒 Топ браков:\n"]; now_ts = int(time.time())
                for idx, r in enumerate(rows_page, start+1): lines.append("{}. {} и {} ({} дн.)".format(idx, silent_mention_badge(r["user1"], peer_id), silent_mention_badge(r["user2"], peer_id), (now_ts - r["created_at"]) // 86400))
            elif top_type == "days":
                with DB_LOCK:
                    total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND join_time>0", (peer_id,)).fetchone()[0]
                    rows = CONN.execute("SELECT user_id, join_time FROM members WHERE peer_id=? AND join_time>0 ORDER BY join_time ASC LIMIT ? OFFSET ?", (peer_id, per_page, (page-1)*per_page)).fetchall()
                lines = ["📅 Топ дней в чате (с последнего захода):\n"]
                for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append("{}. {} — {} дн.".format(idx, silent_mention_badge(r["user_id"], peer_id), days_since(r["join_time"])))
            elif top_type == "streaks":
                with DB_LOCK:
                    total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND streak>0", (peer_id,)).fetchone()[0]
                    rows = CONN.execute("SELECT user_id, streak FROM members WHERE peer_id=? AND streak>0 ORDER BY streak DESC LIMIT ? OFFSET ?", (peer_id, per_page, (page-1)*per_page)).fetchall()
                lines = ["🔥 Топ серий:\n"]
                for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append("{}. {} — {} дн. {}".format(idx, silent_mention_badge(r["user_id"], peer_id), r["streak"], get_streak_emoji(r["streak"])))
            total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages)); nav = []
            if page > 1: nav.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": cmd, "page": page-1})}, "color": "secondary"})
            nav.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
            if page < total_pages: nav.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": cmd, "page": page+1})}, "color": "secondary"})
            cats1 = [{"action": {"type": "callback", "label": "💬", "payload": json.dumps({"cmd": "top_messages", "page": 1})}, "color": "primary" if top_type=="messages" else "secondary"}, {"action": {"type": "callback", "label": "🎨", "payload": json.dumps({"cmd": "top_stickers", "page": 1})}, "color": "primary" if top_type=="stickers" else "secondary"}, {"action": {"type": "callback", "label": "🎲", "payload": json.dumps({"cmd": "top_dice", "page": 1})}, "color": "primary" if top_type=="dice" else "secondary"}]
            cats2 = [{"action": {"type": "callback", "label": "✊✌️✋", "payload": json.dumps({"cmd": "top_kmb", "page": 1})}, "color": "primary" if top_type=="kmb" else "secondary"}, {"action": {"type": "callback", "label": "💒", "payload": json.dumps({"cmd": "top_marriages", "page": 1})}, "color": "primary" if top_type=="marriages" else "secondary"}, {"action": {"type": "callback", "label": "📅", "payload": json.dumps({"cmd": "top_days", "page": 1})}, "color": "primary" if top_type=="days" else "secondary"}]
            cats3 = [{"action": {"type": "callback", "label": "🔥", "payload": json.dumps({"cmd": "top_streaks", "page": 1})}, "color": "primary" if top_type=="streaks" else "secondary"}]
            edit_msg("\n".join(lines), {"inline": True, "buttons": [cats1, cats2, cats3, nav]}); snackbar("📄 Стр. {}".format(page)); return
        if cmd in ["help_general", "help_systems", "help_manage", "help_remind", "help_polls", "help_admin", "help_moderator", "help_main_admin", "help_owner", "help_br", "help_games", "help_md", "help_back", "help_back_main"]:
            checks = {"help_systems": is_admin, "help_manage": is_moderator, "help_moderator": is_moderator, "help_admin": is_admin, "help_main_admin": is_main_admin, "help_owner": is_owner, "help_remind": is_admin, "help_polls": is_admin, "help_md": is_md_member}
            if cmd in checks:
                fn = checks[cmd]; ok = fn(user_id) if cmd == "help_md" else fn(user_id, peer_id)
                if not ok: snackbar("У вас нет прав⛔️"); return
            if cmd in ["help_back", "help_back_main"]: message_text = "📖 Команды MD BOT"; kb_dict = get_help_main_buttons()
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
            edit_msg(message_text, kb_dict); snackbar("✅ Выполнено"); return
    except Exception as e: print("event error:", e)

STATUS_PER_PAGE = 5
def build_status_page(peer, page):
    with DB_LOCK:
        statuses = CONN.execute("SELECT id, name FROM statuses WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
        if not statuses: return None, None, 1
        total = len(statuses); total_pages = max(1, (total + STATUS_PER_PAGE - 1) // STATUS_PER_PAGE)
        try: page = int(page)
        except: page = 1
        page = max(1, min(page, total_pages)); chunk = statuses[(page-1)*STATUS_PER_PAGE: page*STATUS_PER_PAGE]; lines = ["📋 Статусы (стр. {}/{}):\n".format(page, total_pages)]
        for idx, s in enumerate(chunk, (page-1)*STATUS_PER_PAGE+1):
            with DB_LOCK: users = CONN.execute("SELECT user_id FROM user_statuses WHERE status_id=? AND peer_id=?", (s["id"], peer)).fetchall()
            links = [silent_mention_badge(u["user_id"], peer) for u in users]
            lines.append("{} {}\n{}".format(idx, s["name"], "\n".join(links)) if links else "{} {}\n(пусто)".format(idx, s["name"]))
        lines.append(" "); buttons = []
        if page > 1: buttons.append({"action": {"type": "callback", "label": "⬅️", "payload": json.dumps({"cmd": "status_prev", "page": page-1})}, "color": "secondary"})
        buttons.append({"action": {"type": "callback", "label": "{}/{}".format(page, total_pages), "payload": json.dumps({"cmd": "page_info", "page": page, "total": total_pages})}, "color": "default"})
        if page < total_pages: buttons.append({"action": {"type": "callback", "label": "➡️", "payload": json.dumps({"cmd": "status_next", "page": page+1})}, "color": "secondary"})
    return "\n".join(lines), json.dumps({"inline": True, "buttons": [buttons]}), total_pages

LEGENDARY_WHO = ["Пират🏴‍☠️", "Босс 👑", "Абсолют 🪐", "Легенда 🐐", "Олигарх 🎩", "Вампир 🧛", "Чародей 🧙", "Клоун 🤡", "Феникс🐦‍", "Мафиози️"]
LEGEND_SETKTO = {"пират":"Пират🏴‍️", "босс":"Босс 👑", "абсолют":"Абсолют 🪐", "легенда":"Легенда 🐐", "олигарх":"Олигарх 🎩", "вампир":"Вампир 🧛", "чародей":"Чародей 🧙", "клоун":"Клоун 🤡", "феникс":"Феникс🐦", "мафиози":"Мафиози🕴️"}

def handle_ls_card(peer, sender, cmd, args):
    if cmd == "карта": send_card_to(peer, sender)
    elif cmd == "карта_редактировать": open_edit_menu(peer, sender)

def apply_clear_param(peer, target_id, param):
    if param == "фото": set_design(target_id, photo=""); return "✅ Фото карты {} сброшено.".format(silent_mention_badge(target_id, peer))
    field = PARAM_MAP[param]; set_card_field(target_id, **{field: FIELD_DEFAULT[field]}); return "✅ Очищено поле «{}» карты {}.".format(param, silent_mention_badge(target_id, peer))
def handle_clearcard(peer, sender, raw):
    targets = extract_targets(raw, 0)
    if not targets: send_msg(peer, "❌ Формат: /clearcard @юзер [параметр]"); return
    t = targets[0]; param = None; extra = []
    for tok in re.split(r"\s+", raw):
        tl = tok.strip(".,!?").lower()
        if tl in PARAM_MAP:
            if param is None: param = tl
        elif not re.match(r"^[[@]", tok) and not re.search(r"vk.(com|ru)/", tok) and not re.match(r"^\d{5,}$", tok): extra.append(tok)
    if param is None and extra: send_msg(peer, "❌ Нет такого параметра: {}. Доступные: {}.".format(" ".join(extra), PARAM_HINT)); return
    if param: send_msg(peer, apply_clear_param(peer, t, param))
    else: clear_card_data(t); send_msg(peer, "✅ Карта {} очищена (кроме цвета).".format(silent_mention_badge(t, peer)))
def handle_card_ls(peer, sender, raw):
    targets = extract_targets(raw, 0)
    if not targets: send_msg(peer, "❌ Формат: /card @юзер"); return
    send_card_to(peer, targets[0])
def handle_setkto(peer, sender, raw):
    m_id = re.search(r"(?:@|https?://vk.(?:com|ru)/|https?://m.vk.(?:com|ru)/|\[id)(\d+|[a-zA-Z0-9._]+)", raw, re.I)
    if not m_id: send_msg(peer, "❌ Не найден ID или ссылка."); return
    target_str = m_id.group(1)
    if target_str.isdigit(): target_id = int(target_str)
    else:
        try:
            res = VK.utils.resolveScreenName(screen_name=target_str)
            if res and res.get("type") == "user": target_id = int(res["object_id"])
            else: send_msg(peer, "❌ Не удалось найти пользователя по нику."); return
        except: send_msg(peer, "❌ Ошибка резолва ника."); return
    m_peer = re.search(r"\b(2\d{9})\b", raw)
    if not m_peer: send_msg(peer, "❌ Не найден номер чата."); return
    target_peer = int(m_peer.group(1)); clean_raw = re.sub(r"(?:@|https?://vk.(?:com|ru)/|https?://m.vk.(?:com|ru)/|\[id)\d+\|?[^]]*\]?", " ", raw, flags=re.I).strip()
    clean_raw = re.sub(r"\b2\d{9}\b", " ", clean_raw).strip()
    if not clean_raw: send_msg(peer, "❌ Не указаны слова статуса."); return
    clean_status = re.sub(r"[^\w\sа-яА-ЯёЁ]", " ", clean_raw).strip().lower(); final_status = ""
    for key, val in LEGEND_SETKTO.items():
        if key in clean_status: final_status = val; break
    if not final_status:
        words = clean_raw.split()
        if len(words) < 2: send_msg(peer, "❌ Для обычного статуса нужно прилагательное и существительное."); return
        adj, noun = words[0].lower(), words[1].lower()
        if adj not in WHO_ADJ or noun not in WHO_NOUN: send_msg(peer, "❌ Слова должны быть из списков бота!\nПрилагательное найдено: {}\nСуществительное найдено: {}".format(adj in WHO_ADJ, noun in WHO_NOUN)); return
        final_status = "{} {}".format(adj_form(adj, noun_gender(noun)), noun)
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (target_id, target_peer))
        CONN.execute("UPDATE members SET who_name=?, who_ts=? WHERE user_id=? AND peer_id=?", (final_status, int(time.time()), target_id, target_peer)); CONN.commit()
    send_msg(peer, "✅ Статус для id{} в чате {} установлен: {}".format(target_id, target_peer, final_status))
def handle_verify(peer, sender, raw, want):
    targets = extract_targets(raw, 0)
    if not targets: send_msg(peer, "❌ Формат: /{} @юзер".format("verify" if want else "deny")); return
    t = targets[0]
    with DB_LOCK:
        CONN.execute("INSERT OR IGNORE INTO player_cards(user_id) VALUES(?)", (t,))
        CONN.execute("UPDATE player_cards SET verified=? WHERE user_id=?", (1 if want else 0, t)); CONN.commit()
    if want: send_msg(peer, "✅ Карточка {} подтверждена.".format(silent_mention_badge(t, peer)))
    else: send_msg(peer, "✅ Подтверждение карточки {} снято.".format(silent_mention_badge(t, peer)))
def handle_inspector(peer, sender, raw):
    targets = extract_targets(raw, 0)
    if not targets: send_msg(peer, "❌ Формат: /inspector @юзер (повторно — снять роль)"); return
    t = targets[0]
    if t in (CREATOR_ID, LEADER_ID): send_msg(peer, "❌ У создателя и лидера доступ есть всегда."); return
    key = "inspector_{}".format(t)
    if get_setting(0, key, "0") == "1":
        set_setting(0, key, "0"); send_msg(peer, "✅ С {} снята роль проверяющего.".format(silent_mention_badge(t, peer))); send_msg(t, "📋 Вас сняли с роли проверяющего. Команды /verify, /deny, /card и /clearcard больше недоступны.")
    else:
        set_setting(0, key, "1"); send_msg(peer, "✅ {} назначен проверяющим.".format(silent_mention_badge(t, peer))); send_msg(t, INSPECTOR_WELCOME)
def do_clear_card_command(peer, sender, args):
    param = None
    for a in args:
        al = a.strip(".,!?").lower()
        if al in PARAM_MAP: param = al; break
    if args and param is None: send_msg(peer, "❌ Нет такого параметра: {}. Доступные параметры: {} (или без параметра — очистит всё кроме цвета).".format(" ".join(args), PARAM_HINT)); return
    if param:
        if param == "фото": set_design(sender, photo=""); send_msg(peer, "✅ Фото вашей карты сброшено.")
        else: field = PARAM_MAP[param]; set_card_field(sender, **{field: FIELD_DEFAULT[field]}); send_msg(peer, "✅ Очищено поле «{}» вашей карточки.".format(param))
        return
    CLEAR_PENDING[(peer, sender)] = int(time.time()); send_msg(peer, CLEAR_CONFIRM_TEXT)
def check_clear_pending(peer, sender, text):
    ts = CLEAR_PENDING.get((peer, sender))
    if ts is None: return False
    low = text.strip().lower(); age = time.time() - ts
    if age > 60: CLEAR_PENDING.pop((peer, sender), None)
    if low in ("подтвердить", "отказаться"):
        if low == "подтвердить": CLEAR_PENDING.pop((peer, sender), None); clear_card_data(sender); send_msg(peer, "✅ Карточка очищена (кроме цвета)."); return True
        if low in ("отказаться", "отмена"): CLEAR_PENDING.pop((peer, sender), None); send_msg(peer, "❌ Очистка отменена."); return True
    return False

def handle_message(peer, sender, text, msg_obj):
    first_line = text.split("\n")[0].strip(); first = norm(first_line); user_cmid = msg_obj.get("conversation_message_id"); user_mid = msg_obj.get("id")
    if peer < 2000000000:
        low = text.strip().lower(); first_tok = low.split()[0] if low.split() else ""
        if first_tok == "/promo": handle_promo_use(peer, sender, text.strip()[len("/promo"):].strip()); return
        is_boss = sender in (CREATOR_ID, LEADER_ID) and peer == sender; is_insp = is_inspector(sender) and peer == sender; is_auct = is_auctioneer(sender) and peer == sender
        if is_boss:
            if low.startswith("бр форум") or low.startswith("br форум") or low.startswith("br forum"):
                rest = text.strip().split(None, 2); link = rest[2].strip() if len(rest) > 2 else ""
                if not link: send_msg(peer, "❌ Формат: бр форум <ссылка>"); return
                set_setting(0, "br_forum_link", link); send_msg(peer, "✅ Ссылка на форум установлена."); return
            if low.startswith("бр админы") or low.startswith("br админы") or low.startswith("br admins"):
                rest = text.strip().split(None, 2); link = rest[2].strip() if len(rest) > 2 else ""
                if not link: send_msg(peer, "❌ Формат: бр админы <ссылка>"); return
                set_setting(0, "br_admins_link", link); send_msg(peer, "✅ Ссылка на таблицу админов установлена."); return
            if low == "/чаты":
                send_msg(peer, "⏳ Загрузка списка бесед..."); chats = get_all_bot_chats()
                if not chats: send_msg(peer, "📭 Бот пока не зафиксировал ни одной беседы."); return
                lines = []; idx = 1
                for i in range(0, len(chats), 100):
                    chunk = chats[i:i+100]
                    try:
                        convos = VK.messages.getConversationsById(peer_ids=chunk)
                        for item in convos.get("items", []):
                            p_id = item.get("peer", {}).get("id", 0); title = item.get("chat_settings", {}).get("title", "Недоступно"); owner = item.get("chat_settings", {}).get("owner_id", 0)
                            if owner > 0: owner_link = silent_mention(owner)
                            elif owner < 0: owner_link = "[https://vk.com/club{}|Группа {}]".format(abs(owner), abs(owner))
                            else: owner_link = "Нет/ЛС"
                            member_count = "?"
                            try: mresp = VK.messages.getConversationMembers(peer_id=p_id); member_count = str(len(mresp.get("items", []))); time.sleep(0.15)
                            except: pass
                            lines.append("{}. {} | {} | {} | {} уч.".format(idx, p_id, title, owner_link, member_count)); idx += 1
                    except Exception as e: lines.append("Ошибка: {}".format(e))
                msg_text = "📊 Список бесед с ботом:\n" + "\n".join(lines)
                for i in range(0, len(msg_text), 4000): send_msg(peer, msg_text[i:i+4000])
                return
            elif low.startswith("/setkto"): handle_setkto(peer, sender, text[len("/setkto"):].strip()); return
            elif low.startswith("/inspector"): handle_inspector(peer, sender, text[len("/inspector"):].strip()); return
            elif low.startswith("/аукционеры"): handle_list_auctioneers(peer); return
            elif low.startswith("/аукционер"): handle_auctioneer_cmd(peer, sender, text[len("/аукционер"):].strip()); return
            elif low == "/проверяющие": handle_list_inspectors(peer); return
            elif low.startswith("/clearcard"): handle_clearcard(peer, sender, text[len("/clearcard"):].strip()); return
            elif low.startswith("/card"): handle_card_ls(peer, sender, text[len("/card"):].strip()); return
            elif low.startswith("/verify"): handle_verify(peer, sender, text[len("/verify"):].strip(), True); return
            elif low.startswith("/deny"): handle_verify(peer, sender, text[len("/deny"):].strip(), False); return
            elif low.startswith("/стопаукцион"): handle_stop_auction(peer, sender, text); return
            elif low.startswith("/отменить ласт ставку") or low.startswith("/отменить последнюю ставку"): handle_cancel_last_bid(peer, sender, text); return
            elif low.startswith("/некст лот") or low.startswith("/next lot"): handle_next_lot(peer, sender, text); return
            elif low == "/аукцион": open_auction_menu(peer, sender); return
            elif low == "/cpromo": open_promo_menu(peer, sender); return
            elif low.startswith("/voice"): handle_voice(peer, sender, msg_obj, text[len("/voice"):].strip()); return
            elif low.startswith("/экс карта"): handle_ex_card(peer, sender, text[len("/экс карта"):].strip(), True); return
            elif low.startswith("/забрать карту"): handle_ex_card(peer, sender, text[len("/забрать карту"):].strip(), False); return
            elif text.strip().startswith("/"): handle_creator_ls(peer, text); return
        elif is_insp or is_auct:
            if is_insp and low.startswith("/clearcard"): handle_clearcard(peer, sender, text[len("/clearcard"):].strip()); return
            elif is_insp and low.startswith("/card"): handle_card_ls(peer, sender, text[len("/card"):].strip()); return
            elif is_insp and low.startswith("/verify"): handle_verify(peer, sender, text[len("/verify"):].strip(), True); return
            elif is_insp and low.startswith("/deny"): handle_verify(peer, sender, text[len("/deny"):].strip(), False); return
            elif is_auct and low.startswith("/стопаукцион"): handle_stop_auction(peer, sender, text); return
            elif is_auct and (low.startswith("/отменить ласт ставку") or low.startswith("/отменить последнюю ставку")): handle_cancel_last_bid(peer, sender, text); return
            elif is_auct and (low.startswith("/некст лот") or low.startswith("/next lot")): handle_next_lot(peer, sender, text); return
            elif is_auct and low == "/аукцион": open_auction_menu(peer, sender); return
            elif low.startswith("/"): send_msg(peer, "❌ Неизвестная команда: {}\n\n".format(text.strip().split("\n")[0]) + ls_help_text(sender)); return
        if check_clear_pending(peer, sender, text): return
        if first.startswith("мд "):
            pn = first[3:].strip().split()
            if pn:
                c2 = "_".join(pn[:2])
                if c2 == "карта_редактировать" or c2 == "редактор_карты": handle_ls_card(peer, sender, "карта_редактировать", pn[2:]); return
                if c2 == "очистить_карту": do_clear_card_command(peer, sender, pn[2:]); return
                if pn[0] == "карта": handle_ls_card(peer, sender, "карта", pn[1:]); return
                if pn[0] == "команды": send_msg(peer, ls_help_text(sender)); return
                send_msg(peer, "❌ Неизвестная команда: `мд {}`\n\n".format(" ".join(pn)) + ls_help_text(sender)); return
        if text.strip().startswith("/"): send_msg(peer, "❌ Неизвестная команда: {}\n\n".format(text.strip().split("\n")[0]) + ls_help_text(sender)); return
        if handle_card_input(sender, peer, text, cmid=user_cmid, attachments=msg_obj.get("attachments")): return
        if handle_auction_input(sender, peer, text, cmid=user_cmid, attachments=msg_obj.get("attachments")): return
        if handle_promo_input(sender, peer, text, cmid=user_cmid, attachments=msg_obj.get("attachments")): return
        return

    # ===== ЧАТ: /card для проверяющих =====
    if sender > 0 and peer >= 2000000000:
        low0 = text.strip().lower()
        if low0.startswith("/card") and (is_inspector(sender) or sender in (CREATOR_ID, LEADER_ID)): handle_card_ls(peer, sender, text.strip()[len("/card"):].strip()); return

    # ===== ЧАТ: аукцион, ставки, контроль =====
    if sender > 0 and peer >= 2000000000:
        ra = get_running_auction(peer)
        if ra:
            active_window = bool(ra["current_lot_id"]) and ra["lot_deadline"] > int(time.time()); amount = parse_bid(text) if active_window else None
            if amount is not None:
                lot = get_lot(ra["current_lot_id"])
                if lot:
                    bid_id, best_uid, best = get_best_bid(lot["id"]); cur = best if best else 20000000.0
                    if best_uid == sender: send_msg(peer, "{}, вы уже лидер по этому лоту! Ставить повторно можно только после того, как вас перебили.".format(silent_mention_badge(sender, peer))); return
                    step = min_step_m(cur / 1e6) * 1e6
                    if amount < cur + step - 1e-6: send_msg(peer, "{}, ошибка, минимальный перебив {}!".format(silent_mention_badge(sender, peer), fmt_rub(step))); return
                    add_bid(lot["id"], sender, amount); now_ts = int(time.time())
                    with DB_LOCK: CONN.execute("UPDATE auctions SET lot_deadline=? WHERE id=?", (now_ts + 300, ra["id"])); CONN.commit()
                    set_setting(0, "auc_rem_{}".format(lot["id"]), str(now_ts))
                    send_msg(peer, "{}, ставка {} установлена! У остальных есть 5 минут чтобы ее перебить.".format(silent_mention_badge(sender, peer), fmt_rub(amount))); return
            if get_setting(0, "auc_clean_{}".format(peer), "0") == "1" and sender not in (CREATOR_ID, LEADER_ID) and not is_auctioneer(sender): delete_user_msg(peer, user_cmid, user_mid); return

    if not first.startswith("мд "):
        if check_clear_pending(peer, sender, text): return
        if handle_card_input(sender, peer, text, cmid=user_cmid, attachments=msg_obj.get("attachments")): return

    if sender > 0:
        is_sticker = any(att.get("type") == "sticker" for att in (msg_obj.get("attachments") or []))
        try: increment_msg_stat(peer, sender, is_sticker, len(text or ""))
        except: pass

    action = msg_obj.get("action", {})
    if action.get("type") == "chat_invite_user":
        user_id = action.get("member_id")
        if not user_id: return
        with DB_LOCK: ban_row = CONN.execute("SELECT ban_until FROM bans WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone()
        if ban_row and (ban_row["ban_until"] == 0 or ban_row["ban_until"] > int(time.time())):
            try: VK.messages.removeChatUser(chat_id=peer-2000000000, member_id=user_id); send_msg(peer, "🚫 {} забанен.".format(silent_mention_badge(user_id, peer)))
            except: pass
            return
        with DB_LOCK:
            row = CONN.execute("SELECT nickname FROM members WHERE user_id=? AND peer_id=?", (user_id, peer)).fetchone(); now_ts = int(time.time())
            if row: CONN.execute("UPDATE members SET join_time=?, warnings=0, warn_durations='', warn_expiry=0 WHERE user_id=? AND peer_id=?", (now_ts, user_id, peer))
            else: CONN.execute("INSERT INTO members(user_id, peer_id, join_time, warnings, warn_durations, warn_expiry) VALUES(?,?,?,0,'',0)", (user_id, peer, now_ts))
            CONN.execute("INSERT OR IGNORE INTO join_stats(user_id, peer_id, first_join, in_top) VALUES(?,?,?,1)", (user_id, peer, now_ts))
            CONN.execute("UPDATE join_stats SET in_top=1 WHERE user_id=? AND peer_id=?", (user_id, peer)); CONN.commit()
        greeting = get_setting(peer, "greeting_text", "")
        if greeting: send_msg(peer, greeting + "\n\n" + mention(user_id))
        elif get_setting(peer, "control_active") == "1": send_msg(peer, "Добро пожаловать, {}! 🎉\nУстанови ник: `Мд ник <твой_ник>`".format(mention(user_id)))
        return
    if action.get("type") == "chat_kick_user":
        user_id = action.get("member_id")
        if user_id:
            with DB_LOCK: CONN.execute("DELETE FROM members WHERE user_id=? AND peer_id=?", (user_id, peer)); CONN.commit()
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

    with DB_LOCK: mute_row = CONN.execute("SELECT mute_until FROM members WHERE user_id=? AND peer_id=?", (sender, peer)).fetchone()
    if mute_row and mute_row["mute_until"] and mute_row["mute_until"] > time.time():
        if not is_moderator(sender, peer):
            try:
                if user_cmid: VK.messages.delete(peer_id=peer, conversation_message_ids=[user_cmid], delete_for_all=1)
            except: pass
            return

    if get_setting(peer, "silence_mode", "0") == "1":
        if not is_admin(sender, peer):
            try:
                if user_cmid: VK.messages.delete(peer_id=peer, conversation_message_ids=[user_cmid], delete_for_all=1)
            except: pass
            return

    update_member_activity(peer, sender)
    if check_clear_pending(peer, sender, text): return
    pend_raw = get_setting(peer, "top_clean_pending", "")
    if pend_raw:
        try: pend = json.loads(pend_raw)
        except: pend = None
        if pend:
            low = text.strip().lower()
            if low in ["подтвердить", "отменить"]:
                if int(time.time()) - pend.get("ts", 0) > 60: set_setting(peer, "top_clean_pending", ""); send_msg(peer, "⏰ Время подтверждения истекло. Очистка топа отменена."); return
                if pend.get("asker") != sender: send_msg(peer, "⛔ Подтвердить может только тот, кто запустил очистку."); return
                set_setting(peer, "top_clean_pending", "")
                if low == "отменить": send_msg(peer, "❌ Очистка топа отменена."); return
                execute_top_clean(peer, pend.get("targets") or None, pend.get("types") or ["msg_count", "char_count", "sticker_count", "dice_wins", "kmb_wins"]); send_msg(peer, "✅ Топ очищен."); return

    if sender > 0:
        cmid0 = user_cmid or 0
        if cmid0:
            with DB_LOCK:
                CONN.execute("INSERT INTO message_cache(peer_id, cmid, from_id, ts) VALUES(?,?,?,?)", (peer, cmid0, sender, int(time.time())))
                CONN.execute("DELETE FROM message_cache WHERE ts < ?", (int(time.time()) - 7*86400,)); CONN.commit()

    if not first.startswith("мд "): return
    parts_norm = first[3:].strip().split()
    if not parts_norm: send_msg(peer, "Меня кто то звал?🧐 «Мд команды» список команд."); return
    parts_orig = first_line[3:].strip().split(); found_cmd = None; found_idx = -1
    for i in range(len(parts_norm), 0, -1):
        candidate = "_".join(parts_norm[:i]).lower()
        if candidate in VALID_COMMANDS: found_cmd = candidate; found_idx = i; break
    if not found_cmd: found_cmd = parts_norm[0].lower(); found_idx = 1
    cmd = found_cmd.strip(); args = parts_orig[found_idx:] if found_idx <= len(parts_orig) else []
    if cmd in ["обьява", "объяв", "обьяв"]: cmd = "объява"
    if cmd in ["обьявы"]: cmd = "объявы"
    if cmd in ["кд_обьяв"]: cmd = "кд_объяв"
    if cmd == "предлист": cmd = "преды"
    if cmd == "кмб": cmd = "кнб"
    if cmd not in VALID_COMMANDS: send_msg(peer, "Меня кто то звал?🧐 «Мд команды» список команд."); return

    owner = is_owner(sender, peer); real_owner = is_real_owner(sender, peer); admin = is_admin(sender, peer); moderator = is_moderator(sender, peer); main_admin = is_main_admin(sender, peer); sender_role = get_user_role(peer, sender)
    reply_obj = msg_obj.get("reply_message", {}) or {}; has_reply = bool(reply_obj and isinstance(reply_obj, dict) and reply_obj.get("from_id")); reply_msg_id = reply_obj.get("conversation_message_id", 0) if has_reply else 0; reply_text = reply_obj.get("text", "") if has_reply else ""; reply_from = reply_obj.get("from_id", 0) if has_reply else 0

    if cmd == "команды": send_msg(peer, "📖 Команды MD BOT", keyboard=get_help_main_buttons())
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
        lines = ["👑 Владелец: {}".format(", ".join(owners_line) if owners_line else "не определён"), "🥷 Главные Админы(3): {}".format(", ".join(silent_mention_badge(u, peer) for u in main_admins) if main_admins else "отсутствуют"), "🛡 Админы(2): {}".format(", ".join(silent_mention_badge(u, peer) for u in admins_list) if admins_list else "отсутствуют"), "👮‍️ Модераторы(1): {}".format(", ".join(silent_mention_badge(u, peer) for u in moderators_list) if moderators_list else "отсутствуют")]
        send_msg(peer, "\n".join(lines))
    elif cmd == "участник":
        target_id = sender
        if args or has_reply:
            targets = extract_targets(" ".join(args), reply_from)
            if targets:
                target_id = targets[0]
                if target_id != sender and not is_moderator(sender, peer): send_msg(peer, "⛔ Чужую статистику могут смотреть только модераторы и выше."); return
        with DB_LOCK:
            row = CONN.execute("SELECT nickname, warnings, warn_durations, warn_expiry, streak, join_time, who_name, who_ts FROM members WHERE user_id=? AND peer_id=?", (target_id, peer)).fetchone()
            js_row = CONN.execute("SELECT first_join FROM join_stats WHERE user_id=? AND peer_id=?", (target_id, peer)).fetchone()
            st_row = CONN.execute("SELECT s.name FROM user_statuses us JOIN statuses s ON us.status_id=s.id WHERE us.user_id=? AND us.peer_id=?", (target_id, peer)).fetchone()
        if not row and target_id not in (CREATOR_ID, LEADER_ID): send_msg(peer, "ℹ️ Участник {} еще не проявлял активность.".format(silent_mention_badge(target_id, peer))); return
        nick = row["nickname"] if row else "Не установлен"; warns = row["warnings"] if row else 0; durations_raw = row["warn_durations"] if row else "0"; max_warns = int(get_setting(peer, "max_warns", "3") or "3"); streak = row["streak"] if row else 0; role_str = get_role_display(peer, target_id)
        marriage = get_marriage(peer, target_id); marriage_str = "💍 В браке с {}".format(silent_mention_badge(get_marriage_partner(marriage, target_id), peer)) if marriage else "💍 Не состоит в браке"
        join_ts = row["join_time"] if row and row["join_time"] else 0
        if not join_ts and js_row: join_ts = js_row["first_join"]
        first_ts = js_row["first_join"] if js_row else 0
        join_line = "📅 В чате: с {} ({} дн.)".format(fmt_join_date(join_ts), days_since(join_ts)) if join_ts else "📅 В чате: неизвестно"
        first_line_txt = "📅 Первый вход: {} ({} дн.)".format(fmt_join_date(first_ts), days_since(first_ts)) if first_ts else "📅 Первый вход: неизвестно"
        status_str = "🎯Статус: {}".format(st_row["name"]) if st_row else "🎯Статус: Отсутствует."
        who_name = row["who_name"] if row and row["who_name"] else ""; who_ts = row["who_ts"] if row else 0
        if who_name: who_line = "👤 Кто это: {}".format(who_name) if int(time.time()) - who_ts <= 86400 else "🫆 Раньше был: {} ({})".format(who_name, fmt_join_date(who_ts))
        else: who_line = "👤 Кто это: не определено"
        msg = ("👥 Участник {}:\n🎮 Ник: {}\n⚠️ Предупреждений: {}/{} ({} дн.)\n{}\n{}\n🙆‍️ Роль: {}\n{}\n{}\n🔥 Серия посещения: {} дн. {}\n{}").format(silent_mention_badge(target_id, peer), nick, warns, max_warns, durations_raw, join_line, first_line_txt, role_str, status_str, marriage_str, streak, get_streak_emoji(streak), who_line)
        send_msg(peer, msg)
    elif cmd == "ники":
        try:
            page = int(args[0]) if args and args[0].isdigit() else 1
            with DB_LOCK:
                total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND nickname!='' AND nickname IS NOT NULL", (peer,)).fetchone()[0]
                rows = CONN.execute("SELECT user_id, nickname FROM members WHERE peer_id=? AND nickname!='' AND nickname IS NOT NULL ORDER BY user_id LIMIT 40 OFFSET ?", (peer, (page-1)*40)).fetchall()
            if not rows: send_msg(peer, "📝 Никого с ником нет."); return
            per_page = 40; total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages)); lines = ["📝 Ники (стр. {}/{}):\n".format(page, total_pages)]
            for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append('{}. {} — "{}"'.format(idx, silent_mention_badge(r["user_id"], peer), r["nickname"]))
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
            per_page = 40; total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages)); lines = ["👥 Участники (стр. {}/{}):\n".format(page, total_pages)]
            for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append('{}. {} — "{}"'.format(idx, silent_mention_badge(r["user_id"], peer), r["nickname"] or "Не установлен"))
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
            target_id = targets[0]; nick_args = [a for a in args if not re.match(r"^\[id\d+\|", a) and not re.match(r"^@id\d+", a) and not re.match(r"^\d{5,}$", a)]
            if not nick_args: send_msg(peer, "❌ Укажите ник."); return
            new_nick = " ".join(nick_args)
            with DB_LOCK:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (target_id, peer))
                CONN.execute("UPDATE members SET nickname=? WHERE user_id=? AND peer_id=?", (new_nick, target_id, peer)); CONN.commit()
            send_msg(peer, "✅ Ник {} установлен: {}".format(silent_mention_badge(target_id, peer), new_nick))
        else:
            new_nick = " ".join(args)
            with DB_LOCK:
                CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (sender, peer))
                CONN.execute("UPDATE members SET nickname=? WHERE user_id=? AND peer_id=?", (new_nick, sender, peer)); CONN.commit()
            send_msg(peer, "✅ Твой ник установлен: {}".format(new_nick))
    elif cmd == "проверка":
        if not admin: send_msg(peer, "⛔ Только администратор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд проверка @игрок`"); return
        target_id = targets[0]
        kb = {"inline": True, "buttons": [[{"action": {"type": "callback", "label": "⚠️ Предупреждения", "payload": json.dumps({"cmd": "check_warns", "target": target_id})}, "color": "negative"}, {"action": {"type": "callback", "label": "🔇 Муты", "payload": json.dumps({"cmd": "check_mutes", "target": target_id})}, "color": "primary"}]]}
        send_msg(peer, "📜 История наказаний {} за месяц:".format(silent_mention_badge(target_id, peer)), keyboard=kb)
    elif cmd == "голоса":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        is_yesterday = args and args[0].lower() == "вчера"; target_date = (get_msk_now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d") if is_yesterday else get_msk_now().strftime("%Y-%m-%d"); day_name = "вчера" if is_yesterday else "сегодня"
        with DB_LOCK: rows = CONN.execute("SELECT user_id, COUNT(*) as count FROM poll_votes WHERE peer_id=? AND date=? GROUP BY user_id ORDER BY count DESC", (peer, target_date)).fetchall()
        if not rows: send_msg(peer, "🗳 {} никто не голосовал.".format(day_name)); return
        lines = ["🗳 Голоса за {} ({}):\n".format(day_name, target_date)]
        for r in rows: lines.append("• {} — {} раз(а)".format(silent_mention_badge(r['user_id'], peer), r['count']))
        send_msg(peer, "\n".join(lines))
    elif cmd in ["парк", "прем", "чат"]:
        key = {"парк": "park", "прем": "prem", "чат": "chat"}[cmd]; reply = msg_obj.get("reply_message", {})
        if reply and isinstance(reply, dict) and reply.get("text"):
            if not admin: send_msg(peer, "⛔ Только администраторы."); return
            with DB_LOCK: CONN.execute("INSERT OR REPLACE INTO info_blocks(peer_id, key, text) VALUES(?,?,?)", (peer, key, reply["text"].strip())); CONN.commit()
            send_msg(peer, "✅ Информация '{}' обновлена.".format(cmd))
        else:
            with DB_LOCK: row = CONN.execute("SELECT text FROM info_blocks WHERE peer_id=? AND key=?", (peer, key)).fetchone()
            if row and row["text"]: send_msg(peer, "📌 Информация ({}):\n{}".format(cmd.capitalize(), row['text']))
            else: send_msg(peer, "ℹ️ Информация '{}' не установлена.".format(cmd))
    elif cmd == "пред":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        duration_days = int(get_setting(peer, "default_warn_days", "7") or "7"); reason_parts = []
        for arg in args:
            if arg.isdigit() and not re.match(r"^\d{5,}$", arg): duration_days = int(arg)
            elif arg.lower() == "навсегда": duration_days = 9999
            elif not re.match(r"^\[id\d+\|", arg) and not re.match(r"^@id\d+", arg) and not re.match(r"^\d{5,}$", arg): reason_parts.append(arg)
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд пред @игрок причина`"); return
        reason = " ".join(reason_parts).strip()
        if not reason and not has_reply: send_msg(peer, "❌ Укажите причину."); return
        if not reason: reason = "Ответом на сообщение"
        max_warns = int(get_setting(peer, "max_warns", "3") or "3"); now = time.time(); expiry = now + (duration_days * 86400) if duration_days < 9999 else now + (36500 * 86400)
        for t_id in targets:
            if not can_punish(sender, t_id, peer): send_msg(peer, "⛔ Нельзя наказывать {}.".format(silent_mention_badge(t_id, peer))); continue
            days_str = "∞" if duration_days >= 9999 else str(duration_days)
            with DB_LOCK:
                row = CONN.execute("SELECT warnings, warn_durations, warn_reasons FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                if row:
                    cw = (row["warnings"] or 0) + 1; od = row["warn_durations"] or ""; orr = row["warn_reasons"] or ""
                    nd = "{}|{}".format(od, days_str) if od else days_str; nr = "{}|{}".format(orr, reason) if orr else reason
                    CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=?, warn_reasons=? WHERE user_id=? AND peer_id=?", (cw, nd, expiry, nr, t_id, peer))
                else:
                    cw = 1; nd = days_str; nr = reason
                    CONN.execute("INSERT INTO members(user_id, peer_id, warnings, warn_durations, warn_expiry, warn_reasons) VALUES(?,?,?,?,?,?)", (t_id, peer, cw, nd, expiry, nr))
                CONN.commit()
            add_punishment(peer, t_id, "warn", reason, reply_msg_id, reply_text, sender, duration_days * 1440)
            send_msg(peer, "⚠️ {} получает пред ({}/{}) ({} дн.). Причина: {}".format(silent_mention_badge(t_id, peer), cw, max_warns, nd, reason))
            if cw >= max_warns:
                try:
                    VK.messages.removeChatUser(chat_id=peer-2000000000, member_id=t_id); add_punishment(peer, t_id, "ban", "Автокик за {} предов".format(max_warns), 0, "", sender, 0)
                    with DB_LOCK: CONN.execute("UPDATE members SET warnings=0, warn_durations='', warn_expiry=0, warn_reasons='' WHERE user_id=? AND peer_id=?", (t_id, peer)); CONN.commit()
                except: pass
    elif cmd == "снять_пред":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд снять пред @игрок`"); return
        for t_id in targets:
            with DB_LOCK:
                row = CONN.execute("SELECT warnings, warn_durations, warn_reasons, warn_expiry FROM members WHERE user_id=? AND peer_id=?", (t_id, peer)).fetchone()
                if row and row["warnings"] and row["warnings"] > 0:
                    nw = row["warnings"] - 1; parts_d = (row["warn_durations"] or "").split("|")
                    if parts_d and parts_d[-1] != '': parts_d.pop()
                    parts_r = (row["warn_reasons"] or "").split("|")
                    if parts_r and parts_r[-1] != '': parts_r.pop()
                    ne = 0 if nw == 0 else (row["warn_expiry"] or 0)
                    CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=?, warn_reasons=? WHERE user_id=? AND peer_id=?", (nw, "|".join(parts_d), ne, "|".join(parts_r), t_id, peer)); CONN.commit()
                    send_msg(peer, "✅ С {} снято предупреждение. Осталось: {}".format(silent_mention_badge(t_id, peer), nw))
                else: send_msg(peer, "ℹ️ У {} нет предупреждений.".format(silent_mention_badge(t_id, peer)))
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
                    CONN.execute("UPDATE members SET warnings=0, warn_durations='', warn_expiry=0 WHERE user_id=? AND peer_id=?", (t_id, peer)); CONN.commit()
                add_punishment(peer, t_id, "ban", reason, reply_msg_id, reply_text, sender, 0)
                send_msg(peer, "🚫 {} забанен {}.".format(silent_mention_badge(t_id, peer), "навсегда" if ban_days <= 0 else "на {} дн.".format(ban_days)))
            except Exception as e: send_msg(peer, "❌ Не удалось забанить: {}".format(e))
    elif cmd == "разбан":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя."); return
        for t_id in targets:
            with DB_LOCK: res = CONN.execute("DELETE FROM bans WHERE user_id=? AND peer_id=?", (t_id, peer)); CONN.commit()
            send_msg(peer, "✅ {} разбанен.".format(silent_mention_badge(t_id, peer)) if res.rowcount > 0 else "ℹ️ {} не забанен.".format(silent_mention_badge(t_id, peer)))
    elif cmd == "баны":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        now_ts = int(time.time())
        with DB_LOCK: rows = CONN.execute("SELECT user_id, ban_until, reason FROM bans WHERE peer_id=?", (peer,)).fetchall()
        active = [r for r in rows if r["ban_until"] == 0 or r["ban_until"] > now_ts]
        if not active: send_msg(peer, "✅ Забаненных нет."); return
        lines = ["🚫 Забаненные:\n"]
        for r in active:
            dur = "навсегда" if r["ban_until"] == 0 else "{} дн.".format(max(0, (r["ban_until"] - now_ts) // 86400))
            lines.append("• {} — {} | {}".format(silent_mention_badge(r["user_id"], peer), dur, r["reason"] or "Не указана"))
        send_msg(peer, "\n".join(lines))
    elif cmd == "мут":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        targets = extract_targets(" ".join(args), reply_from); minutes = None; reason_parts = []
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
                CONN.execute("UPDATE members SET mute_until=?, mute_reason=? WHERE user_id=? AND peer_id=?", (mute_until, reason, t, peer)); CONN.commit()
            add_punishment(peer, t, "mute", reason, reply_msg_id, reply_text, sender, minutes)
            send_msg(peer, "🔇 {} получил мут на {} мин. Причина: {}".format(silent_mention_badge(t, peer), minutes, reason))
    elif cmd == "снять_мут":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд снять мут @игрок`"); return
        for t in targets:
            with DB_LOCK: CONN.execute("UPDATE members SET mute_until=0, mute_reason='' WHERE user_id=? AND peer_id=?", (t, peer)); CONN.commit()
            send_msg(peer, "🔊 Мут снят с {}.".format(silent_mention_badge(t, peer)))
    elif cmd == "муты":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        now_ts = int(time.time())
        with DB_LOCK: rows = CONN.execute("SELECT user_id, mute_until, mute_reason FROM members WHERE peer_id=? AND mute_until>?", (peer, now_ts)).fetchall()
        if not rows: send_msg(peer, "✅ Замученных нет."); return
        lines = ["🔇 Замученные:\n"]
        for r in rows:
            rem = r["mute_until"] - now_ts; d, h, m, s = rem//86400, (rem%86400)//3600, (rem%3600)//60, rem%60; tp = []
            if d > 0: tp.append("{} дн".format(d))
            if h > 0: tp.append("{} ч".format(h))
            if m > 0: tp.append("{} мин".format(m))
            tp.append("{} сек".format(s))
            lines.append("• {} — {} | {}".format(silent_mention_badge(r["user_id"], peer), " ".join(tp), r["mute_reason"] or "Не указана"))
        send_msg(peer, "\n".join(lines))
    elif cmd == "преды":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        page = int(args[0]) if args and args[0].isdigit() else 1; per_page = 20
        with DB_LOCK:
            total = CONN.execute("SELECT COUNT(*) FROM members WHERE peer_id=? AND warnings>0", (peer,)).fetchone()[0]
            rows = CONN.execute("SELECT user_id, warnings, warn_durations FROM members WHERE peer_id=? AND warnings>0 ORDER BY warnings DESC LIMIT ? OFFSET ?", (peer, per_page, (page-1)*per_page)).fetchall()
        if not rows: send_msg(peer, "✅ Предупреждений нет."); return
        total_pages = max(1, (total + per_page - 1) // per_page); page = max(1, min(page, total_pages)); lines = ["⚠️ Предупреждения (стр. {}/{}):\n".format(page, total_pages)]
        for idx, r in enumerate(rows, (page-1)*per_page+1): lines.append("{}. {} — {} пред. ({} дн.)".format(idx, silent_mention_badge(r["user_id"], peer), r["warnings"], r["warn_durations"] or "0"))
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
        subcmd = args[0].lower(); known_subs = ("создать", "удалить", "редактировать", "снять")
        if subcmd not in known_subs and not re.search(r"\[id\d+\||@id\d+|\b\d{5,}\b|vk\.(com|ru)/", args[0], re.I): send_msg(peer, "❌ Нет такой подкоманды: {}. Подкоманды: создать, удалить, редактировать, снять. Или `Мд статус @игрок <номер>`.".format(subcmd)); return
        if subcmd == "создать":
            name = " ".join(args[1:])
            if not name: send_msg(peer, "❌ Формат: `Мд статус создать <название>`"); return
            with DB_LOCK:
                try: CONN.execute("INSERT INTO statuses(peer_id, name) VALUES(?,?)", (peer, name)); CONN.commit(); send_msg(peer, "✅ Статус «{}» создан.".format(name))
                except: send_msg(peer, "❌ Уже существует.")
        elif subcmd == "удалить":
            if len(args) < 2 or not args[1].isdigit(): send_msg(peer, "❌ Формат: `Мд статус удалить <номер>`"); return
            sn = int(args[1])
            with DB_LOCK:
                rows = CONN.execute("SELECT id FROM statuses WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
                if sn < 1 or sn > len(rows): send_msg(peer, "❌ Не найден."); return
                sid = rows[sn-1]["id"]; CONN.execute("DELETE FROM statuses WHERE id=?", (sid,)); CONN.execute("DELETE FROM user_statuses WHERE status_id=?", (sid,)); CONN.commit()
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
                with DB_LOCK: CONN.execute("DELETE FROM user_statuses WHERE user_id=? AND peer_id=?", (t, peer)); CONN.commit()
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
                with DB_LOCK: CONN.execute("INSERT OR REPLACE INTO user_statuses(user_id, peer_id, status_id) VALUES(?,?,?)", (t, peer, sid)); CONN.commit()
            send_msg(peer, "✅ Назначены на статус «{}».".format(sname))
    elif cmd == "кости":
        if get_setting(peer, "games_disabled", "0") == "1": send_msg(peer, "⛔ Игры в этом чате запрещены."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд кости @игрок`"); return
        opponent = targets[0]
        if opponent == sender: send_msg(peer, "❌ Нельзя играть с самим собой!"); return
        if opponent in (CREATOR_ID, LEADER_ID, get_chat_owner(peer)): send_msg(peer, "❌ Нельзя вызвать владельца."); return
        if dice_blocked(peer, sender): send_msg(peer, "❌ Ты не можешь играть: оба наказания активны!"); return
        if dice_blocked(peer, opponent): send_msg(peer, "❌ {} не может играть!".format(silent_mention_badge(opponent, peer))); return
        expire_stale_games(peer)
        with DB_LOCK:
            active = CONN.execute("SELECT id FROM dice_games WHERE peer_id=? AND state IN ('pending','playing')", (peer,)).fetchone()
            active_kmb = CONN.execute("SELECT id FROM kmb_games WHERE peer_id=? AND state IN ('pending','choosing')", (peer,)).fetchone()
        if active or active_kmb: send_msg(peer, "❌ Уже идёт игра!"); return
        now = int(time.time())
        with DB_LOCK: cursor = CONN.execute("INSERT INTO dice_games(peer_id, initiator, opponent, state, created_at) VALUES(?,?,?,?,?)", (peer, sender, opponent, "pending", now)); game_id = cursor.lastrowid; CONN.commit()
        kb = json.dumps({"inline": True, "buttons": [[{"action": {"type": "callback", "label": "✅ Принять", "payload": json.dumps({"cmd": "dice_accept", "game_id": game_id})}, "color": "positive"}, {"action": {"type": "callback", "label": "❌ Отказаться", "payload": json.dumps({"cmd": "dice_decline", "game_id": game_id})}, "color": "negative"}]]})
        try:
            msg_id = VK.messages.send(peer_id=peer, message="🎲 {}, {} вызывает вас в кости! ⏰ 1 минута".format(silent_mention_badge(opponent, peer), silent_mention_badge(sender, peer)), keyboard=kb, random_id=random.getrandbits(31))
            cmid = resolve_cmid(peer, msg_id)
            with DB_LOCK: CONN.execute("UPDATE dice_games SET message_id=? WHERE id=?", (cmid, game_id)); CONN.commit()
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
        with DB_LOCK: cursor = CONN.execute("INSERT INTO kmb_games(peer_id, initiator, opponent, state, created_at) VALUES(?,?,?,?,?)", (peer, sender, opponent, "pending", now)); game_id = cursor.lastrowid; CONN.commit()
        kb = json.dumps({"inline": True, "buttons": [[{"action": {"type": "callback", "label": "✅ Принять", "payload": json.dumps({"cmd": "kmb_accept", "game_id": game_id})}, "color": "positive"}, {"action": {"type": "callback", "label": "❌ Отказаться", "payload": json.dumps({"cmd": "kmb_decline", "game_id": game_id})}, "color": "negative"}]]})
        try:
            msg_id = VK.messages.send(peer_id=peer, message="✊✌️✋ {}, {} вызывает вас на КНБ! ⏰ 1 минута".format(silent_mention_badge(opponent, peer), silent_mention_badge(sender, peer)), keyboard=kb, random_id=random.getrandbits(31))
            cmid = resolve_cmid(peer, msg_id)
            with DB_LOCK: CONN.execute("UPDATE kmb_games SET message_id=? WHERE id=?", (cmid, game_id)); CONN.commit()
        except: pass
    elif cmd == "айди":
        if not moderator: send_msg(peer, "⛔ Только модератор и выше."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд айди @игрок`"); return
        head = "🆔 Настоящий айди:" if len(targets) == 1 else "🆔 Настоящие айди:"; lines = [head]
        for t in targets: lines.append("• {} — {}".format(silent_mention_badge(t, peer), t))
        send_msg(peer, "\n".join(lines))
    elif cmd == "запретить_игры":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        set_setting(peer, "games_disabled", "1"); send_msg(peer, "🚫 Игры в этом чате запрещены.")
    elif cmd == "разрешить_игры":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        set_setting(peer, "games_disabled", "0"); send_msg(peer, "✅ Игры в этом чате разрешены.")
    elif cmd == "запретить_редактор":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        set_setting(peer, "card_edit_disabled", "1"); send_msg(peer, "🚫 Редактирование карт в этом чате запрещено.")
    elif cmd == "разрешить_редактор":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        set_setting(peer, "card_edit_disabled", "0"); send_msg(peer, "✅ Редактирование карт в этом чате разрешены.")
    elif cmd == "очистить_топ":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        group_fields = {"сообщений": ["msg_count", "char_count"], "эмодзи": ["sticker_count"], "стики": ["sticker_count"], "стикеров": ["sticker_count"], "кости": ["dice_wins"], "кнб": ["kmb_wins"]}
        group_names = {"сообщений": "символы/сообщения", "эмодзи": "эмодзи", "стики": "эмодзи", "стикеров": "эмодзи", "кости": "кости", "кнб": "кнб"}; selected = []; bad = []
        for arg in args:
            g = arg.lower()
            if g in group_fields:
                if g not in selected: selected.append(g)
            elif not re.search(r"\[id\d+\||@id\d+|\b\d{5,}\b|vk\.(com|ru)/", arg, re.I): bad.append(arg)
        if bad: send_msg(peer, "❌ Нет такого типа топа: {}. Доступные: сообщений, эмодзи, кости, кнб.".format(" ".join(bad))); return
        if not selected: selected = ["сообщений", "эмодзи", "кости", "кнб"]
        top_types = []
        for g in selected:
            for f in group_fields[g]:
                if f not in top_types: top_types.append(f)
        targets = extract_targets(" ".join(args), 0)
        if reply_from and reply_from not in targets: targets.append(reply_from)
        set_setting(peer, "top_clean_pending", json.dumps({"asker": sender, "ts": int(time.time()), "targets": targets, "types": top_types})); names = ", ".join(group_names[g] for g in selected)
        if targets: send_msg(peer, "⚠️ Очистить топ(ы) [{}] для: {}?\n«Подтвердить» или «Отменить». ⏰ 1 минута.".format(names, ", ".join(silent_mention_badge(t, peer) for t in targets)))
        else: send_msg(peer, "⚠️ Очистить топ(ы) [{}] для всех?\n«Подтвердить» или «Отменить». ⏰ 1 минута.".format(names))
    elif cmd == "чистка":
        if not admin: send_msg(peer, "⛔ Только администратор и выше."); return
        if not real_owner:
            last_clean = int(get_setting(peer, "last_clean_{}".format(sender), "0") or "0")
            if time.time() - last_clean < 30: send_msg(peer, "⏳ КД на очистку: {} сек.".format(30 - int(time.time() - last_clean))); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Укажите пользователя: `Мд чистка @игрок <число>`"); return
        target_id = targets[0]; count = None
        for a in args:
            if a.isdigit() and 1 <= len(a) <= 3: count = int(a)
        if count is None: send_msg(peer, "❌ Укажите число сообщений: `Мд чистка @игрок <число>` (максимум 50)."); return
        count = max(1, min(count, 50)); cmids = []; history_ok = True
        try:
            history = VK.messages.getHistory(peer_id=peer, count=200)
            for m in history.get("items", []):
                if m.get("from_id") == target_id:
                    cm = m.get("conversation_message_id") or m.get("id")
                    if cm: cmids.append(cm)
                    if len(cmids) >= count: break
        except Exception as e: print("clean history error:", e); history_ok = False
        if not history_ok:
            with DB_LOCK: rows = CONN.execute("SELECT cmid FROM message_cache WHERE peer_id=? AND from_id=? AND cmid>0 ORDER BY id DESC LIMIT ?", (peer, target_id, count)).fetchall()
            cmids = [r["cmid"] for r in rows]
        if not cmids: send_msg(peer, "ℹ️ Не найдено сообщений {} для удаления.".format(silent_mention_badge(target_id, peer))); return
        success = 0; failed = 0
        for cm in cmids:
            ok = False
            try: VK.messages.delete(peer_id=peer, conversation_message_ids=[cm], delete_for_all=1); ok = True
            except Exception:
                try: VK.messages.delete(peer_id=peer, message_ids=[cm], delete_for_all=1); ok = True
                except Exception: failed += 1
            if ok: success += 1
        if not real_owner: set_setting(peer, "last_clean_{}".format(sender), str(int(time.time())))
        if success > 0:
            msg = "🧹 Удалено {} сообщений {}.".format(success, silent_mention_badge(target_id, peer))
            if failed: msg += "\n⚠️ Не удалось удалить {}: VK не даёт удалить сообщения старше 24 часов.".format(failed)
            send_msg(peer, msg)
        else: send_msg(peer, "❌ Не удалось удалить ни одного сообщения (VK [15]).")
    elif cmd in ["адмчат", "admg"]:
        if not owner: send_msg(peer, "⛔ Только владелец."); return
        if args and args[0].lower() == "удалить":
            with DB_LOCK: CONN.execute("DELETE FROM settings WHERE peer_id=? AND key='admin_report_chat'", (peer,)); CONN.commit()
            send_msg(peer, "✅ Привязка удалена."); return
        if not args or not args[0].isdigit(): send_msg(peer, "📌 Текущий чат: `{}`".format(get_setting(peer, "admin_report_chat", "Не установлена"))); return
        set_setting(peer, "admin_report_chat", args[0]); send_msg(peer, "✅ Репорты в чат {}.".format(args[0]))
    elif cmd == "номер_чата":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        chat_owner_id = get_chat_owner(peer); send_msg(peer, "📌 Номер чата: {}\nСоздатель: {}".format(peer, silent_mention_badge(chat_owner_id, peer) if chat_owner_id else "Не определён"))
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
                set_setting(peer, "poll_start", str(sh)); set_setting(peer, "poll_end", str(eh)); set_setting(peer, "poll_minute", str(sm)); send_msg(peer, "✅ Опросы: {}:{} - {}:{}".format(sh, sm, eh, em))
            except: send_msg(peer, "❌ Формат: `Мд время опросов ЧЧ:ММ ЧЧ:ММ`")
        else: send_msg(peer, "❌ Формат: `Мд время опросов ЧЧ:ММ ЧЧ:ММ`")
    elif cmd == "защита":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        targets = extract_targets(" ".join(args), reply_from)
        if not targets:
            with DB_LOCK: protected = [int(r["user_id"]) for r in CONN.execute("SELECT user_id FROM members WHERE peer_id=? AND poll_protected=1", (peer,)).fetchall()]
            send_msg(peer, ("🛡 Защищенные: " + ", ".join(silent_mention_badge(x, peer) for x in protected)) if protected else "🛡 Нет защищенных."); return
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
            with DB_LOCK: CONN.execute("UPDATE members SET poll_protected=0 WHERE user_id=? AND peer_id=?", (t_id, peer)); CONN.commit()
            send_msg(peer, "✅ {} убран из защиты.".format(silent_mention_badge(t_id, peer)))
    elif cmd == "текст_др":
        if not owner: send_msg(peer, "⛔ Только владелец."); return
        reply = msg_obj.get("reply_message", {})
        if not isinstance(reply, dict) or not reply.get("text"):
            current = get_setting(peer, "birthday_text", ""); send_msg(peer, "📝 Текущий текст:\n{}".format(current) if current else "📝 Стандартный текст."); return
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
        src = int(reply.get("conversation_message_id", 0) or 0); att = parse_reply_attachments(reply)
        with DB_LOCK:
            try: CONN.execute("INSERT INTO reminders(peer_id, name, text, attachments, source_message_id, interval_minutes, repeat_count, next_trigger) VALUES(?,?,?,?,?,?,?,?)", (peer, name, reply.get("text", ""), att, src, minutes, rc, time.time() + minutes*60)); CONN.commit(); send_msg(peer, "✅ Напоминание «{}» создано. {} мин.".format(name, minutes))
            except: send_msg(peer, "❌ Уже существует.")
    elif cmd == "список":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        with DB_LOCK: rows = CONN.execute("SELECT id, name, interval_minutes, repeat_count, next_trigger, enabled FROM reminders WHERE peer_id=? ORDER BY id", (peer,)).fetchall()
        if not rows: send_msg(peer, "📭 Пусто."); return
        msg = "📋 Напоминания:\n"; now = time.time()
        for idx, r in enumerate(rows, 1):
            rem = max(0, r["next_trigger"] - now); msg += "#{} {} | {} мин | {}м {}с\n".format(idx, r['name'], r['interval_minutes'], int(rem//60), int(rem%60))
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
            if t in (CREATOR_ID, LEADER_ID, get_chat_owner(peer)): send_msg(peer, "❌ Нельзя менять роль владельца/лидера."); continue
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
            if t in (CREATOR_ID, LEADER_ID, get_chat_owner(peer)): send_msg(peer, "❌ Нельзя снять владельца/лидера."); continue
            old = get_user_role(peer, t)
            if old == 0: send_msg(peer, "ℹ️ {} уже участник.".format(silent_mention_badge(t, peer))); continue
            if old == 4 and not real_owner: send_msg(peer, "⛔ Только владелец."); continue
            if old >= sender_role and not real_owner: send_msg(peer, "⛔ Нельзя снять равного/выше."); continue
            set_user_role(peer, t, 0); send_msg(peer, "✅ {} теперь участник.".format(silent_mention_badge(t, peer)))
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
                tp = args[0].split(":"); ch = int(tp[0]); cm = int(tp[1]) if len(tp) > 1 else 0
                set_setting(peer, "check_hour", str(ch)); set_setting(peer, "check_minute", str(cm)); set_setting(peer, "last_23_check", ""); send_msg(peer, "✅ Проверка: {:02d}:{:02d}".format(ch, cm))
            except: send_msg(peer, "❌ Формат: `Мд проверка опроса ЧЧ:ММ`")
        else: send_msg(peer, "📌 Проверка: {:02d}:{:02d}".format(int(get_setting(peer, "check_hour", "23")), int(get_setting(peer, "check_minute", "0"))))
    elif cmd == "бр":
        if args and args[0].lower() in ("форум", "forum"):
            link = get_setting(0, "br_forum_link", ""); send_msg(peer, "🎮 Форум Black Russia: {}".format(link) if link else "❌ Ссылка на форум не установлена."); return
        if args and args[0].lower() in ("админы", "admins"):
            link = get_setting(0, "br_admins_link", ""); send_msg(peer, "🔹 Актуальная таблица администрации BR BLUE: {}".format(link) if link else "❌ Ссылка на таблицу не установлена."); return
        try:
            page = int(args[0]) if args and args[0].isdigit() else 1; text, kb, _ = build_br_page(page)
            if text is None: send_msg(peer, "❌ Нет данных."); return
            VK.messages.send(peer_id=peer, message=text, keyboard=kb, random_id=random.getrandbits(31))
        except Exception as e: send_msg(peer, "❌ Ошибка: {}".format(e))
    elif cmd == "объява":
        if peer != MD_CHAT_PEER: send_msg(peer, "❌ Только в основной беседе MD."); return
        reply = msg_obj.get("reply_message", {})
        if not reply or not isinstance(reply, dict) or not reply.get("conversation_message_id"): send_msg(peer, "❌ Ответь на сообщение."); return
        cd = int(get_setting(MD_CHAT_PEER, "announce_cd", "60") or "60"); last = int(get_setting(MD_CHAT_PEER, "last_announce_{}".format(sender), "0") or "0"); now = time.time()
        if last > 0 and (now - last) < cd * 60: send_msg(peer, "⏳ КД: {} мин.".format(int((cd*60-(now-last))/60)+1)); return
        cmid = reply.get("conversation_message_id"); chats = get_all_bot_chats(); sc = 0
        for cp in chats:
            if cp == MD_CHAT_PEER: continue
            if get_setting(cp, "announcements_enabled", "1") != "1": continue
            try:
                fj = json.dumps({"peer_id": MD_CHAT_PEER, "conversation_message_ids": [cmid]})
                VK.messages.send(peer_id=cp, message="📢 Объявление от семьи Million Dollars:", forward=fj, random_id=random.getrandbits(31)); sc += 1; time.sleep(0.4)
            except: pass
        set_setting(MD_CHAT_PEER, "last_announce_{}".format(sender), str(int(time.time()))); send_msg(peer, "✅ Объявление в {} чатов.".format(sc))
    elif cmd == "кд_объяв":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        if not args or not args[0].isdigit(): send_msg(peer, "📌 КД: {} мин.".format(get_setting(MD_CHAT_PEER, "announce_cd", "60"))); return
        m = int(args[0])
        if m < 1: send_msg(peer, "❌ Минимум 1 мин."); return
        set_setting(MD_CHAT_PEER, "announce_cd", str(m)); send_msg(peer, "✅ КД: {} мин.".format(m))
    elif cmd == "объявы":
        if not admin: send_msg(peer, "⛔ Только администраторы."); return
        cur = get_setting(peer, "announcements_enabled", "1")
        if cur == "1": set_setting(peer, "announcements_enabled", "0"); send_msg(peer, "🔕 Объявления ВЫКЛ.")
        else: set_setting(peer, "announcements_enabled", "1"); send_msg(peer, "🔔 Объявления ВКЛ.")
    elif cmd == "топ":
        kb = json.dumps({"inline": True, "buttons": [[{"action": {"type": "callback", "label": "💬 Символы / ✉ Сообщения", "payload": json.dumps({"cmd": "top_messages", "page": 1})}, "color": "primary"}, {"action": {"type": "callback", "label": "🎨 Стикеры", "payload": json.dumps({"cmd": "top_stickers", "page": 1})}, "color": "primary"}], [{"action": {"type": "callback", "label": "🎲 Кости", "payload": json.dumps({"cmd": "top_dice", "page": 1})}, "color": "primary"}, {"action": {"type": "callback", "label": "✊✌️✋ КНБ", "payload": json.dumps({"cmd": "top_kmb", "page": 1})}, "color": "primary"}], [{"action": {"type": "callback", "label": "💒 Браки", "payload": json.dumps({"cmd": "top_marriages", "page": 1})}, "color": "primary"}, {"action": {"type": "callback", "label": "📅 Дней в чате", "payload": json.dumps({"cmd": "top_days", "page": 1})}, "color": "primary"}, {"action": {"type": "callback", "label": "🔥 Серий", "payload": json.dumps({"cmd": "top_streaks", "page": 1})}, "color": "primary"}]]})
        send_msg(peer, "🏆 Топы чата — выберите категорию:", keyboard=kb)
    elif cmd == "браки":
        with DB_LOCK:
            rows_all = CONN.execute("SELECT user1, user2, created_at FROM marriages WHERE peer_id=? ORDER BY created_at DESC", (peer,)).fetchall(); active_rows = []
            for r in rows_all:
                m1 = CONN.execute("SELECT 1 FROM members WHERE user_id=? AND peer_id=?", (r["user1"], peer)).fetchone()
                m2 = CONN.execute("SELECT 1 FROM members WHERE user_id=? AND peer_id=?", (r["user2"], peer)).fetchone()
                if m1 or m2: active_rows.append(r)
        if not active_rows: send_msg(peer, "💒 Браков пока нет."); return
        now_ts = int(time.time()); lines = ["💒 Браки пользователей чата:\n"]
        for r in active_rows: lines.append("{} и {} ({} дн.)".format(silent_mention_badge(r["user1"], peer), silent_mention_badge(r["user2"], peer), (now_ts - r["created_at"]) // 86400))
        send_msg(peer, "\n".join(lines))
    elif cmd == "брак":
        targets = extract_targets(" ".join(args), reply_from)
        if not targets: send_msg(peer, "❌ Формат: `Мд брак @игрок`"); return
        target = targets[0]
        if target == sender: send_msg(peer, "❌ На себе жениться нельзя!"); return
        if get_marriage(peer, sender): send_msg(peer, "❌ Ты уже в браке!"); return
        if get_marriage(peer, target): send_msg(peer, "❌ {} уже в браке!".format(silent_mention_badge(target, peer))); return
        kb = json.dumps({"inline": True, "buttons": [[{"action": {"type": "callback", "label": "💍 Согласиться", "payload": json.dumps({"cmd": "marriage_accept", "proposer": sender, "target": target})}, "color": "positive"}, {"action": {"type": "callback", "label": "❌ Отказать", "payload": json.dumps({"cmd": "marriage_decline", "proposer": sender, "target": target})}, "color": "negative"}]]})
        try:
            msg_id = VK.messages.send(peer_id=peer, message="💍 {} делает предложение {}!\nЧто скажешь? ⏰ 1 минута".format(silent_mention_badge(sender, peer), mention(target)), keyboard=kb, random_id=random.getrandbits(31))
            cmid = resolve_cmid(peer, msg_id)
            with DB_LOCK: CONN.execute("INSERT INTO dice_games(peer_id, initiator, opponent, state, message_id, created_at) VALUES(?,?,?,?,?,?)", (peer, sender, target, "marriage", cmid, int(time.time()))); CONN.commit()
        except Exception as e: print("marriage send error:", e)
    elif cmd == "развод":
        marriage = get_marriage(peer, sender)
        if not marriage: send_msg(peer, "❌ Ты не в браке."); return
        if args and args[0].lower() == "подтвердить":
            partner = get_marriage_partner(marriage, sender)
            with DB_LOCK: CONN.execute("DELETE FROM marriages WHERE id=?", (marriage["id"],)); CONN.commit()
            set_setting(peer, "divorce_confirm_{}".format(sender), ""); send_msg(peer, "💔 {} и {} развелись.".format(silent_mention_badge(sender, peer), silent_mention_badge(partner, peer)))
        else:
            set_setting(peer, "divorce_confirm_{}".format(sender), "ожидание"); send_msg(peer, "🥲 Для подтверждения развода напишите: `Мд развод подтвердить`")
    elif cmd == "онлайн":
        try:
            members_resp = VK.messages.getConversationMembers(peer_id=peer); user_ids = [p["id"] for p in members_resp.get("profiles", []) if p.get("id", 0) > 0]
            if not user_ids: send_msg(peer, "❌ Нет участников."); return
            online_users = []
            for i in range(0, len(user_ids), 100):
                chunk = user_ids[i:i+100]
                try:
                    users_data = VK.users.get(user_ids=",".join(map(str, chunk)), fields="online,last_seen")
                    for u in users_data:
                        if u.get("online") == 1:
                            platform = (u.get("last_seen", {}) or {}).get("platform", 0); icon = "🍏" if platform in [2,3,4] else ("🖥️" if platform in [5,6] else "📱"); online_users.append((u.get("first_name", "") + " " + u.get("last_name", ""), icon, u["id"]))
                except: pass
            if not online_users: send_msg(peer, "📝 Никто не онлайн."); return
            lines = ["📝 Список пользователей онлайн:\n"]
            for idx, (name, icon, uid) in enumerate(online_users, 1): lines.append("{}. {} ({})".format(idx, silent_mention(uid), icon))
            send_msg(peer, "\n".join(lines))
        except Exception as e: send_msg(peer, "❌ Ошибка: {}".format(e))
    elif cmd == "др":
        try:
            sync_members(peer); now_msk = get_msk_now()
            with DB_LOCK: member_ids = [r["user_id"] for r in CONN.execute("SELECT user_id FROM members WHERE peer_id=?", (peer,)).fetchall()]
            if not member_ids: send_msg(peer, "❌ Нет участников."); return
            bdate_map = get_bdate_map(member_ids); fill_bdates_from_vk(peer, member_ids, bdate_map); upcoming = []
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
                if 0 <= diff <= 60: upcoming.append((diff, uid, get_zodiac(day, month), "{} {}".format(day, RU_MONTHS[month-1])))
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
        last_ts = int(get_setting(peer, "who_i_cd_{}".format(sender), "0") or "0"); now_ts = int(time.time()); diff = now_ts - last_ts
        if diff < 10800:
            rem = 10800 - diff; m, s = divmod(rem, 60); send_msg(peer, "⏳ {}, вы уже использовали эту команду. До следующего раза осталось {}:{:02d}".format(silent_mention_badge(sender, peer), m, s)); return
        with DB_LOCK: CONN.execute("INSERT OR IGNORE INTO members(user_id, peer_id) VALUES(?,?)", (sender, peer))
        if random.randint(1, 100) == 1:
            legend = random.choice(LEGENDARY_WHO)
            with DB_LOCK: CONN.execute("UPDATE members SET who_name=?, who_ts=? WHERE user_id=? AND peer_id=?", (legend, now_ts, sender, peer)); CONN.commit()
            set_setting(peer, "who_i_cd_{}".format(sender), str(now_ts)); send_msg(peer, "🍀 {}, поздравляю вы получили легендарный статус - {}! (Шанс 1%)".format(silent_mention_badge(sender, peer), legend)); return
        adj = random.choice(WHO_ADJ); noun = random.choice(WHO_NOUN); phrase = "{} {}".format(adj_form(adj, noun_gender(noun)), noun)
        with DB_LOCK: CONN.execute("UPDATE members SET who_name=?, who_ts=? WHERE user_id=? AND peer_id=?", (phrase, now_ts, sender, peer)); CONN.commit()
        set_setting(peer, "who_i_cd_{}".format(sender), str(now_ts)); send_msg(peer, "🍀 {}, вы - {}".format(silent_mention_badge(sender, peer), phrase))
    elif cmd == "кто":
        word = " ".join(args) if args else "это"
        try:
            members_resp = VK.messages.getConversationMembers(peer_id=peer); user_ids = [int(i.get("member_id", 0)) for i in members_resp.get("items", []) if int(i.get("member_id", 0)) > 0]
            if not user_ids: send_msg(peer, "❌ Нет участников."); return
            send_msg(peer, "💬 {},  очевидно, {} — {}!".format(silent_mention_badge(sender, peer), word, silent_mention_badge(random.choice(user_ids), peer)))
        except Exception as e: print("кто error:", e)
    elif cmd == "инфа": send_msg(peer, "💬 {}, вероятно, это {}%.".format(silent_mention_badge(sender, peer), random.randint(0, 100)))
    elif cmd == "монетка":
        result = random.choice([("орёл🪙", "выпал"), ("решка1️⃣", "выпала")]); send_msg(peer, "{}, {} {}!".format(silent_mention_badge(sender, peer), result[1], result[0]))
    elif cmd == "+правила":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        reply = msg_obj.get("reply_message", {})
        if not isinstance(reply, dict) or not reply.get("text"): send_msg(peer, "❌ Ответь на сообщение с правилами."); return
        set_setting(peer, "rules_text", reply["text"].strip()); send_msg(peer, "✅ Правила установлены.")
    elif cmd == "-правила":
        if not main_admin: send_msg(peer, "⛔ Только главный админ и выше."); return
        set_setting(peer, "rules_text", ""); send_msg(peer, "✅ Правила удалены.")
    elif cmd == "правила":
        rules = get_setting(peer, "rules_text", ""); send_msg(peer, "📜 Правила чата:\n{}".format(rules) if rules else "ℹ️ Правила не установлены.")
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
        greeting = get_setting(peer, "greeting_text", ""); send_msg(peer, "👋 Приветствие:\n{}".format(greeting) if greeting else "ℹ️ Приветствие не установлено.")
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
        with DB_LOCK: CONN.execute("INSERT OR REPLACE INTO badges(user_id, peer_id, emoji) VALUES(?,?,?)", (sender, peer, badge_str)); CONN.commit()
        send_msg(peer, "✅ Значок {} установлен!".format(badge_str))
    elif cmd == "удалить_значок":
        with DB_LOCK: CONN.execute("DELETE FROM badges WHERE user_id=? AND peer_id=?", (sender, peer)); CONN.commit()
        send_msg(peer, "✅ Значок удалён.")
    elif cmd == "значки":
        with DB_LOCK: rows = CONN.execute("SELECT user_id, emoji FROM badges WHERE peer_id=? AND emoji!=''", (peer,)).fetchall()
        if not rows: send_msg(peer, "ℹ️ Значков нет."); return
        lines = ["🏷 Значки участников:\n"]
        for r in rows: lines.append("{} — {}".format(silent_mention_badge(r["user_id"], peer), r["emoji"]))
        send_msg(peer, "\n".join(lines))
    elif cmd == "карта": send_card_to(peer, sender)
    elif cmd in ("карта_редактировать", "редактор_карты"):
        if args: send_msg(peer, "❌ У команды `Мд редактор карты` нет параметров."); return
        if get_setting(peer, "card_edit_disabled", "0") == "1": send_msg(peer, "❌ Редактирование карт в данном чате запрещено, используйте в ЛС с ботом."); return
        open_edit_menu(peer, sender)
    elif cmd == "очистить_карту": do_clear_card_command(peer, sender, args)

def timer_loop():
    while True:
        try:
            time.sleep(10)
            if VK is None: continue
            now_msk = get_msk_now(); today_str = now_msk.strftime("%Y-%m-%d"); now = int(time.time())
            for k in list(CLEAR_PENDING.keys()):
                if now - CLEAR_PENDING[k] > 60: CLEAR_PENDING.pop(k, None)
            # Таймаут редактора карт
            with DB_LOCK: stale = CONN.execute("SELECT user_id, peer_id, step, context FROM card_edit_state").fetchall()
            for row in stale:
                try: ctx = json.loads(row["context"] or "{}")
                except: ctx = {}
                if now - ctx.get("ts", 0) > 60:
                    uid, pid = row["user_id"], row["peer_id"]
                    with DB_LOCK: CONN.execute("DELETE FROM card_edit_state WHERE user_id=? AND peer_id=?", (uid, pid))
                    close_card_session(pid, ctx, "Время на редактирование вышло, {} вы бездействовали минуту⏳".format(mention(uid)))
            # Таймауты редакторов аукционов (5 мин), промокодов (1 мин), voice (1 мин)
            with DB_LOCK: astale = CONN.execute("SELECT user_id, peer_id, step, context FROM auction_state").fetchall()
            for row in astale:
                try: ctx = json.loads(row["context"] or "{}")
                except: ctx = {}
                age = now - ctx.get("ts", 0); uid, pid = row["user_id"], row["peer_id"]
                if row["step"].startswith("promo_"):
                    if age > 60:
                        with DB_LOCK: CONN.execute("DELETE FROM auction_state WHERE user_id=? AND peer_id=?", (uid, pid))
                        close_promo_session(pid, ctx, "⏰ Время редактора промокодов вышло, вы бездействовали минуту.")
                elif row["step"].startswith("voice_"):
                    if age > 60:
                        with DB_LOCK: CONN.execute("DELETE FROM auction_state WHERE user_id=? AND peer_id=?", (uid, pid))
                        _close_voice_menu(pid, ctx, "⏰ Меню рассылки закрыто из-за бездействия.")
                elif age > 300:
                    cm = ctx.get("msg_cmid"); mid = ctx.get("msg_id")
                    with DB_LOCK: CONN.execute("DELETE FROM auction_state WHERE user_id=? AND peer_id=?", (uid, pid))
                    for kw in (({"conversation_message_ids": [cm]} if cm else None), ({"message_ids": [mid]} if mid else None)):
                        if not kw: continue
                        try: VK.messages.delete(peer_id=pid, delete_for_all=1, **kw); break
                        except: continue
            # Старт аукционов по расписанию
            with DB_LOCK: sched = CONN.execute("SELECT * FROM auctions WHERE state='scheduled'").fetchall()
            for a in sched:
                dt = parse_auction_dt(a["datetime_str"])
                if dt and now_msk >= dt:
                    with DB_LOCK: CONN.execute("UPDATE auctions SET state='running' WHERE id=?", (a["id"],)); CONN.commit()
                    a2 = get_auction(a["id"]); lots = get_lots(a2["id"])
                    if not lots:
                        with DB_LOCK: CONN.execute("UPDATE auctions SET state='finished' WHERE id=?", (a2["id"],)); CONN.commit()
                        continue
                    start_lot(a2, 0)
            # Завершение лотов + напоминания каждую минуту
            with DB_LOCK: run = CONN.execute("SELECT * FROM auctions WHERE state='running'").fetchall()
            for a in run:
                a = dict(a)
                if not a["current_lot_id"]: continue
                lot = get_lot(a["current_lot_id"])
                if not lot: start_lot(a, a["current_lot_index"] or 0); continue
                remain = a["lot_deadline"] - now
                if remain <= 0: finish_lot(a, lot); continue
                last_rem = int(get_setting(0, "auc_rem_{}".format(lot["id"]), "0") or 0)
                if now - last_rem >= 60:
                    set_setting(0, "auc_rem_{}".format(lot["id"]), str(now)); bid_id, buid, bamt = get_best_bid(lot["id"]); mins_left = max(1, int(-(-remain // 60)))
                    if buid: send_msg(a["peer_id"], "⏳ До конца торгов за лот «{}» осталось {} мин. Последняя ставка: {} от {}.".format(lot["name"], mins_left, fmt_rub(bamt), silent_mention_badge(buid, a["peer_id"])))
                    else: send_msg(a["peer_id"], "⏳ До конца торгов за лот «{}» осталось {} мин. Ставок ещё нет — стартовая цена 20.000.000р.".format(lot["name"], mins_left))
            # Игры
            with DB_LOCK:
                expired = CONN.execute("SELECT * FROM dice_games WHERE state='pending' AND created_at <=?", (now-60,)).fetchall()
                if expired:
                    CONN.execute("UPDATE dice_games SET state='expired' WHERE state='pending' AND created_at <=?", (now-60,)); CONN.commit()
                    for g in expired: edit_game_message(g["peer_id"], g["id"], "⏰ Время вышло! {} не успел принять вызов от {} 🕐".format(silent_mention_badge(g["opponent"], g["peer_id"]), silent_mention_badge(g["initiator"], g["peer_id"])))
                stuck_dice = CONN.execute("SELECT * FROM dice_games WHERE state='playing' AND created_at <=?", (now-600,)).fetchall()
                if stuck_dice:
                    CONN.execute("UPDATE dice_games SET state='expired' WHERE state='playing' AND created_at <=?", (now-600,)); CONN.commit()
                    for g in stuck_dice: edit_game_message(g["peer_id"], g["id"], "⏰ Игра в кости закрыта из-за бездействия (10 минут).")
                exp_m = CONN.execute("SELECT * FROM dice_games WHERE state='marriage' AND created_at <=?", (now-60,)).fetchall()
                if exp_m:
                    CONN.execute("UPDATE dice_games SET state='marriage_expired' WHERE state='marriage' AND created_at <=?", (now-60,)); CONN.commit()
                    for g in exp_m: edit_game_message(g["peer_id"], g["id"], "⏰ Время предложения истекло! 💔")
                expired_kmb = CONN.execute("SELECT * FROM kmb_games WHERE state IN ('pending','choosing') AND created_at <=?", (now-60,)).fetchall()
                if expired_kmb:
                    CONN.execute("UPDATE kmb_games SET state='expired' WHERE state IN ('pending','choosing') AND created_at <=?", (now-60,)); CONN.commit()
                    for g in expired_kmb:
                        if g["state"] == "pending": edit_game_message(g["peer_id"], g["id"], "⏰ КНБ: время вышло!", table="kmb_games")
                        else: send_msg(g["peer_id"], "⏰ КНБ: время вышло! Игра закончена из-за AFK.")
                stuck_kmb = CONN.execute("SELECT * FROM kmb_games WHERE state='choosing' AND created_at <=?", (now-300,)).fetchall()
                if stuck_kmb:
                    CONN.execute("UPDATE kmb_games SET state='expired' WHERE state='choosing' AND created_at <=?", (now-300,)); CONN.commit()
                    for g in stuck_kmb: edit_game_message(g["peer_id"], g["id"], "⏰ КНБ закрыта из-за бездействия (5 минут).", table="kmb_games")
                pend_rows = CONN.execute("SELECT peer_id, value FROM settings WHERE key='top_clean_pending'").fetchall()
                for pr in pend_rows:
                    try: pend = json.loads(pr["value"])
                    except: pend = None
                    if not pend: set_setting(pr["peer_id"], "top_clean_pending", ""); continue
                    if int(time.time()) - pend.get("ts", 0) > 60: set_setting(pr["peer_id"], "top_clean_pending", ""); send_msg(pr["peer_id"], "⏰ Время подтверждения очистки топа истекло. Отменено.")
            with DB_LOCK: due = CONN.execute("SELECT * FROM dice_mentions WHERE next_trigger <=? AND end_time >?", (now, now)).fetchall()
            for dm in due:
                send_msg(dm["peer_id"], "🎲 {}, {} ".format(mention(dm["user_id"]), random.choice(DICE_PHRASES))); nt = now + dm["interval_minutes"] * 60
                with DB_LOCK:
                    if nt >= dm["end_time"]: CONN.execute("DELETE FROM dice_mentions WHERE id=?", (dm["id"],))
                    else: CONN.execute("UPDATE dice_mentions SET next_trigger=? WHERE id=?", (nt, dm["id"]))
                CONN.commit()
            with DB_LOCK:
                peers = CONN.execute("SELECT DISTINCT peer_id FROM reminders").fetchall()
                bday_peers = CONN.execute("SELECT DISTINCT peer_id FROM members").fetchall()
                control_peers = CONN.execute("SELECT DISTINCT peer_id FROM settings WHERE key='control_active' AND value='1'").fetchall()
            for p in peers:
                peer = p["peer_id"]; now_t = time.time()
                with DB_LOCK: due_rem = CONN.execute("SELECT id, name, text, attachments, source_message_id, interval_minutes, repeat_count, enabled FROM reminders WHERE peer_id=? AND next_trigger <=?", (peer, now_t)).fetchall()
                for rem in due_rem:
                    if rem["enabled"] == 1:
                        for _ in range(rem["repeat_count"] or 1):
                            if rem["source_message_id"]:
                                try:
                                    fj = json.dumps({"peer_id": peer, "conversation_message_ids": [rem["source_message_id"]]})
                                    VK.messages.send(peer_id=peer, message="🔔 Напоминание: {}\n@all".format(rem['name']), forward=fj, random_id=random.getrandbits(31))
                                except: send_msg(peer, "🔔 Напоминание: {}\n{}\n@all".format(rem['name'], rem['text']), attachments=rem["attachments"] or None)
                            else: send_msg(peer, "🔔 Напоминание: {}\n{}\n@all".format(rem['name'], rem['text']), attachments=rem["attachments"] or None)
                        time.sleep(0.5)
                        with DB_LOCK: CONN.execute("UPDATE reminders SET next_trigger=? WHERE id=?", (now_t + rem["interval_minutes"]*60, rem["id"])); CONN.commit()
                last_poll_msg = get_setting(peer, "last_poll_msg_id", ""); last_poll_time = int(get_setting(peer, "last_poll_time", "0") or "0")
                if last_poll_msg and last_poll_msg.isdigit() and (time.time() - last_poll_time) > 600:
                    try: VK.messages.delete(peer_id=peer, message_ids=[int(last_poll_msg)], delete_for_all=1)
                    except: pass
                    set_setting(peer, "last_poll_msg_id", ""); set_setting(peer, "last_poll_time", "0")
                if now_msk.hour == 0 and now_msk.minute == 0:
                    for p in bday_peers: check_birthdays(p["peer_id"])
                if now_msk.minute == 0:
                    peers_to_sync = list(set([p["peer_id"] for p in control_peers]))
                    if peers_to_sync: threading.Thread(target=sync_all_peers, args=(peers_to_sync,), daemon=True).start()
                    for p in control_peers:
                        peer = p["peer_id"]; sh = int(get_setting(peer, "poll_start", "10")); eh = int(get_setting(peer, "poll_end", "22")); pm = int(get_setting(peer, "poll_minute", "25")); ch = now_msk.hour
                        is_active = (sh <= ch <= eh) if sh <= eh else (ch >= sh or ch <= eh)
                        if now_msk.minute == pm and is_active:
                            lpk = "last_poll_{}{}".format(ch, pm)
                            if get_setting(peer, lpk, "0") != "1":
                                pct = int(time.time()); kb = json.dumps({"inline": True, "buttons": [[{"action": {"type": "callback", "label": "✅ Проголосовать: Я", "payload": json.dumps({"cmd": "poll_vote", "time": pct})}, "color": "positive"}]]})
                                try:
                                    mid = VK.messages.send(peer_id=peer, message="📊 Опрос: Кто заходит на этот кд? @all", keyboard=kb, random_id=random.getrandbits(31))
                                    set_setting(peer, lpk, "1"); set_setting(peer, "last_poll_msg_id", str(mid)); set_setting(peer, "last_poll_time", str(pct))
                                except: pass
                        check_time = now_msk.replace(hour=int(get_setting(peer, "check_hour", "23")), minute=int(get_setting(peer, "check_minute", "0")), second=0, microsecond=0)
                        if now_msk >= check_time and get_setting(peer, "last_23_check", "") != today_str:
                            admins = set(get_users_with_min_role(peer, 2)); admins.add(CREATOR_ID); admins.add(LEADER_ID); co = get_chat_owner(peer)
                            if co: admins.add(co)
                            with DB_LOCK:
                                members = CONN.execute("SELECT user_id FROM members WHERE peer_id=? AND poll_protected=0", (peer,)).fetchall()
                                voted = set(r["user_id"] for r in CONN.execute("SELECT user_id FROM poll_votes WHERE peer_id=? AND date=?", (peer, today_str)).fetchall())
                                mw = int(get_setting(peer, "max_warns", "3") or "3"); dd = int(get_setting(peer, "default_warn_days", "7") or "7"); expiry = time.time() + dd * 86400
                                inactive = [m["user_id"] for m in members if m["user_id"] not in voted and m["user_id"] not in admins]
                                if inactive:
                                    lines = ["⚠️ Неактивные за день (+1 пред):\n"]
                                    for uid in inactive:
                                        with DB_LOCK:
                                            row = CONN.execute("SELECT warnings, warn_durations FROM members WHERE user_id=? AND peer_id=?", (uid, peer)).fetchone()
                                            cw = (row["warnings"] or 0) + 1 if row else 1; od = row["warn_durations"] if row and row["warn_durations"] else ""
                                            ds = "∞" if dd >= 9999 else str(dd); nd = "{}|{}".format(od, ds) if od else ds
                                            CONN.execute("UPDATE members SET warnings=?, warn_durations=?, warn_expiry=? WHERE user_id=? AND peer_id=?", (cw, nd, expiry, uid, peer)); CONN.commit()
                                        lines.append("{} ({}/{})".format(silent_mention_badge(uid, peer), cw, mw))
                                        if cw >= mw:
                                            try:
                                                VK.messages.removeChatUser(chat_id=peer-2000000000, member_id=uid)
                                                with DB_LOCK: CONN.execute("UPDATE members SET warnings=0, warn_durations='', warn_expiry=0 WHERE user_id=? AND peer_id=?", (uid, peer)); CONN.commit()
                                            except: pass
                                    send_msg(peer, "\n".join(lines))
                                set_setting(peer, "last_23_check", today_str)
                if now_msk.minute == 0:
                    for p in control_peers:
                        peer = p["peer_id"]
                        with DB_LOCK: no_nicks = CONN.execute("SELECT user_id FROM members WHERE peer_id=? AND (nickname='' OR nickname IS NULL)", (peer,)).fetchall()
                        for u in no_nicks:
                            lr = int(get_setting(peer, "nick_rem_{}".format(u['user_id']), "0"))
                            if time.time() - lr > 3600:
                                send_msg(peer, "🔔 {}, установи ник: `Мд ник <ник>` !".format(mention(u['user_id'])))
                                set_setting(peer, "nick_rem_{}".format(u['user_id']), str(int(time.time())))
        except Exception as e: print("timer error:", e)
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
