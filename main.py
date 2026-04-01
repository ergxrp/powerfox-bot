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

# ══════════════════════════════════════════
#  КЛАВІАТУРИ
# ══════════════════════════════════════════

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Каталог"),       KeyboardButton(text="🛒 Кошик")],
            [KeyboardButton(text="📋 Мої замовлення"), KeyboardButton(text="📞 Підтримка")],
        ],
        resize_keyboard=True,
    )

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
#  ПІДТРИМКА
# ══════════════════════════════════════════

@dp.message(F.text == "📞 Підтримка")
async def support(msg: Message):
    await msg.answer(
        "📞 <b>Підтримка</b>\n\n"
        "З будь-яких питань звертайтеся:\n"
        "👉 @your_support_username\n\n"
        "Ми відповідаємо з 9:00 до 21:00 щодня."
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
