# Используем легкий базовый образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости: ffmpeg, nodejs (для JS challenge yt-dlp) и ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код бота
COPY . .

# Команда для запуска бота
CMD ["python", "main.py"]
