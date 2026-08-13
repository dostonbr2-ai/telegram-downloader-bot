import asyncio
import os
import glob
import logging
import re
import json
from typing import Dict, Any, Optional, List
import yt_dlp

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
COOKIES_PATH = os.path.join(os.getcwd(), "cookies.txt")

def _is_youtube_url(url: str) -> bool:
    return bool(re.search(r"(?:youtube\.com|youtu\.be)", url, re.IGNORECASE))

def _is_tiktok_url(url: str) -> bool:
    return bool(re.search(r"(?:tiktok\.com|douyin\.com)", url, re.IGNORECASE))

def _is_instagram_url(url: str) -> bool:
    return bool(re.search(r"(?:instagram\.com|instagr\.am)", url, re.IGNORECASE))

# ==========================================
# 1. TIKTOK MULTI-ENGINE DOWNLOADER
# ==========================================
def _download_tiktok_tikwm(url: str) -> Optional[Dict[str, Any]]:
    """
    Первичный движок для TikTok через TikWM API (поддерживает как видео, так и фото-слайдшоу).
    """
    try:
        from curl_cffi import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.tiktok.com/'
        }
        
        resp = requests.post(
            'https://www.tikwm.com/api/',
            data={'url': url, 'hd': 1},
            headers=headers,
            timeout=15,
            impersonate="chrome"
        )
        data = resp.json()
        
        if data.get('code') == 0 and 'data' in data:
            vdata = data['data']
            title = vdata.get("title", "TikTok")
            uploader = vdata.get("author", {}).get("nickname") or vdata.get("author", {}).get("unique_id")
            
            # Проверяем, является ли пост слайдшоу из фотографий
            if "images" in vdata and isinstance(vdata["images"], list) and len(vdata["images"]) > 0:
                logger.info(f"Обнаружено слайдшоу TikTok из {len(vdata['images'])} фото.")
                photo_paths = []
                for idx, img_url in enumerate(vdata["images"]):
                    p_resp = requests.get(img_url, headers=headers, timeout=20, impersonate="chrome")
                    img_path = os.path.join(DOWNLOAD_DIR, f"tt_photo_{vdata.get('id', 'photo')}_{idx}.jpg")
                    with open(img_path, 'wb') as f:
                        f.write(p_resp.content)
                    photo_paths.append(img_path)
                
                return {
                    "type": "photos",
                    "filepaths": photo_paths,
                    "title": title,
                    "uploader": uploader
                }

            # Если это обычное видео (приоритет отдаем HD качеству без водяных знаков)
            video_url = vdata.get('hdplay') or vdata.get('play') or vdata.get('wmplay')
            if video_url:
                if video_url.startswith('/'):
                    video_url = f"https://www.tikwm.com{video_url}"
                    
                video_id = str(vdata.get('id', 'tiktok_video'))
                filepath = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
                
                v_resp = requests.get(video_url, headers=headers, timeout=30, impersonate="chrome")
                with open(filepath, 'wb') as out_f:
                    out_f.write(v_resp.content)
                    
                return {
                    "type": "video",
                    "filepath": filepath,
                    "title": title,
                    "duration": vdata.get("duration"),
                    "uploader": uploader
                }
    except Exception as e:
        logger.warning(f"Ошибка TikWM API: {e}")
    return None

def _download_tiktok_ssstik(url: str) -> Optional[Dict[str, Any]]:
    """
    Вторичный запасной движок для TikTok через SSSTik API.
    """
    try:
        from curl_cffi import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://ssstik.io/'
        }
        resp = requests.post(
            'https://ssstik.io/abc?url=dl',
            data={'id': url, 'locale': 'en', 'tt': 'b1V3'},
            headers=headers,
            timeout=15,
            impersonate="chrome"
        )
        html = resp.text
        match = re.search(r'href="(https://[^"]*tikcdn[^"]*)"', html)
        if match:
            video_url = match.group(1)
            filepath = os.path.join(DOWNLOAD_DIR, "ssstik_video.mp4")
            v_resp = requests.get(video_url, headers={'Referer': 'https://www.tiktok.com/'}, timeout=30, impersonate="chrome")
            with open(filepath, 'wb') as f:
                f.write(v_resp.content)
            return {
                "type": "video",
                "filepath": filepath,
                "title": "TikTok Video",
                "uploader": None
            }
    except Exception as e:
        logger.warning(f"Ошибка SSSTik API: {e}")
    return None

def _download_tiktok(url: str) -> Dict[str, Any]:
    # 1. Пробуем TikWM (видео или фото)
    res = _download_tiktok_tikwm(url)
    if res:
        return res
    
    # 2. Пробуем SSSTik
    res = _download_tiktok_ssstik(url)
    if res:
        return res
        
    # 3. Финальный фоллбек на yt-dlp без куки
    return _download_ytdlp(url, use_cookies=False)

# ==========================================
# 2. YOUTUBE MULTI-ENGINE DOWNLOADER
# ==========================================
def _download_youtube_pytubefix(url: str) -> Optional[Dict[str, Any]]:
    """
    Загрузка YouTube через pytubefix (мгновенно обходит блокировки бота 'Sign in to confirm you're not a bot').
    """
    logger.info(f"Загрузка с YouTube через pytubefix: {url}")
    try:
        from pytubefix import YouTube
        yt = YouTube(url)
        ys = yt.streams.get_highest_resolution()
        if not ys:
            ys = yt.streams.filter(progressive=True, file_extension='mp4').first()
            
        if ys:
            filepath = ys.download(output_path=DOWNLOAD_DIR)
            return {
                "type": "video",
                "filepath": filepath,
                "title": yt.title or "YouTube Video",
                "duration": int(yt.length) if yt.length else None,
                "uploader": yt.author,
            }
    except Exception as e:
        logger.warning(f"Сбой pytubefix ({e}), переключаемся на yt-dlp...")
    return None

def _download_youtube(url: str) -> Dict[str, Any]:
    """
    Универсальный многоуровневый загрузчик YouTube:
    - Первичный движок: pytubefix на нормализованный URL (автоматический PO Token / PO Client)
    - Вторичный движок: yt-dlp с куки
    - Третичный движок: yt-dlp без куки + Chrome impersonate
    """
    logger.info(f"Загрузка с YouTube: {url}")
    
    # Нормализуем YouTube Shorts и короткие ссылки в формат watch?v= ДО отправки в движки
    match = re.search(r'(?:v=|\/shorts\/|\/embed\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
    clean_url = f"https://www.youtube.com/watch?v={match.group(1)}" if match else url
    
    # 1. Сначала пробуем pytubefix на чистый URL
    res = _download_youtube_pytubefix(clean_url)
    if res:
        return res

    # 2. Попытка yt-dlp с куки
    try:
        return _download_ytdlp(clean_url, use_cookies=True)
    except Exception as e1:
        logger.warning(f"YouTube Попытка yt-dlp (с куки) завершилась с ошибкой: {e1}")

    # 3. Попытка yt-dlp без куки с имперсонацией Chrome
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget
        extra_opts = {
            'impersonate': ImpersonateTarget.from_str('chrome'),
            'extractor_args': {'youtube': ['player_client=ios,android']}
        }
        return _download_ytdlp(clean_url, use_cookies=False, extra_opts=extra_opts)
    except Exception as e2:
        logger.warning(f"YouTube Попытка yt-dlp (без куки + Chrome impersonate) завершилась с ошибкой: {e2}")

    # 4. Попытка 4: Чистый фоллбек без куки
    return _download_ytdlp(clean_url, use_cookies=False)

# ==========================================
# 3. INSTAGRAM MULTI-ENGINE DOWNLOADER
# ==========================================
def _download_instagram(url: str) -> Dict[str, Any]:
    """
    Загрузка с Instagram через yt-dlp с использованием куки.
    """
    logger.info(f"Загрузка с Instagram: {url}")
    return _download_ytdlp(url, use_cookies=True)

# ==========================================
# 4. UNIVERSAL YT-DLP CORE ENGINE
# ==========================================
def _download_ytdlp(url: str, use_cookies: bool = True, extra_opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    output_template = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")
    
    ydl_opts = {
        'format': 'bestvideo[filesize<=48M]+bestaudio/best[filesize<=48M]/best/b',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'extractor_args': {'youtube': ['player_skip=web,tv,mweb']} # Игнорируем блокирующиеся клиенты YouTube
    }

    if extra_opts:
        ydl_opts.update(extra_opts)

    if use_cookies and os.path.exists(COOKIES_PATH) and os.path.getsize(COOKIES_PATH) > 0:
        logger.info(f"Использование файла куки для {url}: {COOKIES_PATH}")
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
            raise FileNotFoundError("Скачанный видеофайл не найден на диске.")
    
    return {
        "type": "video",
        "filepath": final_path,
        "title": info.get("title", "Видео"),
        "duration": int(float(info["duration"])) if info.get("duration") is not None else None,
        "width": int(float(info["width"])) if info.get("width") is not None else None,
        "height": int(float(info["height"])) if info.get("height") is not None else None,
        "uploader": info.get("uploader") or info.get("uploader_id"),
    }

def _download_router(url: str) -> Dict[str, Any]:
    if _is_youtube_url(url):
        return _download_youtube(url)
    elif _is_tiktok_url(url):
        return _download_tiktok(url)
    elif _is_instagram_url(url):
        return _download_instagram(url)
    else:
        return _download_ytdlp(url, use_cookies=False)

async def download_video(url: str) -> Dict[str, Any]:
    """
    Асинхронный точечный вызов загрузчика медиа.
    """
    return await asyncio.to_thread(_download_router, url)

def remove_file(filepath_or_list: Optional[Any]):
    """
    Удаление одиночных файлов или списка фото после отправки в Telegram.
    """
    if not filepath_or_list:
        return
        
    paths = filepath_or_list if isinstance(filepath_or_list, list) else [filepath_or_list]
    for fp in paths:
        if isinstance(fp, str) and os.path.exists(fp):
            try:
                os.remove(fp)
                logger.info(f"Удален временный файл: {fp}")
            except Exception as e:
                logger.error(f"Ошибка при удалении {fp}: {e}")
