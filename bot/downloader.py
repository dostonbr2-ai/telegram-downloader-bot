import asyncio
import os
import glob
import logging
from typing import Dict, Any, Optional
import yt_dlp
from pytubefix import YouTube

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def _is_youtube_url(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url

def _download_youtube(url: str) -> Dict[str, Any]:
    """
    Скачивание с YouTube с использованием pytubefix (обходит блокировки 429).
    """
    logger.info(f"Загрузка с YouTube через pytubefix: {url}")
    yt = YouTube(url, client='WEB')
    
    # Сначала пытаемся получить комбинированный поток mp4 с видео и звуком
    stream = yt.streams.filter(progressive=True, file_extension='mp4').get_highest_resolution()
    if not stream:
        # Резервный вариант — наилучший любой доступный поток
        stream = yt.streams.get_highest_resolution()
        
    filepath = stream.download(output_path=DOWNLOAD_DIR)
    
    return {
        "filepath": filepath,
        "title": yt.title or "YouTube Video",
        "duration": yt.length,
        "width": None,
        "height": None,
        "uploader": yt.author,
    }

def _download_ytdlp(url: str) -> Dict[str, Any]:
    """
    Скачивание с Instagram / TikTok через yt-dlp.
    """
    output_template = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")
    
    ydl_opts = {
        'format': 'bestvideo[filesize<=48M][ext=mp4]+bestaudio[ext=m4a]/best[filesize<=48M][ext=mp4]/best[filesize<=48M]/best/b',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'impersonate': 'chrome',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if info is None:
        raise ValueError("Не удалось получить информацию о видео.")
    
    filename = ydl.prepare_filename(info)
    base, _ = os.path.splitext(filename)
    mp4_filename = base + ".mp4"
    
    if os.path.exists(mp4_filename):
        final_path = mp4_filename
    elif os.path.exists(filename):
        final_path = filename
    else:
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

def _download_with_ytdlp(url: str) -> Dict[str, Any]:
    if _is_youtube_url(url):
        try:
            return _download_youtube(url)
        except Exception as e:
            logger.warning(f"pytubefix ошибка: {e}, пробование резервного yt-dlp")
            return _download_ytdlp(url)
    else:
        return _download_ytdlp(url)

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
