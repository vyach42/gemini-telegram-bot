
# telegram_gemini_bot.py
import asyncio
import httpx
import os
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Загружаем переменные окружения из .env файла
load_dotenv()

# --- Конфигурация ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Память для каждого пользователя (временно, в оперативной памяти)
user_histories = {}
MAX_HISTORY_LENGTH = 10

GEMINI_API_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def get_gemini_response(history: list) -> str:
    if not GEMINI_API_KEY:
        logger.error("Ключ Gemini API не настроен в .env файле.")
        return "Ошибка конфигурации: Ключ Gemini API не найден."

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": msg} for msg in history]
        }]
    }

    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            response = await client.post(GEMINI_API_ENDPOINT, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            if "candidates" in data and data["candidates"] and                "content" in data["candidates"][0] and                "parts" in data["candidates"][0]["content"] and                data["candidates"][0]["content"]["parts"]:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            elif "error" in data:
                logger.error(f"Gemini API Error: {data['error']}")
                return f"Ошибка от Gemini API: {data['error'].get('message', 'Неизвестная ошибка')}"
            else:
                logger.error(f"Неожиданная структура ответа от Gemini: {data}")
                return "Не удалось извлечь осмысленный ответ от Gemini."

    except httpx.HTTPStatusError as e:
        logger.error(f"Ошибка статуса HTTP при запросе к Gemini: {e.response.status_code} - {e.response.text}")
        return f"Ошибка API ({e.response.status_code}). Попробуйте позже или проверьте консоль для деталей."
    except httpx.RequestError as e:
        logger.error(f"Ошибка HTTP запроса к Gemini: {e}")
        return "Ошибка сети при обращении к Gemini. Попробуйте позже."
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при вызове Gemini: {e}", exc_info=True)
        return "Произошла внутренняя ошибка. Проверьте логи."

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name
    await update.message.reply_text(f"Привет, {user_name}! Я твой бот с Gemini AI. Просто отправь мне сообщение.")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    if not user_message:
        return

    chat_id = str(update.effective_chat.id)
    user_name = update.effective_user.first_name
    logger.info(f"Получено сообщение от {user_name} (ID: {chat_id}): '{user_message}'")

    thinking_message = await update.message.reply_text("🤖 Думаю над вашим запросом...")

    if chat_id not in user_histories:
        user_histories[chat_id] = []

    user_histories[chat_id].append(user_message)
    user_histories[chat_id] = user_histories[chat_id][-MAX_HISTORY_LENGTH:]

    gemini_reply = await get_gemini_response(user_histories[chat_id])

    user_histories[chat_id].append(gemini_reply)
    user_histories[chat_id] = user_histories[chat_id][-MAX_HISTORY_LENGTH:]

    if thinking_message:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=thinking_message.message_id,
            text=gemini_reply,
        parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(gemini_reply)

def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Токен Telegram бота не найден! Проверьте файл .env.")
        return
    if not GEMINI_API_KEY:
        logger.warning("ПРЕДУПРЕЖДЕНИЕ: Ключ Gemini API не найден! Ответы от Gemini не будут работать. Проверьте файл .env.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    logger.info("Бот запускается... Нажмите Ctrl+C для остановки.")
    application.run_polling()

if __name__ == "__main__":
    main()
