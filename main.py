"""
Telegram Shop Bot — Спортивне харчування
Стек: Python 3.10+, aiogram 3.x, aiosqlite
"""

import asyncio
import csv
import io
import logging
import os
import urllib.request
import openpyxl
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
import aiosqlite

# ─────────────────────────────────────────
#  НАЛАШТУВАННЯ
# ─────────────────────────────────────────
BOT_TOKEN   = "8620629928:AAHQ-1xoohNkFESNApf9Z2KaG4Rb4CFPIMw"
ADMIN_ID    = 872996070
DB_PATH     = "shop.db"
SHEET_ID    = "1l4ONQZmxujosdjZpDV51HG7ZSHIw_Vra-lkG_7R_6ck"
SYNC_EVERY  = 600  # секунд (10 хвилин)
# ─────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp  = Dispatcher(storage=MemoryStorage())

EXCEL_PATH = "catalog.xlsx"

# ══════════════════════════════════════════
#  ЧИТАННЯ КАТАЛОГУ З GOOGLE SHEETS
# ══════════════════════════════════════════

def load_catalog_from_sheets() -> dict:
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        text = resp.read().decode("utf-8")
        reader = csv.reader(io.StringIO(text))
        next(reader, None)  # пропустити заголовок
        catalog = {}
        for row in reader:
            if len(row) < 4 or not row[0] or not row[1]:
                continue
            category, name, weight = row[0].strip(), row[1].strip(), row[2].strip()
            try:
                price = float(row[3].strip().replace(",", "."))
            except ValueError:
                continue
            catalog.setdefault(category, []).append((name, weight, price))
        logging.info(f"Завантажено з Google Sheets: {sum(len(v) for v in catalog.values())} товарів")
        return catalog
    except Exception as e:
        logging.warning(f"Не вдалося завантажити Google Sheets: {e}. Використовую локальний файл.")
        return load_catalog_from_excel()

def load_catalog_from_excel() -> dict:
    catalog = {}
    if not os.path.exists(EXCEL_PATH):
        logging.warning(f"{EXCEL_PATH} not found")
        return catalog
    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        category, name, weight, price = row[0], row[1], row[2], row[3]
        if not name or price is None:
            continue
        catalog.setdefault(str(category), []).append(
            (str(name), str(weight) if weight else "", float(price))
        )
    return catalog

# ══════════════════════════════════════════
#  КАТАЛОГ (резервний, якщо немає Excel)
# ══════════════════════════════════════════
CATALOG = {
    "🏆 Протеїн": [
        ("Optimum Nutrition 100% Whey Gold Standard", "2.27 кг", 2500),
        ("Kevin Levrone Gold Whey", "2 кг", 1500),
        ("Kevin Levrone Gold ISO", "2 кг", 3300),
        ("MST Best Whey Protein", "2 кг", 2100),
        ("Dymatize ISO100", "1.6 кг", 3200),
        ("BSN Syntha-6", "2.27 кг", 2700),
        ("Rule 1 Whey Blend", "2.27 кг", 2300),
        ("Scitec 100% Whey", "2.35 кг", 2200),
    ],
    "💪 Гейнери": [
        ("Kevin Levrone Anabolic Mass", "3 кг", 1000),
        ("Kevin Levrone Gold Lean Mass", "3 кг", 3100),
        ("Optimum Nutrition Serious Mass", "5.4 кг", 2600),
        ("Mutant Mass", "6.8 кг", 2800),
        ("BSN True Mass", "4.7 кг", 2500),
    ],
    "⚡ Креатин": [
        ("Kevin Levrone Gold Creatine", "300 г", 700),
        ("Kevin Levrone Anabolic Creatine", "300 г", 790),
        ("Optimum Nutrition Creatine Powder", "300 г", 1300),
        ("Kevin Levrone Anabolic Crea10", "300 г", 750),
        ("MyProtein Creatine Monohydrate", "500 г", 900),
        ("Scitec Creatine Monohydrate", "300 г", 1000),
    ],
    "🔥 BCAA / EAA": [
        ("Optimum Nutrition BCAA 1000", "200 капсул", 700),
        ("Optimum Nutrition Amino Energy", "270 г", 800),
        ("Kevin Levrone BCAA Defender", "400 г", 900),
        ("XTEND BCAA", "430 г", 1200),
        ("MST BCAA Powder", "400 г", 700),
    ],
    "🚀 Передтренувальні": [
        ("C4 Original (Cellucor)", "390 г", 1200),
        ("Optimum Nutrition Pre-Workout", "300 г", 1100),
        ("Kevin Levrone Gold Pre Workout", "300 г", 1000),
        ("MST Pump Killer", "300 г", 950),
        ("BSN NO-Xplode", "600 г", 1300),
    ],
    "🔻 Жироспалювачі": [
        ("L-Carnitine (BioTech)", "500 мл", 700),
        ("Kevin Levrone Fat Burner", "60 капсул", 900),
        ("Animal Cuts", "42 пакети", 1400),
        ("Nutrex Lipo-6", "120 капсул", 1300),
        ("MST Fat Burner", "90 капсул", 800),
    ],
    "🧬 Вітаміни та мінерали": [
        ("Optimum Nutrition Opti-Men", "90 таб", 900),
        ("Optimum Nutrition Opti-Women", "90 таб", 850),
        ("Animal Pak", "44 пакети", 1200),
        ("NOW Foods Multivitamin", "100 таб", 700),
        ("MST Multivitamin", "90 таб", 600),
    ],
    "🐟 Омега": [
        ("Omega-3 (NOW Foods)", "200 капсул", 600),
        ("Optimum Nutrition Fish Oil", "100 капсул", 500),
        ("MST Omega 3-6-9", "120 капсул", 550),
        ("BioTech Fish Oil", "100 капсул", 650),
    ],
    "🧪 Глютамін": [
        ("Optimum Nutrition Glutamine", "300 г", 900),
        ("MST Glutamine", "300 г", 700),
        ("Kevin Levrone Glutamine", "300 г", 800),
    ],
    "💊 Тестобустери": [
        ("Animal Test", "21 пакет", 1500),
        ("MST Test Booster", "90 капсул", 900),
        ("Kevin Levrone Testosterone Booster", "120 капсул", 1100),
    ],
    "🍫 Батончики": [
        ("Quest Bar", "60 г", 90),
        ("Optimum Nutrition Protein Bar", "60 г", 80),
        ("BSN Protein Crisp", "57 г", 70),
        ("BioTech Protein Bar", "70 г", 60),
    ],
    "🌿 Інше": [
        ("Collagen (NOW Foods)", "300 г", 800),
        ("ZMA (Optimum Nutrition)", "90 капсул", 600),
        ("Ашваганда (KSM-66)", "60 капсул", 500),
        ("Ізотонік (Isotonic Drink Powder)", "500 г", 400),
    ],
}

# ══════════════════════════════════════════
#  БАЗА ДАНИХ
# ══════════════════════════════════════════

PHOTO_MAP = {
    "Optimum Nutrition 100% Whey Gold Standard": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02861/v/69.jpg",
    "Kevin Levrone Gold Whey": "https://levrosupplements.com/134-large_default/gold-whey-2-kg.jpg",
    "Kevin Levrone Gold ISO": "https://levrosupplements.com/132-large_default/gold-iso-2-kg.jpg",
    "MST Best Whey Protein": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02861/v/69.jpg",
    "Dymatize ISO100": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/dyz/dyz35820/v/40.jpg",
    "BSN Syntha-6": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/bsn/bsn00720/v/37.jpg",
    "Rule 1 Whey Blend": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/rul/rul00493/v/40.jpg",
    "Scitec 100% Whey": "https://scitecnutrition.com/images/product_images/5146_8253f79d8cbe.webp",
    "Kevin Levrone Anabolic Mass": "https://levrosupplements.com/403-large_default/anabolic-mass-7-kg.jpg",
    "Kevin Levrone Gold Lean Mass": "https://levrosupplements.com/403-large_default/anabolic-mass-7-kg.jpg",
    "Optimum Nutrition Serious Mass": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02300/v/37.jpg",
    "Mutant Mass": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02300/v/37.jpg",
    "BSN True Mass": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/bsn/bsn00655/v/42.jpg",
    "Kevin Levrone Gold Creatine": "https://levrosupplements.com/113-large_default/gold-creatine-300-g.jpg",
    "Kevin Levrone Anabolic Creatine": "https://levrosupplements.com/113-large_default/gold-creatine-300-g.jpg",
    "Optimum Nutrition Creatine Powder": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02385/v/53.jpg",
    "Kevin Levrone Anabolic Crea10": "https://levrosupplements.com/113-large_default/gold-creatine-300-g.jpg",
    "MyProtein Creatine Monohydrate": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02385/v/53.jpg",
    "Scitec Creatine Monohydrate": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02385/v/53.jpg",
    "Optimum Nutrition BCAA 1000": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02036/v/48.jpg",
    "Optimum Nutrition Amino Energy": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02525/v/58.jpg",
    "Kevin Levrone BCAA Defender": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/sci/sci00027/v/5.jpg",
    "XTEND BCAA": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/sci/sci00027/v/5.jpg",
    "MST BCAA Powder": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/sci/sci00027/v/5.jpg",
    "C4 Original (Cellucor)": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/cll/cll12637/v/34.jpg",
    "Optimum Nutrition Pre-Workout": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02525/v/58.jpg",
    "Kevin Levrone Gold Pre Workout": "https://levrosupplements.com/113-large_default/gold-creatine-300-g.jpg",
    "MST Pump Killer": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/cll/cll12637/v/34.jpg",
    "BSN NO-Xplode": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/bsn/bsn00152/v/39.jpg",
    "L-Carnitine (BioTech)": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/nrx/nrx00773/v/67.jpg",
    "Kevin Levrone Fat Burner": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/nrx/nrx00773/v/67.jpg",
    "Animal Cuts": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/unn/unn03293/v/40.jpg",
    "Nutrex Lipo-6": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/nrx/nrx00773/v/67.jpg",
    "MST Fat Burner": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/nrx/nrx00773/v/67.jpg",
    "Optimum Nutrition Opti-Men": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn05223/v/56.jpg",
    "Optimum Nutrition Opti-Women": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02450/v/41.jpg",
    "Animal Pak": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/unn/unn03012/v/1.jpg",
    "NOW Foods Multivitamin": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/now/now03881/v/72.jpg",
    "MST Multivitamin": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/now/now03881/v/72.jpg",
    "Omega-3 (NOW Foods)": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/now/now01652/v/68.jpg",
    "Optimum Nutrition Fish Oil": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02984/v/13.jpg",
    "MST Omega 3-6-9": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/now/now01652/v/68.jpg",
    "BioTech Fish Oil": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/now/now01652/v/68.jpg",
    "Optimum Nutrition Glutamine": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02281/v/78.jpg",
    "MST Glutamine": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02281/v/78.jpg",
    "Kevin Levrone Glutamine": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02281/v/78.jpg",
    "Animal Test": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/unn/unn03032/v/83.jpg",
    "MST Test Booster": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/unn/unn03032/v/83.jpg",
    "Kevin Levrone Testosterone Booster": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/unn/unn03032/v/83.jpg",
    "Quest Bar": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/qst/qst01225/v/12.jpg",
    "Optimum Nutrition Protein Bar": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/qst/qst01225/v/12.jpg",
    "BSN Protein Crisp": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/bsn/bsn90692/v/56.jpg",
    "BioTech Protein Bar": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/qst/qst01225/v/12.jpg",
    "Collagen (NOW Foods)": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/now/now03008/v/49.jpg",
    "ZMA (Optimum Nutrition)": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02482/v/79.jpg",
    "Ашваганда (KSM-66)": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/now/now04633/v/8.jpg",
    "Ізотонік (Isotonic Drink Powder)": "https://cloudinary.images-iherb.com/image/upload/f_auto,q_auto:eco/images/opn/opn02525/v/58.jpg",
}

async def apply_photos_to_db(db):
    for name, url in PHOTO_MAP.items():
        await db.execute("UPDATE products SET photo_url=? WHERE name=?", (url, name))
    await db.commit()

async def sync_catalog_to_db():
    catalog = await asyncio.get_event_loop().run_in_executor(None, load_catalog_from_sheets)
    if not catalog:
        catalog = CATALOG
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM products")
        await db.execute("DELETE FROM categories")
        await db.commit()
        for cat_name, items in catalog.items():
            await db.execute("INSERT INTO categories (name) VALUES (?)", (cat_name,))
            cur2 = await db.execute("SELECT last_insert_rowid()")
            (cat_id,) = await cur2.fetchone()
            for name, weight, price in items:
                await db.execute(
                    "INSERT INTO products (category_id, name, weight, price, photo_url) VALUES (?,?,?,?,?)",
                    (cat_id, name, weight, price, PHOTO_MAP.get(name)),
                )
        await db.commit()
        await apply_photos_to_db(db)
    logging.info("Catalog synced from Excel successfully")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name        TEXT NOT NULL,
            weight      TEXT,
            price       REAL NOT NULL,
            photo_url   TEXT
        );
        CREATE TABLE IF NOT EXISTS cart (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty        INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS orders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            full_name  TEXT,
            phone      TEXT,
            address    TEXT,
            comment    TEXT,
            total      REAL,
            status     TEXT DEFAULT 'нове',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id   INTEGER NOT NULL,
            name       TEXT,
            weight     TEXT,
            price      REAL,
            qty        INTEGER
        );
        """)
        await db.commit()
    await sync_catalog_to_db()

# ══════════════════════════════════════════
#  FSM
# ══════════════════════════════════════════

class OrderFSM(StatesGroup):
    full_name = State()
    phone     = State()
    address   = State()
    comment   = State()

# ключ: (goal, gender, exp, budget)  budget: lo=до 600, mid=600-1500, hi=1500+
QUIZ_RECOMMENDATIONS = {
    # ── НАБІР МАСИ ──────────────────────────────────────────────────────
    ("mass","m","beginner","lo"): ["Optimum Nutrition Creatine Powder", "Optimum Nutrition BCAA 1000"],
    ("mass","m","beginner","mid"):["Optimum Nutrition 100% Whey Gold Standard", "Optimum Nutrition Creatine Powder", "Optimum Nutrition Opti-Men"],
    ("mass","m","beginner","hi"): ["Kevin Levrone Anabolic Mass", "Optimum Nutrition 100% Whey Gold Standard", "Optimum Nutrition Creatine Powder", "Optimum Nutrition Opti-Men"],
    ("mass","m","middle","lo"):   ["Optimum Nutrition Creatine Powder", "XTEND BCAA"],
    ("mass","m","middle","mid"):  ["BSN Syntha-6", "Optimum Nutrition Creatine Powder", "XTEND BCAA"],
    ("mass","m","middle","hi"):   ["Kevin Levrone Anabolic Mass", "BSN Syntha-6", "XTEND BCAA", "Optimum Nutrition Creatine Powder"],
    ("mass","m","advanced","lo"): ["Optimum Nutrition Creatine Powder", "XTEND BCAA"],
    ("mass","m","advanced","mid"):["Rule 1 Whey Blend", "Kevin Levrone Gold Creatine", "XTEND BCAA"],
    ("mass","m","advanced","hi"): ["Mutant Mass", "Dymatize ISO100", "C4 Original (Cellucor)", "Animal Test"],

    ("mass","f","beginner","lo"): ["Optimum Nutrition Opti-Women", "Optimum Nutrition Creatine Powder"],
    ("mass","f","beginner","mid"):["Scitec 100% Whey", "Optimum Nutrition Creatine Powder", "Optimum Nutrition Opti-Women"],
    ("mass","f","beginner","hi"): ["Kevin Levrone Anabolic Mass", "Scitec 100% Whey", "Optimum Nutrition Opti-Women"],
    ("mass","f","middle","lo"):   ["Optimum Nutrition Creatine Powder", "XTEND BCAA"],
    ("mass","f","middle","mid"):  ["BSN Syntha-6", "Optimum Nutrition Creatine Powder", "Optimum Nutrition Opti-Women"],
    ("mass","f","middle","hi"):   ["Kevin Levrone Anabolic Mass", "BSN Syntha-6", "XTEND BCAA", "Optimum Nutrition Opti-Women"],
    ("mass","f","advanced","lo"): ["Optimum Nutrition Creatine Powder", "MST BCAA Powder"],
    ("mass","f","advanced","mid"):["Rule 1 Whey Blend", "Kevin Levrone Gold Creatine", "XTEND BCAA"],
    ("mass","f","advanced","hi"): ["Mutant Mass", "Dymatize ISO100", "C4 Original (Cellucor)", "Optimum Nutrition Opti-Women"],

    # ── СХУДНЕННЯ ───────────────────────────────────────────────────────
    ("cut","m","beginner","lo"):  ["L-Carnitine (BioTech)"],
    ("cut","m","beginner","mid"): ["L-Carnitine (BioTech)", "Scitec 100% Whey", "Optimum Nutrition Opti-Men"],
    ("cut","m","beginner","hi"):  ["L-Carnitine (BioTech)", "Scitec 100% Whey", "Optimum Nutrition Opti-Men", "Optimum Nutrition Amino Energy"],
    ("cut","m","middle","lo"):    ["L-Carnitine (BioTech)", "XTEND BCAA"],
    ("cut","m","middle","mid"):   ["Nutrex Lipo-6", "L-Carnitine (BioTech)", "XTEND BCAA"],
    ("cut","m","middle","hi"):    ["Nutrex Lipo-6", "L-Carnitine (BioTech)", "XTEND BCAA", "Optimum Nutrition Amino Energy"],
    ("cut","m","advanced","lo"):  ["L-Carnitine (BioTech)", "MST BCAA Powder"],
    ("cut","m","advanced","mid"): ["Animal Cuts", "L-Carnitine (BioTech)", "MST BCAA Powder"],
    ("cut","m","advanced","hi"):  ["Animal Cuts", "MST Pump Killer", "Optimum Nutrition Amino Energy", "MST BCAA Powder"],

    ("cut","f","beginner","lo"):  ["L-Carnitine (BioTech)", "Optimum Nutrition Opti-Women"],
    ("cut","f","beginner","mid"): ["L-Carnitine (BioTech)", "Optimum Nutrition Opti-Women", "Scitec 100% Whey"],
    ("cut","f","beginner","hi"):  ["L-Carnitine (BioTech)", "Optimum Nutrition Opti-Women", "Scitec 100% Whey", "Optimum Nutrition Amino Energy"],
    ("cut","f","middle","lo"):    ["L-Carnitine (BioTech)", "MST BCAA Powder"],
    ("cut","f","middle","mid"):   ["Nutrex Lipo-6", "L-Carnitine (BioTech)", "XTEND BCAA"],
    ("cut","f","middle","hi"):    ["Nutrex Lipo-6", "L-Carnitine (BioTech)", "XTEND BCAA", "Optimum Nutrition Amino Energy"],
    ("cut","f","advanced","lo"):  ["L-Carnitine (BioTech)", "MST BCAA Powder"],
    ("cut","f","advanced","mid"): ["Animal Cuts", "L-Carnitine (BioTech)", "XTEND BCAA"],
    ("cut","f","advanced","hi"):  ["Animal Cuts", "MST Pump Killer", "L-Carnitine (BioTech)", "XTEND BCAA"],

    # ── СИЛА ТА ВИТРИВАЛІСТЬ ────────────────────────────────────────────
    ("strength","m","beginner","lo"):  ["Optimum Nutrition Creatine Powder", "Optimum Nutrition BCAA 1000"],
    ("strength","m","beginner","mid"): ["Optimum Nutrition Creatine Powder", "Rule 1 Whey Blend", "Optimum Nutrition Opti-Men"],
    ("strength","m","beginner","hi"):  ["Optimum Nutrition Creatine Powder", "Rule 1 Whey Blend", "Optimum Nutrition Opti-Men", "BSN NO-Xplode"],
    ("strength","m","middle","lo"):    ["Kevin Levrone Gold Creatine", "XTEND BCAA"],
    ("strength","m","middle","mid"):   ["BSN NO-Xplode", "Kevin Levrone Gold Creatine", "Rule 1 Whey Blend"],
    ("strength","m","middle","hi"):    ["BSN NO-Xplode", "Kevin Levrone Gold Creatine", "Rule 1 Whey Blend", "XTEND BCAA"],
    ("strength","m","advanced","lo"):  ["Kevin Levrone Anabolic Crea10", "MST BCAA Powder"],
    ("strength","m","advanced","mid"): ["MST Pump Killer", "Kevin Levrone Anabolic Crea10", "Kevin Levrone Gold Whey"],
    ("strength","m","advanced","hi"):  ["MST Pump Killer", "Kevin Levrone Anabolic Crea10", "Animal Test", "Kevin Levrone Gold Whey"],

    ("strength","f","beginner","lo"):  ["Optimum Nutrition Creatine Powder", "Optimum Nutrition Opti-Women"],
    ("strength","f","beginner","mid"): ["Optimum Nutrition Creatine Powder", "Rule 1 Whey Blend", "Optimum Nutrition Opti-Women"],
    ("strength","f","beginner","hi"):  ["Optimum Nutrition Creatine Powder", "Rule 1 Whey Blend", "Optimum Nutrition Opti-Women", "BSN NO-Xplode"],
    ("strength","f","middle","lo"):    ["Kevin Levrone Gold Creatine", "XTEND BCAA"],
    ("strength","f","middle","mid"):   ["BSN NO-Xplode", "Kevin Levrone Gold Creatine", "Rule 1 Whey Blend"],
    ("strength","f","middle","hi"):    ["BSN NO-Xplode", "Kevin Levrone Gold Creatine", "Rule 1 Whey Blend", "XTEND BCAA"],
    ("strength","f","advanced","lo"):  ["Kevin Levrone Anabolic Crea10", "MST BCAA Powder"],
    ("strength","f","advanced","mid"): ["MST Pump Killer", "Kevin Levrone Anabolic Crea10", "Kevin Levrone Gold Whey"],
    ("strength","f","advanced","hi"):  ["MST Pump Killer", "Kevin Levrone Anabolic Crea10", "XTEND BCAA", "Kevin Levrone Gold Whey"],

    # ── ЗАГАЛЬНЕ ЗДОРОВ'Я ───────────────────────────────────────────────
    ("health","m","beginner","lo"):  ["Omega-3 (NOW Foods)", "Optimum Nutrition Opti-Men"],
    ("health","m","beginner","mid"): ["Omega-3 (NOW Foods)", "Optimum Nutrition Opti-Men", "Collagen (NOW Foods)"],
    ("health","m","beginner","hi"):  ["Omega-3 (NOW Foods)", "Optimum Nutrition Opti-Men", "Collagen (NOW Foods)", "Optimum Nutrition Glutamine"],
    ("health","m","middle","lo"):    ["Omega-3 (NOW Foods)", "Optimum Nutrition Glutamine"],
    ("health","m","middle","mid"):   ["Animal Pak", "Omega-3 (NOW Foods)", "Optimum Nutrition Glutamine"],
    ("health","m","middle","hi"):    ["Animal Pak", "Omega-3 (NOW Foods)", "Optimum Nutrition Glutamine", "ZMA (Optimum Nutrition)"],
    ("health","m","advanced","lo"):  ["Omega-3 (NOW Foods)", "Optimum Nutrition Glutamine"],
    ("health","m","advanced","mid"): ["Animal Pak", "Omega-3 (NOW Foods)", "Optimum Nutrition Glutamine"],
    ("health","m","advanced","hi"):  ["Animal Pak", "Omega-3 (NOW Foods)", "Optimum Nutrition Glutamine", "Ашваганда (KSM-66)"],

    ("health","f","beginner","lo"):  ["Omega-3 (NOW Foods)", "Optimum Nutrition Opti-Women"],
    ("health","f","beginner","mid"): ["Omega-3 (NOW Foods)", "Optimum Nutrition Opti-Women", "Collagen (NOW Foods)"],
    ("health","f","beginner","hi"):  ["Omega-3 (NOW Foods)", "Optimum Nutrition Opti-Women", "Collagen (NOW Foods)", "Optimum Nutrition Glutamine"],
    ("health","f","middle","lo"):    ["Omega-3 (NOW Foods)", "Optimum Nutrition Glutamine"],
    ("health","f","middle","mid"):   ["Animal Pak", "Omega-3 (NOW Foods)", "Collagen (NOW Foods)"],
    ("health","f","middle","hi"):    ["Animal Pak", "Omega-3 (NOW Foods)", "Collagen (NOW Foods)", "Optimum Nutrition Glutamine"],
    ("health","f","advanced","lo"):  ["Omega-3 (NOW Foods)", "Optimum Nutrition Glutamine"],
    ("health","f","advanced","mid"): ["Animal Pak", "Omega-3 (NOW Foods)", "Optimum Nutrition Glutamine"],
    ("health","f","advanced","hi"):  ["Animal Pak", "Omega-3 (NOW Foods)", "Optimum Nutrition Glutamine", "Ашваганда (KSM-66)"],
}

PRODUCT_DESC = {
    "Optimum Nutrition 100% Whey Gold Standard": "🥛 Якісний протеїн для відновлення та росту м'язів після тренування",
    "Optimum Nutrition Creatine Powder":         "⚡ Збільшує силу та м'язову масу, покращує вибухову потужність",
    "Optimum Nutrition Opti-Men":                "💊 Комплекс вітамінів та мінералів для активних чоловіків",
    "Optimum Nutrition Opti-Women":              "💊 Комплекс вітамінів та мінералів спеціально для жінок",
    "Kevin Levrone Anabolic Mass":               "💪 Гейнер для набору маси — протеїн + вуглеводи в одному",
    "BSN Syntha-6":                              "🥛 Повільний протеїн для тривалого живлення м'язів",
    "XTEND BCAA":                                "🔄 BCAA для відновлення та захисту м'язів під час тренування",
    "Mutant Mass":                               "💪 Важкий гейнер для максимального набору ваги і маси",
    "Dymatize ISO100":                           "🥛 Ізолят протеїну — чистий білок без жирів і вуглеводів",
    "C4 Original (Cellucor)":                    "🔥 Передтренувальний комплекс для енергії та концентрації",
    "Animal Test":                               "🦁 Тестобустер для підвищення рівня тестостерону і сили",
    "L-Carnitine (BioTech)":                     "🔥 Спалює жир, перетворюючи його на енергію під час кардіо",
    "Scitec 100% Whey":                          "🥛 Протеїн для збереження м'язів при схудненні",
    "Nutrex Lipo-6":                             "🔥 Потужний жироспалювач для прискорення метаболізму",
    "Optimum Nutrition Amino Energy":            "⚡ Амінокислоти + кофеїн для енергії та відновлення",
    "MST BCAA Powder":                           "🔄 BCAA для захисту м'язів та прискорення відновлення",
    "Animal Cuts":                               "✂️ Потужний жироспалюючий комплекс для рельєфу",
    "MST Pump Killer":                           "💥 Передтренувальний без кофеїну для пампу та витривалості",
    "Rule 1 Whey Blend":                         "🥛 Протеїн для відновлення та зростання сили після тренувань",
    "BSN NO-Xplode":                             "🔥 Передтренувальний для вибухової сили та витривалості",
    "Kevin Levrone Gold Creatine":               "⚡ Чистий креатин моногідрат для максимального приросту сили",
    "Optimum Nutrition BCAA 1000":               "🔄 BCAA у капсулах для відновлення та антикатаболічного ефекту",
    "Kevin Levrone Anabolic Crea10":             "⚡ Крeatин з транспортною системою для кращого засвоєння",
    "Kevin Levrone Gold Whey":                   "🥛 Преміальний протеїн для набору сили та відновлення",
    "Omega-3 (NOW Foods)":                       "🐟 Омега-3 для здоров'я серця, суглобів та імунітету",
    "Collagen (NOW Foods)":                      "💧 Колаген для суглобів, шкіри та сполучних тканин",
    "Animal Pak":                                "💊 Легендарний вітамінний пак для атлетів — все в одному",
    "Optimum Nutrition Glutamine":               "🔄 Глютамін для відновлення, імунітету та здоров'я кишківника",
    "ZMA (Optimum Nutrition)":                   "😴 Цинк + магній + B6 для кращого сну та відновлення",
    "Ашваганда (KSM-66)":                        "🌿 Адаптоген для зниження стресу, сили та гормонального балансу",
}

# ══════════════════════════════════════════
#  КЛАВІАТУРИ
# ══════════════════════════════════════════

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Підібрати товар під мене")],
            [KeyboardButton(text="🛍 Каталог"),       KeyboardButton(text="🛒 Кошик")],
            [KeyboardButton(text="📋 Мої замовлення"), KeyboardButton(text="💬 Менеджер для консультацій")],
        ],
        resize_keyboard=True,
    )

def quiz_goals_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💪 Набір маси",          callback_data="qg:mass")],
        [InlineKeyboardButton(text="🔥 Схуднення",           callback_data="qg:cut")],
        [InlineKeyboardButton(text="⚡ Сила та витривалість", callback_data="qg:strength")],
        [InlineKeyboardButton(text="🌿 Загальне здоров'я",   callback_data="qg:health")],
    ])

def quiz_gender_kb(goal: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Чоловік", callback_data=f"qs:{goal}:m")],
        [InlineKeyboardButton(text="👩 Жінка",   callback_data=f"qs:{goal}:f")],
    ])

def quiz_exp_kb(goal: str, gender: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Початківець",     callback_data=f"qe:{goal}:{gender}:beginner")],
        [InlineKeyboardButton(text="🟡 Середній рівень", callback_data=f"qe:{goal}:{gender}:middle")],
        [InlineKeyboardButton(text="🔴 Просунутий",      callback_data=f"qe:{goal}:{gender}:advanced")],
    ])

def quiz_budget_kb(goal: str, gender: str, exp: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 До 1000 грн",      callback_data=f"qb:{goal}:{gender}:{exp}:lo")],
        [InlineKeyboardButton(text="💳 1000 – 2000 грн",  callback_data=f"qb:{goal}:{gender}:{exp}:mid")],
        [InlineKeyboardButton(text="💎 2000+ грн",         callback_data=f"qb:{goal}:{gender}:{exp}:hi")],
    ])

async def categories_kb() -> InlineKeyboardMarkup:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, name FROM categories ORDER BY id")
        rows = await cur.fetchall()
    buttons = [[InlineKeyboardButton(text=n, callback_data=f"cat:{cid}")] for cid, n in rows]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def products_kb(category_id: int) -> InlineKeyboardMarkup:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name, weight, price FROM products WHERE category_id=? ORDER BY id",
            (category_id,),
        )
        rows = await cur.fetchall()
    buttons = [
        [InlineKeyboardButton(
            text=f"{n} ({w}) — {p:.0f} грн",
            callback_data=f"prod:{pid}"
        )]
        for pid, n, w, p in rows
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Категорії", callback_data="catalog")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def product_detail_kb(product_id: int, category_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Додати до кошика", callback_data=f"add:{product_id}")],
        [InlineKeyboardButton(text="⬅️ Назад до категорії", callback_data=f"cat:{category_id}")],
    ])

async def cart_kb(user_id: int) -> InlineKeyboardMarkup:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT c.id, p.name, c.qty, p.price FROM cart c "
            "JOIN products p ON p.id=c.product_id WHERE c.user_id=?",
            (user_id,),
        )
        items = await cur.fetchall()
    buttons = []
    for cid, name, qty, price in items:
        short = name[:22] + "…" if len(name) > 22 else name
        buttons.append([
            InlineKeyboardButton(text="➖", callback_data=f"qdec:{cid}"),
            InlineKeyboardButton(text=f"{short} x{qty}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"qinc:{cid}"),
            InlineKeyboardButton(text="🗑", callback_data=f"qdel:{cid}"),
        ])
    if items:
        buttons.append([InlineKeyboardButton(text="✅ Оформити замовлення", callback_data="checkout")])
        buttons.append([InlineKeyboardButton(text="🗑 Очистити кошик", callback_data="clear_cart")])
    buttons.append([InlineKeyboardButton(text="🛍 До каталогу", callback_data="catalog")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ══════════════════════════════════════════
#  /start
# ══════════════════════════════════════════

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer(
        f"👋 Вітаємо, <b>{msg.from_user.first_name}</b>!\n\n"
        "🏋️ Ми продаємо спортивне харчування з доставкою.\n"
        "💳 Оплата — при отриманні.\n\n"
        "Оберіть розділ у меню нижче 👇",
        reply_markup=main_menu(),
    )

# ══════════════════════════════════════════
#  АДМІН — перезавантаження каталогу
# ══════════════════════════════════════════

@dp.message(Command("reload"))
async def cmd_reload(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer("🔄 Оновлюю каталог з Excel...")
    await sync_catalog_to_db()
    await msg.answer("✅ Каталог успішно оновлено!")

# ══════════════════════════════════════════
#  КАТАЛОГ
# ══════════════════════════════════════════

@dp.message(F.text == "🛍 Каталог")
async def show_catalog(msg: Message):
    await msg.answer("📂 <b>Оберіть категорію:</b>", reply_markup=await categories_kb())

async def safe_edit_or_resend(cb: CallbackQuery, text: str, reply_markup):
    if cb.message.photo:
        await cb.message.delete()
        await bot.send_message(cb.message.chat.id, text, reply_markup=reply_markup)
    else:
        await cb.message.edit_text(text, reply_markup=reply_markup)

@dp.callback_query(F.data == "catalog")
async def cb_catalog(cb: CallbackQuery):
    await safe_edit_or_resend(cb, "📂 <b>Оберіть категорію:</b>", await categories_kb())
    await cb.answer()

@dp.callback_query(F.data.startswith("cat:"))
async def cb_category(cb: CallbackQuery):
    cid = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name FROM categories WHERE id=?", (cid,))
        row = await cur.fetchone()
    name = row[0] if row else "Категорія"
    await safe_edit_or_resend(cb, f"{name}\n\nОберіть товар:", await products_kb(cid))
    await cb.answer()

@dp.callback_query(F.data.startswith("prod:"))
async def cb_product(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT name, weight, price, category_id, photo_url FROM products WHERE id=?", (pid,)
        )
        row = await cur.fetchone()
    if not row:
        return await cb.answer("Товар не знайдено")
    name, weight, price, cat_id, photo_url = row
    text = (
        f"📦 <b>{name}</b>\n"
        f"⚖️ Об'єм/вага: {weight}\n"
        f"💰 Ціна: <b>{price:.0f} грн</b>\n\n"
        f"💳 Оплата при отриманні"
    )
    kb = await product_detail_kb(pid, cat_id)
    if photo_url:
        try:
            await cb.message.delete()
            await bot.send_photo(
                chat_id=cb.message.chat.id,
                photo=photo_url,
                caption=text,
                reply_markup=kb
            )
        except Exception:
            await cb.message.edit_text(text, reply_markup=kb)
    else:
        await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# ══════════════════════════════════════════
#  КОШИК
# ══════════════════════════════════════════

async def render_cart_text(user_id: int) -> tuple[str, bool]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT p.name, p.weight, c.qty, p.price FROM cart c "
            "JOIN products p ON p.id=c.product_id WHERE c.user_id=?",
            (user_id,),
        )
        items = await cur.fetchall()
    if not items:
        return "🛒 Кошик порожній.\n\nДодайте товари з каталогу!", False
    total = sum(qty * price for _, _, qty, price in items)
    lines = "\n".join(
        f"• {n} ({w}) × {qty} = <b>{qty*p:.0f} грн</b>"
        for n, w, qty, p in items
    )
    return f"🛒 <b>Ваш кошик:</b>\n\n{lines}\n\n💰 Разом: <b>{total:.0f} грн</b>", True

@dp.message(F.text == "🛒 Кошик")
async def show_cart(msg: Message):
    text, _ = await render_cart_text(msg.from_user.id)
    await msg.answer(text, reply_markup=await cart_kb(msg.from_user.id))

async def refresh_cart(cb: CallbackQuery):
    text, _ = await render_cart_text(cb.from_user.id)
    await cb.message.edit_text(text, reply_markup=await cart_kb(cb.from_user.id))

@dp.callback_query(F.data.startswith("add:"))
async def cb_add(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    uid = cb.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, qty FROM cart WHERE user_id=? AND product_id=?", (uid, pid)
        )
        row = await cur.fetchone()
        if row:
            await db.execute("UPDATE cart SET qty=qty+1 WHERE id=?", (row[0],))
        else:
            await db.execute("INSERT INTO cart (user_id, product_id, qty) VALUES (?,?,1)", (uid, pid))
        await db.commit()
    await cb.answer("✅ Додано до кошика!")

@dp.callback_query(F.data.startswith("qinc:"))
async def cb_inc(cb: CallbackQuery):
    cid = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE cart SET qty=qty+1 WHERE id=? AND user_id=?", (cid, cb.from_user.id))
        await db.commit()
    await refresh_cart(cb)
    await cb.answer()

@dp.callback_query(F.data.startswith("qdec:"))
async def cb_dec(cb: CallbackQuery):
    cid = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT qty FROM cart WHERE id=? AND user_id=?", (cid, cb.from_user.id))
        row = await cur.fetchone()
        if row and row[0] > 1:
            await db.execute("UPDATE cart SET qty=qty-1 WHERE id=?", (cid,))
        else:
            await db.execute("DELETE FROM cart WHERE id=? AND user_id=?", (cid, cb.from_user.id))
        await db.commit()
    await refresh_cart(cb)
    await cb.answer()

@dp.callback_query(F.data.startswith("qdel:"))
async def cb_del(cb: CallbackQuery):
    cid = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE id=? AND user_id=?", (cid, cb.from_user.id))
        await db.commit()
    await refresh_cart(cb)
    await cb.answer("🗑 Видалено")

@dp.callback_query(F.data == "clear_cart")
async def cb_clear(cb: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id=?", (cb.from_user.id,))
        await db.commit()
    await refresh_cart(cb)
    await cb.answer("🗑 Кошик очищено")

@dp.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()

# ══════════════════════════════════════════
#  ОФОРМЛЕННЯ ЗАМОВЛЕННЯ
# ══════════════════════════════════════════

@dp.callback_query(F.data == "checkout")
async def cb_checkout(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer(
        "📝 <b>Оформлення замовлення</b>\n\nКрок 1/4\nВведіть ваше <b>ім'я та прізвище</b>:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(OrderFSM.full_name)
    await cb.answer()

@dp.message(OrderFSM.full_name)
async def fsm_name(msg: Message, state: FSMContext):
    await state.update_data(full_name=msg.text)
    await msg.answer(
        "Крок 2/4\nВведіть ваш <b>номер телефону</b>:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Поділитися номером", request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True,
        ),
    )
    await state.set_state(OrderFSM.phone)

@dp.message(OrderFSM.phone, F.contact)
async def fsm_phone_contact(msg: Message, state: FSMContext):
    await state.update_data(phone=msg.contact.phone_number)
    await _ask_address(msg, state)

@dp.message(OrderFSM.phone, F.text)
async def fsm_phone_text(msg: Message, state: FSMContext):
    await state.update_data(phone=msg.text)
    await _ask_address(msg, state)

async def _ask_address(msg: Message, state: FSMContext):
    await msg.answer(
        "Крок 3/4\nВведіть <b>адресу доставки</b>:\n"
        "<i>(місто, відділення Нової Пошти або адреса)</i>",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(OrderFSM.address)

@dp.message(OrderFSM.address)
async def fsm_address(msg: Message, state: FSMContext):
    await state.update_data(address=msg.text)
    await msg.answer(
        "Крок 4/4\nДодайте <b>коментар до замовлення</b> або натисніть «Пропустити»:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="➡️ Пропустити")]],
            resize_keyboard=True, one_time_keyboard=True,
        ),
    )
    await state.set_state(OrderFSM.comment)

@dp.message(OrderFSM.comment)
async def fsm_comment(msg: Message, state: FSMContext):
    comment = "" if msg.text == "➡️ Пропустити" else msg.text
    await state.update_data(comment=comment)
    data = await state.get_data()
    uid = msg.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT c.qty, p.name, p.weight, p.price FROM cart c "
            "JOIN products p ON p.id=c.product_id WHERE c.user_id=?",
            (uid,),
        )
        items = await cur.fetchall()
        total = sum(qty * price for qty, _, _, price in items)

        await db.execute(
            "INSERT INTO orders (user_id, full_name, phone, address, comment, total) "
            "VALUES (?,?,?,?,?,?)",
            (uid, data["full_name"], data["phone"], data["address"], data.get("comment",""), total),
        )
        cur2 = await db.execute("SELECT last_insert_rowid()")
        (order_id,) = await cur2.fetchone()

        for qty, name, weight, price in items:
            await db.execute(
                "INSERT INTO order_items (order_id, name, weight, price, qty) VALUES (?,?,?,?,?)",
                (order_id, name, weight, price, qty),
            )
        await db.execute("DELETE FROM cart WHERE user_id=?", (uid,))
        await db.commit()

    lines = "\n".join(f"• {n} ({w}) × {q} = {q*p:.0f} грн" for q, n, w, p in items)
    confirm_text = (
        f"✅ <b>Замовлення #{order_id} прийнято!</b>\n\n"
        f"👤 {data['full_name']}\n"
        f"📞 {data['phone']}\n"
        f"📍 {data['address']}\n"
        f"💬 {data.get('comment','—')}\n\n"
        f"<b>Товари:</b>\n{lines}\n\n"
        f"💰 Разом: <b>{total:.0f} грн</b>\n\n"
        f"💳 Оплата при отриманні\n"
        f"Ми зв'яжемося з вами для підтвердження!"
    )
    await msg.answer(confirm_text, reply_markup=main_menu())

    admin_text = (
        f"🔔 <b>Нове замовлення #{order_id}</b>\n\n"
        f"👤 {data['full_name']}\n"
        f"📞 {data['phone']}\n"
        f"📍 {data['address']}\n"
        f"💬 {data.get('comment','—')}\n\n"
        f"<b>Товари:</b>\n{lines}\n\n"
        f"💰 Сума: <b>{total:.0f} грн</b>\n"
        f"🆔 Telegram ID: <code>{uid}</code>"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"adm_ok:{order_id}:{uid}")],
                [InlineKeyboardButton(text="❌ Скасувати",   callback_data=f"adm_no:{order_id}:{uid}")],
            ])
        )
    except Exception:
        pass

    await state.clear()

# ══════════════════════════════════════════
#  АДМІН — зміна статусу замовлення
# ══════════════════════════════════════════

@dp.callback_query(F.data.startswith("adm_ok:"))
async def adm_confirm(cb: CallbackQuery):
    _, order_id, uid = cb.data.split(":")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status='підтверджено' WHERE id=?", (order_id,))
        await db.commit()
    await cb.message.edit_reply_markup()
    await cb.answer("✅ Замовлення підтверджено")
    try:
        await bot.send_message(int(uid),
            f"✅ Ваше замовлення <b>#{order_id}</b> підтверджено! "
            f"Очікуйте доставку 📦"
        )
    except Exception:
        pass

@dp.callback_query(F.data.startswith("adm_no:"))
async def adm_cancel(cb: CallbackQuery):
    _, order_id, uid = cb.data.split(":")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status='скасовано' WHERE id=?", (order_id,))
        await db.commit()
    await cb.message.edit_reply_markup()
    await cb.answer("❌ Замовлення скасовано")
    try:
        await bot.send_message(int(uid),
            f"❌ На жаль, замовлення <b>#{order_id}</b> було скасовано. "
            f"Зверніться до підтримки для уточнень."
        )
    except Exception:
        pass

# ══════════════════════════════════════════
#  МОЇ ЗАМОВЛЕННЯ
# ══════════════════════════════════════════

@dp.message(F.text == "📋 Мої замовлення")
async def my_orders(msg: Message):
    uid = msg.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, total, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (uid,),
        )
        rows = await cur.fetchall()
    if not rows:
        return await msg.answer("У вас ще немає замовлень.\n\nПерегляньте наш каталог! 🛍")
    lines = "\n".join(
        f"#{oid} | {total:.0f} грн | {status} | {created[:16]}"
        for oid, total, status, created in rows
    )
    await msg.answer(f"📋 <b>Ваші замовлення:</b>\n\n<code>{lines}</code>")

# ══════════════════════════════════════════
#  КВІЗ — ПІДБІР ТОВАРУ
# ══════════════════════════════════════════

GOAL_LABELS = {
    "mass":     "💪 Набір маси",
    "cut":      "🔥 Схуднення",
    "strength": "⚡ Сила та витривалість",
    "health":   "🌿 Загальне здоров'я",
}
GENDER_LABELS = {
    "m": "👨 Чоловік",
    "f": "👩 Жінка",
}
EXP_LABELS = {
    "beginner": "🟢 Початківець",
    "middle":   "🟡 Середній рівень",
    "advanced": "🔴 Просунутий",
}
BUDGET_LABELS = {
    "lo":  "💰 До 1000 грн",
    "mid": "💳 1000–2000 грн",
    "hi":  "💎 2000+ грн",
}

@dp.message(F.text == "🎯 Підібрати товар під мене")
async def quiz_start(msg: Message):
    await msg.answer(
        "🎯 <b>Підбір товару під ваші цілі</b>\n\n"
        "Дайте відповідь на 4 питання — і я підберу найкращі товари саме для вас!\n\n"
        "<b>Питання 1 з 4:</b> Яка ваша головна ціль?",
        reply_markup=quiz_goals_kb(),
    )

@dp.callback_query(F.data.startswith("qg:"))
async def cb_quiz_goal(cb: CallbackQuery):
    goal = cb.data.split(":")[1]
    label = GOAL_LABELS.get(goal, goal)
    await cb.message.edit_text(
        f"1️⃣ Ціль: <b>{label}</b>\n\n"
        "<b>Питання 2 з 4:</b> Ваша стать?",
        reply_markup=quiz_gender_kb(goal),
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("qs:"))
async def cb_quiz_gender(cb: CallbackQuery):
    _, goal, gender = cb.data.split(":")
    goal_label   = GOAL_LABELS.get(goal, goal)
    gender_label = GENDER_LABELS.get(gender, gender)
    await cb.message.edit_text(
        f"1️⃣ Ціль: <b>{goal_label}</b>\n"
        f"2️⃣ Стать: <b>{gender_label}</b>\n\n"
        "<b>Питання 3 з 4:</b> Який ваш рівень досвіду у спорті?",
        reply_markup=quiz_exp_kb(goal, gender),
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("qe:"))
async def cb_quiz_exp(cb: CallbackQuery):
    _, goal, gender, exp = cb.data.split(":")
    goal_label   = GOAL_LABELS.get(goal, goal)
    gender_label = GENDER_LABELS.get(gender, gender)
    exp_label    = EXP_LABELS.get(exp, exp)
    await cb.message.edit_text(
        f"1️⃣ Ціль: <b>{goal_label}</b>\n"
        f"2️⃣ Стать: <b>{gender_label}</b>\n"
        f"3️⃣ Рівень: <b>{exp_label}</b>\n\n"
        "<b>Питання 4 з 4:</b> Який ваш місячний бюджет на спортхарч?",
        reply_markup=quiz_budget_kb(goal, gender, exp),
    )
    await cb.answer()

async def _show_quiz_results(message, goal: str, gender: str, exp: str, budget: str):
    goal_label   = GOAL_LABELS.get(goal, goal)
    gender_label = GENDER_LABELS.get(gender, gender)
    exp_label    = EXP_LABELS.get(exp, exp)
    budget_label = BUDGET_LABELS.get(budget, budget)

    product_names = QUIZ_RECOMMENDATIONS.get((goal, gender, exp, budget), [])
    price_limit   = {"lo": 1000, "mid": 2000}.get(budget)

    async with aiosqlite.connect(DB_PATH) as db:
        found = []
        for pname in product_names:
            if price_limit:
                cur = await db.execute(
                    "SELECT id, name, weight, price FROM products "
                    "WHERE name LIKE ? AND price <= ? LIMIT 1",
                    (f"%{pname[:20]}%", price_limit),
                )
            else:
                cur = await db.execute(
                    "SELECT id, name, weight, price FROM products WHERE name LIKE ? LIMIT 1",
                    (f"%{pname[:20]}%",),
                )
            row = await cur.fetchone()
            if row:
                found.append(row)

    back_data = f"{goal}:{gender}:{exp}:{budget}"

    if not found:
        await message.edit_text(
            f"1️⃣ {goal_label}  2️⃣ {gender_label}  3️⃣ {exp_label}  4️⃣ {budget_label}\n\n"
            "На жаль, рекомендовані товари зараз не знайдені в каталозі. "
            "Зверніться до нашого менеджера @notsweat02 для персональної консультації!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Пройти знову", callback_data="quiz_restart")],
            ]),
        )
        return

    lines = []
    for pid, pname, weight, price in found:
        w = f" ({weight})" if weight else ""
        desc = PRODUCT_DESC.get(pname, "")
        desc_line = f"\n   <i>{desc}</i>" if desc else ""
        lines.append(f"• <b>{pname}</b>{w} — <b>{price:.0f} грн</b>{desc_line}")

    buttons = []
    for pid, pname, weight, price in found:
        short = pname[:28] + "…" if len(pname) > 28 else pname
        buttons.append([InlineKeyboardButton(text=f"👁 {short}", callback_data=f"qview:{pid}:{back_data}")])
    buttons.append([InlineKeyboardButton(text="🔄 Пройти знову", callback_data="quiz_restart")])
    buttons.append([InlineKeyboardButton(text="🛍 До каталогу",  callback_data="catalog")])

    text = (
        f"✅ <b>Результати підбору:</b>\n"
        f"1️⃣ {goal_label}  |  2️⃣ {gender_label}\n"
        f"3️⃣ {exp_label}  |  4️⃣ {budget_label}\n\n"
        f"Ось що ми рекомендуємо:\n\n"
        + "\n\n".join(lines) +
        "\n\n👇 Натисніть на товар щоб його оглянути:"
    )
    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("qb:"))
async def cb_quiz_budget(cb: CallbackQuery):
    _, goal, gender, exp, budget = cb.data.split(":")
    await _show_quiz_results(cb.message, goal, gender, exp, budget)
    await cb.answer()

@dp.callback_query(F.data == "quiz_restart")
async def cb_quiz_restart(cb: CallbackQuery):
    await cb.message.edit_text(
        "🎯 <b>Підбір товару під ваші цілі</b>\n\n"
        "<b>Питання 1 з 4:</b> Яка ваша головна ціль?",
        reply_markup=quiz_goals_kb(),
    )
    await cb.answer()

PRODUCT_DETAIL_DESC = {
    "Optimum Nutrition 100% Whey Gold Standard":
        "Один з найпопулярніших протеїнів у світі. Містить 24 г білка на порцію, мінімум жирів і вуглеводів. "
        "Ідеальний для прийому після тренування — швидко засвоюється та запускає ріст м'язів.\n"
        "📏 <b>Дозування:</b> 1 порція (30 г) у 180–240 мл води або молока одразу після тренування.",
    "Optimum Nutrition Creatine Powder":
        "Чистий креатин моногідрат без домішок. Збільшує силові показники, покращує вибухову потужність і прискорює відновлення між підходами.\n"
        "📏 <b>Дозування:</b> 5 г на день. У перші 5–7 днів (фаза завантаження) — 20 г на день, розділені на 4 прийоми.",
    "Optimum Nutrition Opti-Men":
        "Преміальний вітамінно-мінеральний комплекс для чоловіків. Містить 75+ активних інгредієнтів: вітаміни, мінерали, амінокислоти, екстракти рослин.\n"
        "📏 <b>Дозування:</b> 3 таблетки на день під час їжі.",
    "Optimum Nutrition Opti-Women":
        "Вітамінний комплекс розроблений спеціально для жінок. Підтримує гормональний баланс, здоров'я шкіри, нігтів та волосся.\n"
        "📏 <b>Дозування:</b> 2 таблетки на день під час їжі.",
    "Kevin Levrone Anabolic Mass":
        "Потужний гейнер для набору м'язової маси. Містить суміш швидких і повільних протеїнів, складні вуглеводи та креатин. Підходить тим, хто важко набирає вагу.\n"
        "📏 <b>Дозування:</b> 1–3 порції на день. Одна порція — 150 г порошку на 400–600 мл молока.",
    "BSN Syntha-6":
        "Багатокомпонентний протеїн із 6 видів білка. Дає тривале живлення м'язів і відмінний смак. Підходить між прийомами їжі та перед сном.\n"
        "📏 <b>Дозування:</b> 1–2 порції (47 г) на день у 300 мл молока або води.",
    "XTEND BCAA":
        "Класичний BCAA у пропорції 2:1:1 (лейцин:ізолейцин:валін) плюс глютамін і цитрулін малат. Захищає м'язи від руйнування та прискорює відновлення.\n"
        "📏 <b>Дозування:</b> 1 порція (14 г) під час або після тренування у 300 мл води.",
    "Mutant Mass":
        "Екстремальний гейнер для максимального набору маси. До 1060 ккал на порцію, 56 г білка, 192 г вуглеводів. Для тих, хто хоче суттєво збільшити вагу.\n"
        "📏 <b>Дозування:</b> 1–2 порції на день. Одна порція — 280 г на 600 мл молока.",
    "Dymatize ISO100":
        "Ізолят сироваткового протеїну — найчистіша форма білка. 25 г білка, майже нуль жирів і вуглеводів. Ідеальний при схудненні або для тих, хто рахує кожну калорію.\n"
        "📏 <b>Дозування:</b> 1 порція (32 г) після тренування у 250 мл води.",
    "C4 Original (Cellucor)":
        "Легендарний передтренувальний комплекс. Бета-аланін, аргінін, кофеїн і вітаміни групи B дають вибухову енергію та концентрацію на весь тренінг.\n"
        "📏 <b>Дозування:</b> 1 порція (6 г) у 150 мл води за 20–30 хв до тренування. Не приймати після 17:00.",
    "Animal Test":
        "Потужний натуральний тестобустер. Підвищує рівень тестостерону, збільшує силу та libido. Рекомендований для чоловіків від 21 року.\n"
        "📏 <b>Дозування:</b> 1 пак на день разом з їжею. Курс — 21 день, потім 7 днів перерва.",
    "L-Carnitine (BioTech)":
        "Транспортує жирові кислоти в мітохондрії, де вони спалюються як енергія. Найефективніший під час кардіотренувань.\n"
        "📏 <b>Дозування:</b> 1000–2000 мг за 30–40 хв до кардіотренування.",
    "Scitec 100% Whey":
        "Якісний протеїн на основі концентрату сироватки. 22 г білка на порцію, широкий вибір смаків. Відмінне співвідношення ціна/якість.\n"
        "📏 <b>Дозування:</b> 1–2 порції (30 г) на день — після тренування та між прийомами їжі.",
    "Nutrex Lipo-6":
        "Один з найвідоміших жироспалювачів. Рідкі капсули для швидкого засвоєння. Прискорює метаболізм, знижує апетит та підвищує термогенез.\n"
        "📏 <b>Дозування:</b> 2 капсули вранці та 1 капсула за 6 годин до сну. Не перевищувати 3 капсули на добу.",
    "Optimum Nutrition Amino Energy":
        "Амінокислоти + натуральний кофеїн в одному продукті. Дає м'яку енергію, підтримує відновлення та може замінити каву.\n"
        "📏 <b>Дозування:</b> 1–2 порції (9–18 г) у 300 мл води до або під час тренування.",
    "MST BCAA Powder":
        "BCAA у порошку з відмінною розчинністю та смаком. Антикатаболічний ефект та підтримка відновлення м'язів.\n"
        "📏 <b>Дозування:</b> 1 порція (10 г) під час або після тренування у 300 мл води.",
    "Animal Cuts":
        "Комплексний жироспалюючий стек від Universal Nutrition. Містить 8 груп активних інгредієнтів для спалювання жиру, підвищення енергії та виводу зайвої рідини.\n"
        "📏 <b>Дозування:</b> 1 пак двічі на день разом з їжею. Курс — 3 тижні, 1 тиждень перерва.",
    "MST Pump Killer":
        "Передтренувальний без кофеїну на основі аргініну, цитруліну та бета-аланіну. Дає потужний памп, витривалість без перезбудження.\n"
        "📏 <b>Дозування:</b> 1 порція (20 г) у 300 мл води за 30 хв до тренування.",
    "Rule 1 Whey Blend":
        "Суміш швидкого та середнього протеїнів (ізолят + концентрат). 25 г білка, мінімум цукру. Відмінний вибір для щоденного використання.\n"
        "📏 <b>Дозування:</b> 1 порція (32 г) після тренування у 250–300 мл води або молока.",
    "BSN NO-Xplode":
        "Класичний передтренувальний комплекс від BSN. Креатин, бета-аланін, кофеїн і NO-стимулятори дають силу, витривалість та памп.\n"
        "📏 <b>Дозування:</b> 1 порція (18 г) у 180 мл води за 30 хв до тренування.",
    "Kevin Levrone Gold Creatine":
        "Мікронізований креатин моногідрат від Kevin Levrone. Краще розчиняється та засвоюється. Збільшує силу та об'єм м'язів.\n"
        "📏 <b>Дозування:</b> 5 г на день у воді або соку. Фаза завантаження — 20 г на день перші 5 днів.",
    "Optimum Nutrition BCAA 1000":
        "BCAA у зручних капсулах (2:1:1). Не потребує приготування, зручно брати з собою. Захищає м'язи та допомагає відновленню.\n"
        "📏 <b>Дозування:</b> 2 капсули двічі на день — до та після тренування.",
    "Kevin Levrone Anabolic Crea10":
        "Унікальна формула з 10 формами креатину + транспортна система. Максимальне насичення м'язів без затримки води.\n"
        "📏 <b>Дозування:</b> 1 порція (15 г) за 30 хв до тренування у 250 мл соку.",
    "Kevin Levrone Gold Whey":
        "Преміальний протеїн від Kevin Levrone. 23 г білка, відмінний смак, повний амінокислотний профіль для відновлення і росту м'язів.\n"
        "📏 <b>Дозування:</b> 1–2 порції (30 г) на день у 250 мл молока або води.",
    "Omega-3 (NOW Foods)":
        "Риб'ячий жир високої якості. Підтримує здоров'я серцево-судинної системи, суглобів, мозку та знижує запалення в організмі.\n"
        "📏 <b>Дозування:</b> 1–2 капсули тричі на день під час їжі.",
    "Collagen (NOW Foods)":
        "Гідролізований колаген для здоров'я суглобів, зв'язок, шкіри та кісток. Особливо корисний при інтенсивних тренуваннях.\n"
        "📏 <b>Дозування:</b> 2 капсули двічі на день разом з вітаміном C для кращого засвоєння.",
    "Animal Pak":
        "Легендарний вітамінно-мінеральний комплекс для серйозних атлетів. Містить 60+ інгредієнтів: вітаміни, мінерали, амінокислоти, антиоксиданти.\n"
        "📏 <b>Дозування:</b> 1–2 паки на день разом з їжею. Запивати великою кількістю води.",
    "Optimum Nutrition Glutamine":
        "Глютамін у чистому вигляді. Прискорює відновлення, підтримує імунну систему та здоров'я кишківника після інтенсивних навантажень.\n"
        "📏 <b>Дозування:</b> 5 г після тренування та 5 г перед сном у воді або соку.",
    "ZMA (Optimum Nutrition)":
        "Класична формула цинку, магнію та вітаміну B6. Покращує якість сну, підтримує відновлення і природний рівень тестостерону.\n"
        "📏 <b>Дозування:</b> 3 капсули для чоловіків або 2 для жінок за 30–60 хв до сну на порожній шлунок.",
    "Ашваганда (KSM-66)":
        "Преміальний екстракт ашваганди (8% вітанолідів). Знижує рівень кортизолу, покращує стресостійкість, підвищує силу та libido.\n"
        "📏 <b>Дозування:</b> 1 капсула (300–600 мг) на день разом з їжею. Курс — 2–3 місяці.",
}

@dp.callback_query(F.data.startswith("qview:"))
async def cb_quiz_view(cb: CallbackQuery):
    parts = cb.data.split(":")
    pid   = int(parts[1])
    back_data = ":".join(parts[2:])

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT name, weight, price, photo_url FROM products WHERE id=?", (pid,)
        )
        row = await cur.fetchone()
    if not row:
        return await cb.answer("Товар не знайдено")

    name, weight, price, photo_url = row
    w = f"{weight}" if weight else "—"
    short_desc = PRODUCT_DESC.get(name, "")
    detail_desc = PRODUCT_DETAIL_DESC.get(name, "")

    text = (
        f"📦 <b>{name}</b>\n"
        f"⚖️ Об'єм/вага: <b>{w}</b>\n"
        f"💰 Ціна: <b>{price:.0f} грн</b>\n\n"
        + (f"<i>{short_desc}</i>\n\n" if short_desc else "")
        + (detail_desc + "\n\n" if detail_desc else "")
        + "💳 Оплата при отриманні"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Додати до кошика", callback_data=f"add:{pid}")],
        [InlineKeyboardButton(text="⬅️ До результатів",  callback_data=f"qback:{back_data}")],
    ])

    if photo_url:
        try:
            await cb.message.delete()
            await bot.send_photo(
                chat_id=cb.message.chat.id,
                photo=photo_url,
                caption=text,
                reply_markup=kb,
            )
        except Exception:
            await cb.message.edit_text(text, reply_markup=kb)
    else:
        await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data.startswith("qback:"))
async def cb_quiz_back(cb: CallbackQuery):
    parts = cb.data.split(":")
    goal, gender, exp, budget = parts[1], parts[2], parts[3], parts[4]
    if cb.message.photo:
        await cb.message.delete()
        msg = await bot.send_message(cb.message.chat.id, "⏳")
        await _show_quiz_results(msg, goal, gender, exp, budget)
    else:
        await _show_quiz_results(cb.message, goal, gender, exp, budget)
    await cb.answer()

# ══════════════════════════════════════════
#  ПІДТРИМКА
# ══════════════════════════════════════════

@dp.message(F.text == "💬 Менеджер для консультацій")
async def support(msg: Message):
    await msg.answer(
        "💬 <b>Менеджер для консультацій</b>\n\n"
        "З будь-яких питань щодо товарів, замовлень та доставки звертайтеся до нашого менеджера:\n\n"
        "👉 @notsweat02\n\n"
        "Відповідаємо з 9:00 до 21:00 щодня."
    )

# ══════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════

async def auto_sync_loop():
    while True:
        await asyncio.sleep(SYNC_EVERY)
        try:
            await sync_catalog_to_db()
            logging.info("Автосинхронізація каталогу завершена")
        except Exception as e:
            logging.error(f"Помилка автосинхронізації: {e}")

async def health_check_server():
    from aiohttp import web
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Health check server started on port {port}")

async def main():
    await init_db()
    asyncio.create_task(auto_sync_loop())
    asyncio.create_task(health_check_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
