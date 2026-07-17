import asyncio
import os
import sqlite3
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")  # токен из переменных Render
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

DB_NAME = "lunchbot.db"

# ========== ВЕБ-СЕРВЕР ДЛЯ RENDER ==========
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

# Кнопки для выбора корпуса
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
        "🍽 Привет! Я помогу тебе найти место для перекуса рядом с твоим корпусом.\n\n"
        "Я показываю только кофейни, пекарни, магазины и киоски.\n"
        "Без столовых!\n\n"
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
        "Теперь нажми «🍽 Что поесть?», чтобы посмотреть варианты.",
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
        await message.answer("😕 Рядом с этим корпусом пока нет точек в базе.\nПопробуй позже.")
        return
    
    answer = f"🍽 Лучшие места рядом с {campus}:\n\n"
    for place in places:
        answer += (
            f"🏪 {place['name']}\n"
            f"⭐ {place['rating']} | {place['category']} | {place['walk_time']} мин пешком\n"
            f"💳 ~{place['avg_bill']} ₽\n"
            f"📍 {place['address']}\n\n"
        )
    
    await message.answer(answer)

@dp.message(lambda msg: msg.text == "📍 Сменить корпус")
async def change_campus(message: types.Message):
    await message.answer(
        "Выбери свой корпус:",
        reply_markup=campus_kb
    )

@dp.message(lambda msg: msg.text == "ℹ️ О боте")
async def about(message: types.Message):
    await message.answer(
        "🍽 LunchBot для Лицея ВШЭ\n\n"
        "📌 Помогает быстро найти место для перекуса\n"
        "🚫 Не показывает столовые и буфеты\n"
        "📍 Работает для 6 корпусов Лицея:\n"
        "   • Покровка\n"
        "   • Солянка\n"
        "   • Колобовский\n"
        "   • Лялин пер.\n"
        "   • Трифоновская\n"
        "   • Потаповский\n\n"
        "Версия 1.0"
    )

@dp.message()
async def unknown(message: types.Message):
    await message.answer(
        "Я не понимаю эту команду.\n"
        "Используй кнопки меню 👇"
    )

async def run_bot():
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

# ========== ЗАПУСК В ПОТОКЕ ==========
def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot())

# ========== ГЛАВНЫЙ ЗАПУСК ==========
if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    bot_thread = Thread(target=start_bot_thread)
    bot_thread.start()
    
    # Запускаем Flask для Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)