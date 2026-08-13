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
COOKIES_PATH = os.path.join(os.getcwd(), "cookies.txt")

def _is_youtube_url(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url

def _download_ytdlp(url: str, use_cookies: bool = True) -> Dict[str, Any]:
    output_template = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")
    
    ydl_opts = {
        'format': 'bestvideo[filesize<=48M][ext=mp4]+bestaudio[ext=m4a]/best[filesize<=48M][ext=mp4]/best[filesize<=48M]/best/b',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'extractor_args': {'youtube': ['player_skip=web,tv,mweb']} # Пропуск клиентов, требующих JS и PO Token
    }

    if use_cookies and os.path.exists(COOKIES_PATH) and os.path.getsize(COOKIES_PATH) > 0:
        logger.info(f"Использование файла куки: {COOKIES_PATH}")
        ydl_opts['cookiefile'] = COOKIES_PATH

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

def _download_youtube(url: str) -> Dict[str, Any]:
    """
    Скачивание YouTube видео через yt-dlp с пропуском веб-клиентов. 
    Мы отключаем куки для YouTube, потому что старые/экспортированные куки 
    вызывают ошибку 'Sign in to confirm you're not a bot' на серверных IP.
    """
    logger.info(f"Загрузка с YouTube через yt-dlp (без куки): {url}")
    return _download_ytdlp(url, use_cookies=False)

def _download_tiktok(url: str) -> Dict[str, Any]:
    """
    Скачивание TikTok через плагин TikWM API (обходит ограничения на возраст/логин).
    """
    logger.info(f"Загрузка с TikTok через TikWM API: {url}")
    try:
        import urllib.request
        import urllib.parse
        import json
        
        req = urllib.request.Request(
            'https://www.tikwm.com/api/',
            data=urllib.parse.urlencode({'url': url, 'hd': 1}).encode('utf-8'),
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            
        if data.get('code') == 0 and 'data' in data and 'play' in data['data']:
            video_info = data['data']
            video_url = video_info['play']
            if video_url.startswith('/'):
                video_url = f"https://www.tikwm.com{video_url}"
                
            video_id = video_info.get('id', 'tiktok_video')
            filepath = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
            
            # Скачиваем файл на диск
            req_video = urllib.request.Request(video_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req_video, timeout=30) as v_resp, open(filepath, 'wb') as out_f:
                out_f.write(v_resp.read())
                
            return {
                "filepath": filepath,
                "title": video_info.get("title", "TikTok Video"),
                "duration": video_info.get("duration"),
                "uploader": video_info.get("author", {}).get("nickname") or video_info.get("author", {}).get("unique_id"),
            }
    except Exception as e:
        logger.warning(f"Сбой TikWM API для TikTok ({e}), переключаемся на yt-dlp...")
        
    return _download_ytdlp(url)

def _download_with_ytdlp(url: str) -> Dict[str, Any]:
    if _is_youtube_url(url):
        return _download_youtube(url)
    elif "tiktok.com" in url or "tik" in url:
        return _download_tiktok(url)
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
