# 🎬 Telegram Bot для скачивания видео (Instagram, TikTok, YouTube)

Асинхронный Telegram-бот на Python (`aiogram 3` + `yt-dlp`), который скачивает видео из Instagram (Reels), TikTok (без водяных знаков) и YouTube (Shorts и обычные видео) при отправке ссылки в чат.

---

## 📌 Быстрый старт и получение токена бота

### Шаг 1: Создание бота в Telegram
1. Откройте Telegram и найдите бота [@BotFather](https://t.me/BotFather).
2. Отправьте команду `/newbot`.
3. Введите имя для вашего бота (например, `My Media Downloader`).
4. Введите юзернейм для бота, заканчивающийся на `bot` (например, `super_downloader_media_bot`).
5. `@BotFather` пришлет вам **HTTP API Token**. Сохраните его!

### Шаг 2: Настройка переменных окружения
1. Переименуйте файл `.env.example` в `.env` (или создайте файл `.env`).
2. Вставьте ваш токен:
   ```env
   BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

---

## 🌐 Как развернуть бота в облаке (24/7 работа, НЕ на своем компьютере)

Чтобы бот работал круглые сутки самостоятельно, его нужно запустить на удаленном сервере или бесплатном/недорогом хостинге. Ниже приведены популярные способы:

---

### Вариант 1: Запуск на VPS (Ubuntu / Debian) — Самый надежный способ
Если у вас есть виртуальный сервер (например, Aeza, Timeweb, Hetzner, Selectel и т.д.):

#### Способ 1.1: Через Docker (Рекомендуется)
1. Загрузите файлы проекта на ваш VPS:
   ```bash
   git clone <ссылка_на_ваш_репозиторий>
   cd telegram-media-downloader-bot
   ```
2. Создайте файл `.env` и указать ваш `BOT_TOKEN`:
   ```bash
   nano .env
   ```
3. Запустите бота через Docker Compose:
   ```bash
   docker-compose up -d --build
   ```
   *Бот автоматически запустится и будет работать в фоновом режиме даже при перезагрузке сервера.*

#### Способ 1.2: Без Docker (через systemd)
1. Установите Python и FFmpeg на сервер:
   ```bash
   sudo apt update && sudo apt install -y python3 python3-pip python3-venv ffmpeg
   ```
2. Перейдите в папку с ботом и создайте виртуальное окружение:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Настройте службу `systemd` для фоновой работы:
   ```bash
   sudo nano /etc/systemd/system/downloader_bot.service
   ```
   Вставьте содержимое:
   ```ini
   [Unit]
   Description=Telegram Media Downloader Bot
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/path/to/telegram-media-downloader-bot
   ExecStart=/path/to/telegram-media-downloader-bot/venv/bin/python main.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
4. Запустите сервис:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable downloader_bot
   sudo systemctl start downloader_bot
   ```

---

### Вариант 2: Бесплатный/Облачный хостинг (Render.com)

1. Создайте репозиторий на [GitHub](https://github.com) и выложите туда этот проект.
2. Зарегистрируйтесь на [Render.com](https://render.com).
3. Нажмите **New +** -> **Web Service** или **Background Worker**.
4. Подключите ваш GitHub репозиторий.
5. Выберите **Docker** в качестве Environment (системные зависимости и `ffmpeg` подтянутся автоматически из `Dockerfile`).
6. В разделе **Environment Variables** добавьте переменную:
   - `BOT_TOKEN` = ваш токен от BotFather.
7. Нажмите **Deploy**. Бот начнет работать в облаке!

---

### Вариант 3: Хостинг Railway.app / Amvera.ru / Koyeb.com

1. Загрузите код бота в Ваш GitHub репозиторий.
2. Подключите репозиторий в панель хостинга (Railway / Amvera / Koyeb).
3. Хостинг автоматически определит `Dockerfile` или `requirements.txt`.
4. Введите переменную `BOT_TOKEN` в настройках проекта.
5. Запустите проект.

---

## 🛠️ Локальное тестирование на ПК (опционально)

Если перед выгрузкой в облако вы хотите протестировать бота у себя на компьютере:

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. Убедитесь, что у вас установлен `ffmpeg` (для объединения видео и аудио от yt-dlp).
3. Запустите бота:
   ```bash
   python main.py
   ```
