import os
import logging
import asyncio
import traceback
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode, ContentType
from dotenv import load_dotenv
from aiohttp import web

from check_sub import check_subscription, get_subscription_keyboard

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# Пытаемся загрузить шрифт при старте
try:
    test_font = ImageFont.truetype(FONT_PATH, 20)
    logger.info("✅ Шрифт Impact успешно загружен")
except Exception as e:
    logger.error(f"❌ Не удалось загрузить шрифт: {e}")
    logger.info("📝 Скачайте шрифт Impact Cyrillic и положите в папку fonts/")

def resize_image_if_needed(img):
    """
    Увеличивает изображение, если оно слишком маленькое
    """
    # Минимальная ширина для нормального наложения текста
    MIN_WIDTH = 800
    
    if img.width < MIN_WIDTH:
        # Рассчитываем новый размер, сохраняя пропорции
        new_width = MIN_WIDTH
        new_height = int(img.height * (MIN_WIDTH / img.width))
        
        logger.info(f"📏 Изображение слишком маленькое ({img.width}x{img.height})")
        logger.info(f"📈 Увеличиваем до {new_width}x{new_height}")
        
        # Увеличиваем изображение с высоким качеством
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
    return img

def create_meme_image(image_bytes: bytes, top_text: str, bottom_text: str) -> BytesIO:
    """
    Создает мем с текстом как в интернете - классический размер
    """
    try:
        # Открываем изображение
        img = Image.open(BytesIO(image_bytes)).convert('RGBA')
        logger.info(f"✅ Исходное изображение: размер {img.width}x{img.height}")
        
        # Увеличиваем если нужно
        img = resize_image_if_needed(img)
        logger.info(f"✅ После обработки: размер {img.width}x{img.height}")
        
        # Создаем копию
        img_with_text = img.copy()
        draw = ImageDraw.Draw(img_with_text)
        
        # ===== КЛАССИЧЕСКИЙ РАЗМЕР МЕМА =====
        font_size = int(img.width * 0.08)
        font_size = max(40, min(90, font_size))
        logger.info(f"📏 Размер шрифта: {font_size}px")
        
        try:
            font = ImageFont.truetype(FONT_PATH, font_size)
        except:
            font = ImageFont.load_default()
        
        max_text_width = int(img.width * 0.85)
        
        # Функция разбиения на строки
        def split_into_lines(text):
            words = text.upper().split()
            if not words:
                return []
            
            lines = []
            current_line = words[0]
            
            for word in words[1:]:
                test_line = current_line + " " + word
                test_width = draw.textlength(test_line, font=font)
                
                if test_width <= max_text_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            lines.append(current_line)
            return lines
        
        # ===== ОТСТУПЫ =====
        top_offset = int(img.height * 0.03)
        bottom_offset = int(img.height * 0.03)
        
        # Рисуем верхний текст
        if top_text and top_text.strip():
            lines = split_into_lines(top_text)
            
            if lines:
                line_height = font_size + 8
                y = top_offset
                
                for i, line in enumerate(lines):
                    line_width = draw.textlength(line, font=font)
                    x = (img.width - line_width) // 2
                    line_y = y + (i * line_height)
                    
                    # Обводка 3px
                    outline = 3
                    for dx in range(-outline, outline + 1):
                        for dy in range(-outline, outline + 1):
                            if dx != 0 or dy != 0:
                                if (dx*dx + dy*dy) <= outline*outline + 1:
                                    draw.text((x + dx, line_y + dy), line, font=font, fill='black')
                    
                    draw.text((x, line_y), line, font=font, fill='white')
        
        # Рисуем нижний текст
        if bottom_text and bottom_text.strip():
            lines = split_into_lines(bottom_text)
            
            if lines:
                line_height = font_size + 8
                total_height = len(lines) * line_height
                y = img.height - total_height - bottom_offset
                
                for i, line in enumerate(lines):
                    line_width = draw.textlength(line, font=font)
                    x = (img.width - line_width) // 2
                    line_y = y + (i * line_height)
                    
                    outline = 3
                    for dx in range(-outline, outline + 1):
                        for dy in range(-outline, outline + 1):
                            if dx != 0 or dy != 0:
                                if (dx*dx + dy*dy) <= outline*outline + 1:
                                    draw.text((x + dx, line_y + dy), line, font=font, fill='black')
                    
                    draw.text((x, line_y), line, font=font, fill='white')
        
        # Сохраняем
        output = BytesIO()
        img_with_text.save(output, format='PNG', optimize=True)
        output.seek(0)
        
        logger.info("✅ Мем готов")
        return output
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        logger.error(traceback.format_exc())
        raise e

# ============= ВСЕ ОБРАБОТЧИКИ (без изменений) =============
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} запустил бота")
    
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
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} отправил фото")
    
    is_subscribed = await check_subscription(bot, user_id, CHANNEL_ID)
    
    if not is_subscribed:
        keyboard = get_subscription_keyboard(CHANNEL_ID)
        await message.answer(
            "❌ Чтобы пользоваться ботом, нужно подписаться на канал @shtoporch",
            reply_markup=keyboard
        )
        return
    
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        image_bytes = downloaded_file.getvalue()
        
        user_data[user_id] = {'image': image_bytes, 'stage': 'waiting_top_text'}
        
        await message.answer(
            "📝 Теперь напиши текст для ВЕРХНЕЙ части мема\n"
            "(или отправь /skip чтобы пропустить, или /cancel чтобы отменить)"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке фото: {e}")
        await message.answer("❌ Не удалось обработать фото. Попробуй другую картинку.")

@dp.message_handler(commands=['skip'])
async def skip_command(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        await message.answer("❌ Сначала отправь картинку!")
        return
    
    current_stage = user_data[user_id].get('stage')
    
    if current_stage == 'waiting_top_text':
        user_data[user_id]['top_text'] = ''
        user_data[user_id]['stage'] = 'waiting_bottom_text'
        await message.answer(
            "📝 Теперь напиши текст для НИЖНЕЙ части мема\n"
            "(или отправь /skip чтобы пропустить, или /cancel чтобы отменить)"
        )
    elif current_stage == 'waiting_bottom_text':
        await create_meme_from_data(user_id, '', message)
    else:
        await message.answer("❌ Непонятная команда. Напиши /cancel и начни заново.")

@dp.message_handler(commands=['cancel'])
async def cancel_command(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]
        await message.answer("✅ Создание мема отменено. Можешь начать заново с отправки картинки.")
    else:
        await message.answer("🤷 Нет активного процесса создания мема.")

async def create_meme_from_data(user_id, bottom_text, message):
    top_text = user_data[user_id].get('top_text', '')
    image_bytes = user_data[user_id].get('image')
    
    if not image_bytes:
        await message.answer("❌ Что-то пошло не так. Начни заново с отправки картинки.")
        del user_data[user_id]
        return
    
    processing_msg = await message.answer("🔄 Создаю мем... (это может занять несколько секунд)")
    
    try:
        meme_image = create_meme_image(image_bytes, top_text, bottom_text)
        
        await message.answer_photo(
            photo=meme_image,
            caption="🎉 Твой мем готов!\n\nСоздай новый - отправь ещё картинку!"
        )
        
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания мема: {e}")
        logger.error(traceback.format_exc())
        await message.answer(
            "❌ Не удалось создать мем.\n"
            "Попробуй другую картинку или напиши /start"
        )
    
    del user_data[user_id]

@dp.message_handler(lambda message: message.text and not message.text.startswith('/'))
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    
    is_subscribed = await check_subscription(bot, user_id, CHANNEL_ID)
    
    if not is_subscribed:
        keyboard = get_subscription_keyboard(CHANNEL_ID)
        await message.answer(
            "❌ Чтобы пользоваться ботом, нужно подписаться на канал @shtoporch",
            reply_markup=keyboard
        )
        return
    
    if user_id not in user_data:
        await message.answer(
            "❌ Сначала отправь картинку!\n"
            "Или напиши /start чтобы начать"
        )
        return
    
    current_stage = user_data[user_id].get('stage')
    
    if current_stage == 'waiting_top_text':
        if len(message.text) > 200:
            await message.answer("❌ Текст слишком длинный! Максимум 200 символов.")
            return
            
        user_data[user_id]['top_text'] = message.text
        user_data[user_id]['stage'] = 'waiting_bottom_text'
        await message.answer(
            "📝 Теперь напиши текст для НИЖНЕЙ части мема\n"
            "(или отправь /skip чтобы пропустить, или /cancel чтобы отменить)"
        )
        
    elif current_stage == 'waiting_bottom_text':
        if len(message.text) > 200:
            await message.answer("❌ Текст слишком длинный! Максимум 200 символов.")
            return
        
        await create_meme_from_data(user_id, message.text, message)

# ============= RENDER =============
async def handle_health(request):
    return web.Response(text="Бот работает!")

async def run_web_server():
    app = web.Application()
    app.router.add_get('/', handle_health)
    app.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    
    logger.info("🌐 Веб-сервер для Health Check запущен на порту 10000")
    await site.start()
    
    await asyncio.Event().wait()

async def main():
    asyncio.create_task(run_web_server())
    await asyncio.sleep(2)
    await bot.delete_webhook()
    await asyncio.sleep(1)
    logger.info("🤖 Бот запускается...")
    await dp.start_polling()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        logger.error(traceback.format_exc())
