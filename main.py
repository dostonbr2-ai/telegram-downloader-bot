import os
import asyncio
import logging
import sys
import base64
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

from bot.config import BOT_TOKEN
from bot.handlers import router

async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    """
    Запуск минимального HTTP веб-сервера для удовлетворения Health Check на Render.
    """
    port = int(os.getenv("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Health check web-server запущен на порту {port}")

def init_cookies():
    """
    Проверка и декодирование cookies.txt из переменной окружения YOUTUBE_COOKIES_BASE64.
    """
    cookies_b64 = os.getenv("YOUTUBE_COOKIES_BASE64")
    if cookies_b64 and not os.path.exists("cookies.txt"):
        try:
            with open("cookies.txt", "wb") as f:
                f.write(base64.b64decode(cookies_b64))
            logging.info("Успешно создан cookies.txt из переменной YOUTUBE_COOKIES_BASE64")
        except Exception as e:
            logging.error(f"Ошибка декодирования куки из переменной окружения: {e}")

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Запуск Telegram-бота...")

    # Инициализация куки
    init_cookies()

    # Запускаем порт для Render
    await start_web_server()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        from aiogram.exceptions import TelegramConflictError
        import asyncio
        
        # Retry logic for Render zero-downtime deploys
        for attempt in range(5):
            try:
                await dp.start_polling(bot)
                break
            except TelegramConflictError:
                logging.warning(f"Конфликт Telegram API (попытка {attempt + 1}/5). Ждем 5 секунд...")
                await asyncio.sleep(5)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
