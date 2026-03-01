FROM python:3.9-slim

WORKDIR /app

# Устанавливаем зависимости для Pillow
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY . .

# Создаем папку для шрифтов если её нет
RUN mkdir -p fonts

# Запускаем бота
CMD ["python", "bot.py"]

