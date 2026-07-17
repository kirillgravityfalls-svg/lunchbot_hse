import asyncio
import os
import sqlite3
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

DB_NAME = "lunchbot.db"

# ========== ВЕБ-СЕРВЕР ==========
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running", 200

@app.route('/health')
def health_check():
    return "OK", 200

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Кнопки
campus_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Покровка")],
        [KeyboardButton(text="Солянка")],
        [KeyboardButton(text="Колобовский")],
        [KeyboardButton(text="Лялин пер.")],
        [KeyboardButton(text="Трифоновская")],
        [KeyboardButton(text="Потаповский")]
    ],
    resize_keyboard=True
)

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍽 Что поесть?")],
        [KeyboardButton(text="📍 Сменить корпус")],
        [KeyboardButton(text="ℹ️ О боте")]
    ],
    resize_keyboard=True
)

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🍽 Привет! Я помогу тебе найти место для перекуса.\n\n"
        "Выбери свой корпус:",
        reply_markup=campus_kb
    )

@dp.message(lambda msg: msg.text in ["Покровка", "Солянка", "Колобовский", "Лялин пер.", "Трифоновская", "Потаповский"])
async def set_campus(message: types.Message):
    campus = message.text
    user_id = message.from_user.id
    
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO users (user_id, campus) VALUES (?, ?)",
        (user_id, campus)
    )
    conn.commit()
    conn.close()
    
    await message.answer(
        f"✅ Корпус выбран: {campus}\n\n"
        "Теперь нажми «🍽 Что поесть?»",
        reply_markup=main_kb
    )

@dp.message(lambda msg: msg.text == "🍽 Что поесть?")
async def get_food(message: types.Message):
    user_id = message.from_user.id
    
    conn = get_db()
    user = conn.execute("SELECT campus FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if not user:
        await message.answer("⚠️ Сначала выбери корпус через /start")
        conn.close()
        return
    
    campus = user["campus"]
    
    places = conn.execute(
        "SELECT name, address, walk_time, rating, category, avg_bill "
        "FROM places WHERE campus = ? AND is_active = 1 "
        "ORDER BY rating DESC LIMIT 5",
        (campus,)
    ).fetchall()
    conn.close()
    
    if not places:
        await message.answer("😕 Рядом с этим корпусом пока нет точек.")
        return
    
    answer = f"🍽 Лучшие места рядом с {campus}:\n\n"
    for place in places:
        answer += (
            f"🏪 {place['name']}\n"
            f"⭐ {place['rating']} | {place['category']} | {place['walk_time']} мин\n"
            f"💳 ~{place['avg_bill']} ₽\n"
            f"📍 {place['address']}\n\n"
        )
    
    await message.answer(answer)

@dp.message(lambda msg: msg.text == "📍 Сменить корпус")
async def change_campus(message: types.Message):
    await message.answer("Выбери свой корпус:", reply_markup=campus_kb)

@dp.message(lambda msg: msg.text == "ℹ️ О боте")
async def about(message: types.Message):
    await message.answer(
        "🍽 LunchBot для Лицея ВШЭ\n\n"
        "📌 Помогает найти место для перекуса\n"
        "🚫 Не показывает столовые\n"
        "📍 6 корпусов Лицея\n\n"
        "Версия 1.0"
    )

@dp.message()
async def unknown(message: types.Message):
    await message.answer("Используй кнопки меню 👇")

# ========== ЗАПУСК ==========
async def run_bot():
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    # Запускаем бота в основном потоке (главное изменение!)
    asyncio.run(run_bot())