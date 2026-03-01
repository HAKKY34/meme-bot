import os
import logging
import asyncio
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode, ContentType
from dotenv import load_dotenv
from aiohttp import web
import threading

from check_sub import check_subscription, get_subscription_keyboard

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Словарь для временного хранения данных пользователя
user_data = {}

# Загрузка шрифта
FONT_PATH = "fonts/impact.ttf"

def create_meme_image(image_bytes: bytes, top_text: str, bottom_text: str) -> BytesIO:
    """
    Создает мем с текстом сверху и снизу
    """
    # Открываем изображение
    img = Image.open(BytesIO(image_bytes)).convert('RGBA')
    
    # Создаем копию для рисования
    img_with_text = img.copy()
    draw = ImageDraw.Draw(img_with_text)
    
    # Рассчитываем размер шрифта (10% от ширины изображения)
    font_size = int(img.width * 0.1)
    
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except:
        # Если шрифт не загрузился, используем дефолтный
        font = ImageFont.load_default()
        logging.warning("Шрифт Impact не найден, используется дефолтный")
    
    # Функция для отрисовки текста с обводкой
    def draw_text_with_outline(text, y_pos, is_top=True):
        text = text.upper()
        
        # Получаем размер текста
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Центрируем текст
        x = (img.width - text_width) // 2
        
        # Корректируем позицию Y
        if is_top:
            y = y_pos
        else:
            y = img.height - text_height - y_pos
        
        # Рисуем обводку (черный текст с небольшим смещением)
        outline_range = max(2, int(font_size * 0.05))
        for dx in range(-outline_range, outline_range + 1):
            for dy in range(-outline_range, outline_range + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill='black')
        
        # Рисуем основной текст (белый)
        draw.text((x, y), text, font=font, fill='white')
    
    # Рисуем верхний текст
    draw_text_with_outline(top_text, 20, is_top=True)
    
    # Рисуем нижний текст
    draw_text_with_outline(bottom_text, 20, is_top=False)
    
    # Сохраняем в байты
    output = BytesIO()
    img_with_text.save(output, format='PNG')
    output.seek(0)
    
    return output

# ============= НОВЫЙ КОД ДЛЯ RENDER =============
# Создаем простой HTTP сервер для Health Check
async def handle_health(request):
    """Обработчик для проверки здоровья"""
    return web.Response(text="Бот работает!")

async def run_web_server():
    """Запускает веб-сервер на порту 10000"""
    app = web.Application()
    app.router.add_get('/', handle_health)
    app.router.add_get('/health', handle_health)
    
    # Render ожидает порт 10000
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    
    logging.info("🌐 Веб-сервер для Health Check запущен на порту 10000")
    await site.start()
    
    # Держим сервер запущенным
    await asyncio.Event().wait()
# ================================================

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    # Проверяем подписку
    is_subscribed = await check_subscription(bot, user_id, CHANNEL_ID)
    
    if is_subscribed:
        await message.answer(
            "👋 Привет! Я бот для создания мемов.\n\n"
            "📝 Как пользоваться:\n"
            "1. Отправь мне картинку\n"
            "2. Напиши текст для верхней части\n"
            "3. Напиши текст для нижней части\n\n"
            "Я сделаю из этого мем!"
        )
    else:
        keyboard = get_subscription_keyboard(CHANNEL_ID)
        await message.answer(
            "❌ Чтобы пользоваться ботом, нужно подписаться на канал @shtoporch",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

@dp.callback_query_handler(lambda c: c.data == 'check_sub')
async def check_sub_callback(callback_query: types.CallbackQuery):
    """Проверка подписки после нажатия кнопки"""
    user_id = callback_query.from_user.id
    
    is_subscribed = await check_subscription(bot, user_id, CHANNEL_ID)
    
    if is_subscribed:
        await bot.answer_callback_query(callback_query.id, text="✅ Подписка подтверждена!")
        await bot.send_message(
            user_id,
            "👋 Отлично! Теперь ты можешь создавать мемы.\n\n"
            "📝 Отправь мне картинку, и я скажу что делать дальше."
        )
    else:
        await bot.answer_callback_query(
            callback_query.id, 
            text="❌ Подписка не найдена! Подпишись и нажми кнопку снова",
            show_alert=True
        )

@dp.message_handler(content_types=ContentType.PHOTO)
async def handle_photo(message: types.Message):
    """Обработчик получения фото"""
    user_id = message.from_user.id
    
    # Проверяем подписку
    is_subscribed = await check_subscription(bot, user_id, CHANNEL_ID)
    
    if not is_subscribed:
        keyboard = get_subscription_keyboard(CHANNEL_ID)
        await message.answer(
            "❌ Чтобы пользоваться ботом, нужно подписаться на канал @shtoporch",
            reply_markup=keyboard
        )
        return
    
    # Получаем фото максимального размера
    photo = message.photo[-1]
    
    # Скачиваем фото
    file_info = await bot.get_file(photo.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    image_bytes = downloaded_file.getvalue()
    
    # Сохраняем фото во временное хранилище
    user_data[user_id] = {'image': image_bytes, 'stage': 'waiting_top_text'}
    
    await message.answer(
        "📝 Теперь напиши текст для ВЕРХНЕЙ части мема"
    )

@dp.message_handler(lambda message: message.text and not message.text.startswith('/'))
async def handle_text(message: types.Message):
    """Обработчик текстовых сообщений"""
    user_id = message.from_user.id
    
    # Проверяем подписку
    is_subscribed = await check_subscription(bot, user_id, CHANNEL_ID)
    
    if not is_subscribed:
        keyboard = get_subscription_keyboard(CHANNEL_ID)
        await message.answer(
            "❌ Чтобы пользоваться ботом, нужно подписаться на канал @shtoporch",
            reply_markup=keyboard
        )
        return
    
    # Проверяем, есть ли пользователь в процессе создания мема
    if user_id not in user_data:
        await message.answer(
            "❌ Сначала отправь картинку!"
        )
        return
    
    current_stage = user_data[user_id].get('stage')
    
    if current_stage == 'waiting_top_text':
        # Сохраняем верхний текст и ждем нижний
        user_data[user_id]['top_text'] = message.text
        user_data[user_id]['stage'] = 'waiting_bottom_text'
        await message.answer(
            "📝 Теперь напиши текст для НИЖНЕЙ части мема"
        )
        
    elif current_stage == 'waiting_bottom_text':
        # Получаем нижний текст и создаем мем
        bottom_text = message.text
        top_text = user_data[user_id].get('top_text', '')
        image_bytes = user_data[user_id].get('image')
        
        if not image_bytes or not top_text:
            await message.answer("❌ Что-то пошло не так. Начни заново с отправки картинки.")
            del user_data[user_id]
            return
        
        # Отправляем сообщение о начале обработки
        processing_msg = await message.answer("🔄 Создаю мем...")
        
        try:
            # Создаем мем
            meme_image = create_meme_image(image_bytes, top_text, bottom_text)
            
            # Отправляем результат
            await message.answer_photo(
                photo=meme_image,
                caption="🎉 Твой мем готов!\n\nСоздай новый - отправь ещё картинку"
            )
            
            # Удаляем сообщение о обработке
            await processing_msg.delete()
            
        except Exception as e:
            logging.error(f"Ошибка создания мема: {e}")
            await message.answer("❌ Не удалось создать мем. Попробуй другую картинку.")
        
        # Очищаем данные пользователя
        del user_data[user_id]

async def main():
    """Основная функция запуска бота"""
    # Запускаем HTTP сервер для Health Check в фоне
    asyncio.create_task(run_web_server())
    
    # Даем серверу время запуститься
    await asyncio.sleep(3)
    
    # Удаляем вебхук на всякий случай
    await bot.delete_webhook()
    
    # Небольшая пауза после удаления вебхука
    await asyncio.sleep(1)
    
    # Запускаем бота с пропуском старых обновлений
    logging.info("🤖 Бот запускается...")
    await dp.start_polling(skip_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен")
