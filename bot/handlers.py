import re
import os
import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import FSInputFile, Message, InputMediaPhoto

from bot.downloader import download_video, remove_file

logger = logging.getLogger(__name__)

router = Router()

import html

# Универсальный регулярный поиск медиассылок Instagram и TikTok
URL_EXTRACT_REGEX = re.compile(
    r"(https?://[^\s]+|(?:[a-zA-Z0-9-]+\.)*(?:instagram\.com|instagr\.am|tiktok\.com|douyin\.com)/[^\s]+)",
    re.IGNORECASE
)

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 МБ — лимит Telegram Bot API

@router.message(CommandStart())
async def cmd_start(message: Message):
    welcome_text = (
        "👋 <b>Привет! Я бот для скачивания видео и фото.</b>\n\n"
        "Отправь мне ссылку из:\n"
        "• 📷 <b>Instagram</b> (Reels, посты)\n"
        "• 🎵 <b>TikTok</b> (видео без знаков и слайдшоу из фото)\n\n"
        "Просто отправь ссылку в чат, и я пришлю готовый медиафайл!"
    )
    await message.answer(welcome_text, parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "ℹ️ <b>Инструкция по использованию:</b>\n\n"
        "1. Скопируйте ссылку на видео из Instagram или TikTok.\n"
        "2. Вставьте её в чат и нажмите отправить.\n"
        "3. Бот обработает ссылку и пришлет готовый файл!\n\n"
        "⚠️ <i>Ограничение</i>: Telegram Bot API позволяет отправлять файлы до 50 МБ."
    )
    await message.answer(help_text, parse_mode="HTML")

@router.message(F.text)
async def handle_text_messages(message: Message):
    text = message.text.strip()
    
    match = URL_EXTRACT_REGEX.search(text)
    if not match:
        await message.answer(
            "🤔 Я понимаю только ссылки на <b>Instagram</b> или <b>TikTok</b>.\n"
            "Отправьте мне ссылку на видео!",
            parse_mode="HTML"
        )
        return

    url = match.group(0)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    status_msg = await message.answer("⏳ <b>Скачиваю медиа...</b> Пожалуйста, подождите.", parse_mode="HTML")
    
    target_files_to_clean = None
    try:
        data = await download_video(url)
        res_type = data.get("type", "video")
        
        # 1. ОБРАБОТКА ФОТО-СЛАЙДШОУ (TikTok Photo Carousel)
        if res_type == "photos":
            photo_paths = data.get("filepaths", [])
            target_files_to_clean = photo_paths
            
            if not photo_paths:
                raise ValueError("Не удалось загрузить фотографии из слайдшоу.")
                
            await status_msg.edit_text(f"📤 <b>Отправляю слайдшоу из {len(photo_paths)} фото...</b>", parse_mode="HTML")
            
            # Формируем MediaGroup для отправки альбома в Telegram (максимум 10 элементов в одной группе)
            media_group = []
            title = html.escape(str(data.get('title', 'Слайдшоу TikTok')))
            uploader = html.escape(str(data['uploader'])) if data.get("uploader") else None
            caption = f"🖼 <b>{title}</b>"
            if uploader:
                caption += f"\n👤 <i>Автор:</i> {uploader}"
                
            for idx, p_path in enumerate(photo_paths[:10]):
                photo_file = FSInputFile(p_path)
                if idx == 0:
                    media_group.append(InputMediaPhoto(media=photo_file, caption=caption[:1024], parse_mode="HTML"))
                else:
                    media_group.append(InputMediaPhoto(media=photo_file))
                    
            await message.answer_media_group(media=media_group)
            await status_msg.delete()
            return

        # 2. ОБРАБОТКА ОБЫЧНОГО ВИДЕО
        filepath = data.get("filepath")
        target_files_to_clean = filepath
        
        if not filepath or not os.path.exists(filepath):
            raise FileNotFoundError("Скачанный видеофайл отсутствует.")
            
        file_size = os.path.getsize(filepath)
        if file_size > MAX_FILE_SIZE_BYTES:
            size_mb = round(file_size / (1024 * 1024), 1)
            await status_msg.edit_text(
                f"⚠️ <b>Размер видео превышает 50 МБ ({size_mb} МБ).</b>\n\n"
                "Telegram Bot API запрещает отправку файлов крупнее 50 МБ через бота.",
                parse_mode="HTML"
            )
            return

        await status_msg.edit_text("📤 <b>Загружаю видео в Telegram...</b>", parse_mode="HTML")
        
        video_file = FSInputFile(filepath)
        title = html.escape(str(data.get('title', 'Видео')))
        uploader = html.escape(str(data['uploader'])) if data.get("uploader") else None
        caption = f"🎬 <b>{title}</b>"
        if uploader:
            caption += f"\n👤 <i>Автор:</i> {uploader}"
            
        # Безопасно приводим параметры к int для валидации Pydantic v2 в aiogram 3
        width = int(float(data["width"])) if data.get("width") is not None else None
        height = int(float(data["height"])) if data.get("height") is not None else None
        duration = int(float(data["duration"])) if data.get("duration") is not None else None

        await message.answer_video(
            video=video_file,
            caption=caption[:1024],
            parse_mode="HTML",
            width=width,
            height=height,
            duration=duration
        )
        
        await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Ошибка при скачивании {url}: {e}")
        error_text = (
            "❌ **Не удалось скачать видео.**\n\n"
            "Возможные причины:\n"
            "• Видео является приватным или было удалено.\n"
            "• Размер видео превышает 50 МБ.\n"
            "• Неподдерживаемая ссылка.\n\n"
            f"🛠 **Детали ошибки (для разработчика):**\n`{str(e)}`"
        )
        try:
            await status_msg.edit_text(error_text, parse_mode="Markdown")
        except Exception:
            await message.answer(error_text, parse_mode="Markdown")
    finally:
        if target_files_to_clean:
            remove_file(target_files_to_clean)
