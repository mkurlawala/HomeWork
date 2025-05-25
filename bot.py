import logging
import openai
import asyncio
import easyocr
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.utils import executor
from datetime import datetime, timedelta

# === LOAD ENV VARIABLES ===
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
reader = easyocr.Reader(['en'])

# === IN-MEMORY USER TRACKER ===
user_usage = {}
FREE_LIMIT = 5
premium_users = set()

# === AI RESPONSE FUNCTION ===
async def ask_openai(question: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": question}]
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return f"Error: {e}"

# === UPGRADE BUTTON ===
def get_upgrade_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("\ud83d\udc8e Upgrade Now", url="https://ko-fi.com/homeworkhelperAI"))
    return markup

# === HELP / START ===
@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: Message):
    await message.reply(
        "\ud83d\udc4b Welcome to QuickHelp AI!\nJust send your homework question as text or photo.\n\n\ud83d\udca1 You can ask up to 5 free questions daily.",
        reply_markup=get_upgrade_markup()
    )

# === UPGRADE HANDLER ===
@dp.message_handler(commands=['upgrade'])
async def send_upgrade_qr(message: Message):
    await message.reply("\ud83d\udcb0 You can upgrade via Ko-fi for unlimited access:")
    await message.reply("\ud83d\udd17 https://ko-fi.com/homeworkhelperAI")
    qr = InputFile("upi_qr.png")
    await bot.send_photo(chat_id=message.chat.id, photo=qr)

@dp.callback_query_handler(lambda c: c.data == 'upgrade')
async def process_upgrade_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "\ud83d\udcb0 You can upgrade via Ko-fi for unlimited access:")
    await bot.send_message(callback_query.from_user.id, "\ud83d\udd17 https://ko-fi.com/homeworkhelperAI")
    qr = InputFile("upi_qr.png")
    await bot.send_photo(chat_id=callback_query.from_user.id, photo=qr)

# === TEXT HANDLER ===
@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle_question(message: Message):
    user_id = message.from_user.id
    now = datetime.utcnow().date()

    if user_id not in premium_users:
        if user_id not in user_usage:
            user_usage[user_id] = {"date": now, "count": 0}

        if user_usage[user_id]["date"] != now:
            user_usage[user_id] = {"date": now, "count": 0}

        if user_usage[user_id]["count"] >= FREE_LIMIT:
            await message.reply("\u26a0\ufe0f You’ve used your 5 free questions for today.")
            await send_upgrade_qr(message)
            return

    await message.reply("\ud83d\udd0d Thinking...")
    answer = await ask_openai(message.text)
    await message.reply(answer)
    if user_id not in premium_users:
        user_usage[user_id]["count"] += 1

# === PAYMENT SCREENSHOT HANDLER ===
@dp.message_handler(lambda message: message.caption and 'paid' in message.caption.lower(), content_types=types.ContentType.PHOTO)
async def handle_payment_proof(message: Message):
    user_id = message.from_user.id
    premium_users.add(user_id)
    await message.reply("\u2705 Payment received! You’ve been upgraded to unlimited access. Thank you!")

# === PHOTO HANDLER ===
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    now = datetime.utcnow().date()

    if user_id not in premium_users:
        if user_id not in user_usage:
            user_usage[user_id] = {"date": now, "count": 0}

        if user_usage[user_id]["date"] != now:
            user_usage[user_id] = {"date": now, "count": 0}

        if user_usage[user_id]["count"] >= FREE_LIMIT:
            await message.reply("\u26a0\ufe0f You’ve used your 5 free questions for today.")
            await send_upgrade_qr(message)
            return

    await message.reply("\ud83d\udcf7 Received image. Processing...")
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_path = file.file_path
    downloaded_file = await bot.download_file(file_path)

    with open("temp.jpg", "wb") as f:
        f.write(downloaded_file.read())

    try:
        result = reader.readtext("temp.jpg", detail=0)
        extracted_text = " ".join(result)
        await message.reply(f"\ud83d\udcdd Extracted text:\n{extracted_text[:500]}...")
        answer = await ask_openai(extracted_text)
        await message.reply(answer)
        if user_id not in premium_users:
            user_usage[user_id]["count"] += 1
    except Exception as e:
        await message.reply(f"❌ OCR failed: {e}")

    os.remove("temp.jpg")

# === RUN ===
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
