import os, json, re, random, urllib.request, urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TOKEN = os.environ["BOT_TOKEN"]
OWNER = os.environ.get("OWNER_ID", "").strip()
OWNER = int(OWNER) if OWNER else None
TZ = ZoneInfo("Asia/Tashkent")
STATE = "state.json"

PHRASES = [
    "Аббосхон, привет! Тихо напоминаю: {task}. Ты отлично справляешься, у тебя всё получится 🌿",
    "Мягкое напоминание: {task}. Сделай это в своём темпе, ты молодец, что помнишь о важном ✨",
    "Эй, ты не один(а) с этим. Пора: {task}. Один небольшой шаг, и станет легче 💛",
    "Время для: {task}. Я верю в тебя, и у тебя уже есть всё, чтобы с этим справиться 🌤",
    "Спокойно, без спешки: {task}. Ты уже многое сделал(а), и это тоже получится 🍀",
]

HELP = (
    "Привет! Напиши мне, например:\n"
    "• напомни завтра 10:00 сдать работу\n"
    "• напомни 25.11 18:00 позвонить Тимуру\n"
    "• напомни через 2 часа выпить воды\n\n"
    "Команды: список, удали 1"
)


def api(method, **params):
    data = urllib.parse.urlencode(params).encode()
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
        return json.load(r)


def send(chat, text):
    api("sendMessage", chat_id=chat, text=text)


def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"offset": 0, "tasks": []}


def save(st):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)


def parse(text, base):
    t = re.sub(r"^\s*(/remind|напомни)\s*", "", text, flags=re.I).strip()
    m = re.match(r"через\s+(\d+)\s*(мин|час|ч\b|д)\S*\s+(.+)", t, re.I | re.S)
    if m:
        n, unit, task = int(m.group(1)), m.group(2).lower(), m.group(3)
        delta = timedelta(minutes=n) if unit.startswith("м") else (
            timedelta(hours=n) if unit.startswith("ч") else timedelta(days=n))
        return base + delta, task.strip()
    m = re.match(r"(сегодня|завтра|послезавтра)\s+(?:(?:в\s+)?(\d{1,2})[:.](\d{2})\s+)?(.+)", t, re.I | re.S)
    if m:
        days = {"сегодня": 0, "завтра": 1, "послезавтра": 2}[m.group(1).lower()]
        h, mi = (int(m.group(2)), int(m.group(3))) if m.group(2) else (9, 0)
        d = (base + timedelta(days=days)).replace(hour=h, minute=mi, second=0, microsecond=0)
        return d, m.group(4).strip()
    m = re.match(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s+(?:(?:в\s+)?(\d{1,2})[:.](\d{2})\s+)?(.+)", t, re.S)
    if m:
        day, mon = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else base.year
        h, mi = (int(m.group(4)), int(m.group(5))) if m.group(4) else (9, 0)
        try:
            return datetime(year, mon, day, h, mi, tzinfo=TZ), m.group(6).strip()
        except ValueError:
            return None
    return None


def fmt(d):
    return d.strftime("%d.%m в %H:%M")


def handle(msg, st):
    chat = msg["chat"]["id"]
    text = msg["text"].strip()
    base = datetime.fromtimestamp(msg["date"], TZ)
    low = text.lower()
    if low in ("/start", "помощь", "/help"):
        send(chat, HELP)
    elif low in ("список", "/list"):
        mine = [t for t in st["tasks"] if not t["sent"]]
        if not mine:
            send(chat, "Пока нет запланированных напоминаний.")
        else:
            send(chat, "\n".join(f"{i}. {fmt(datetime.fromisoformat(t['at']))} — {t['text']}" for i, t in enumerate(mine, 1)))
    elif re.match(r"(удали|/del)\s+\d+", low):
        n = int(re.search(r"\d+", low).group())
        mine = [t for t in st["tasks"] if not t["sent"]]
        if 1 <= n <= len(mine):
            st["tasks"].remove(mine[n - 1])
            send(chat, "Убрал, всё хорошо 🌿")
        else:
            send(chat, "Не нашёл такой номер. Напиши «список».")
    else:
        res = parse(text, base)
        if not res:
            send(chat, "Не совсем понял срок. " + HELP)
        elif res[0] <= base:
            send(chat, "Это время уже прошло. Попробуй указать позже.")
        else:
            st["tasks"].append({"text": res[1], "at": res[0].isoformat(), "sent": False})
            send(chat, f"Записал 💛 Напомню {fmt(res[0])}: {res[1]}")


def main():
    st = load()
    ups = api("getUpdates", offset=st["offset"], timeout=0).get("result", [])
    for u in ups:
        st["offset"] = u["update_id"] + 1
        msg = u.get("message")
        if not msg or "text" not in msg:
            continue
        if OWNER is None:
            send(msg["chat"]["id"], f"Твой ID: {msg['chat']['id']}. Добавь его в секрет OWNER_ID на GitHub.")
        elif msg["chat"]["id"] == OWNER:
            handle(msg, st)
    if OWNER is not None:
        now = datetime.now(TZ)
        for t in st["tasks"]:
            if not t["sent"] and datetime.fromisoformat(t["at"]) <= now:
                send(OWNER, random.choice(PHRASES).format(task=t["text"]))
                t["sent"] = True
        st["tasks"] = [t for t in st["tasks"] if not t["sent"]]
    save(st)


main()
