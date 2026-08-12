import asyncio
import os
import glob
import logging
from typing import Dict, Any, Optional
import yt_dlp

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def _download_with_ytdlp(url: str) -> Dict[str, Any]:
    """
    Синхронная функция скачивания медиафайла через yt-dlp.
    Исполняется в отдельном потоке через asyncio.to_thread.
    """
    output_template = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")
    
    ydl_opts = {
        # Формат: видео + аудио размером до 48MB (лимит Telegram Bot API 50MB)
        'format': 'bestvideo[filesize<=48M][ext=mp4]+bestaudio[ext=m4a]/best[filesize<=48M][ext=mp4]/best[filesize<=48M]/best/b',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        # Обход защиты YouTube / TikTok от ботов
        'extractor_args': {
            'youtube': {
                'player_client': ['mweb', 'android', 'ios'],
                'skip': ['webpage', 'configs']
            }
        },
        'impersonate': 'chrome',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        logger.warning(f"Первичная попытка не удалась, пробуем резервный клиент: {e}")
        # Резервный вариант настройки без строгих ограничений по формату
        fallback_opts = {
            'format': 'best[filesize<=48M]/best',
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            }
        }
        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
            info = ydl.extract_info(url, download=True)

    if info is None:
        raise ValueError("Не удалось получить информацию о видео.")
    
    # Определение итогового пути к файлу
    filename = ydl.prepare_filename(info)
    
    # Если формат был сконвертирован в mp4
    base, _ = os.path.splitext(filename)
    mp4_filename = base + ".mp4"
    
    if os.path.exists(mp4_filename):
        final_path = mp4_filename
    elif os.path.exists(filename):
        final_path = filename
    else:
        # Ищем любой файл с таким ID в папке
        matching_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{info.get('id', '')}.*"))
        if matching_files:
            final_path = matching_files[0]
        else:
            raise FileNotFoundError("Скачанный файл не найден на диске.")
    
    return {
        "filepath": final_path,
        "title": info.get("title", "Видео"),
        "duration": info.get("duration"),
        "width": info.get("width"),
        "height": info.get("height"),
        "uploader": info.get("uploader") or info.get("uploader_id"),
    }

async def download_video(url: str) -> Dict[str, Any]:
    """
    Асинхронная обертка над скачиванием видео.
    """
    return await asyncio.to_thread(_download_with_ytdlp, url)

def remove_file(filepath: Optional[str]):
    """
    Удаление файла после отправки пользователю.
    """
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
            logger.info(f"Удален временный файл: {filepath}")
        except Exception as e:
            logger.error(f"Ошибка при удалении файла {filepath}: {e}")
