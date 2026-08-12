import re
import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import FSInputFile, Message

from bot.downloader import download_video, remove_file

logger = logging.getLogger(__name__)

router = Router()

# Регулярное выражение для поиска ссылок на YouTube, TikTok, Instagram
URL_REGEX = r"https?://(?:www\.)?(?:instagram\.com|instagr\.am|tiktok\.com|youtube\.com|youtu\.be)/[^\s]+"

@router.message(CommandStart())
async def cmd_start(message: Message):
    welcome_text = (
        "👋 **Привет! Я бот для скачивания видео.**\n\n"
        "Отправь мне ссылку на видео из:\n"
        "• 📷 **Instagram** (Reels, посты)\n"
        "• 🎵 **TikTok** (без водяных знаков)\n"
        "• 🔴 **YouTube** (Shorts и обычные видео)\n\n"
        "Просто отправь ссылку в чат, и я пришлю тебе готовый файл!"
    )
    await message.answer(welcome_text, parse_mode="Markdown")

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "ℹ️ **Как пользоваться ботом:**\n\n"
        "1. Скопируй ссылку на видео из Instagram, TikTok или YouTube.\n"
        "2. Вставь и отправь её мне в сообщение.\n"
        "3. Подожди несколько секунд — я скачаю видео и пришлю его тебе!\n\n"
        "⚠️ *Обратите внимание*: Telegram разрешает отправку видеофайлов размером до 50 МБ."
    )
    await message.answer(help_text, parse_mode="Markdown")

@router.message(F.text.regexp(URL_REGEX))
async def handle_url(message: Message):
    # Поиск ссылки в сообщении
    match = re.search(URL_REGEX, message.text)
    if not match:
        return
    
    url = match.group(0)
    status_msg = await message.answer("⏳ **Скачиваю видео...** Пожалуйста, подождите.", parse_mode="Markdown")
    
    filepath = None
    try:
        data = await download_video(url)
        filepath = data["filepath"]
        
        await status_msg.edit_text("📤 **Загружаю видео в Telegram...**", parse_mode="Markdown")
        
        video_file = FSInputFile(filepath)
        caption = f"🎬 **{data.get('title', 'Видео')}**"
        if data.get("uploader"):
            caption += f"\n👤 *Автор:* {data['uploader']}"
            
        await message.answer_video(
            video=video_file,
            caption=caption[:1024],  # Ограничение Telegram на длину подписи
            parse_mode="Markdown",
            width=data.get("width"),
            height=data.get("height"),
            duration=data.get("duration")
        )
        
        # Удаляем статусное сообщение после успешной отправки
        await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Ошибка при скачивании {url}: {e}")
        error_text = (
            "❌ **Не удалось скачать видео.**\n\n"
            "Возможные причины:\n"
            "• Видео является приватным или было удалено.\n"
            "• Размер видео превышает 50 МБ.\n"
            "• Неподдерживаемая ссылка."
        )
        await status_msg.edit_text(error_text, parse_mode="Markdown")
    finally:
        if filepath:
            remove_file(filepath)

@router.message(F.text)
async def handle_other_text(message: Message):
    await message.answer(
        "🤔 Я понимаю только ссылки на **Instagram**, **TikTok** или **YouTube**.\n"
        "Отправьте мне ссылку на видео!",
        parse_mode="Markdown"
    )
