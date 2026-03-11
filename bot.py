import os
import logging
import asyncio
import traceback
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode, ContentType, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from aiohttp import web

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

# Два канала для подписки
CHANNEL_1 = "@krovotok_tg"
CHANNEL_2 = "@celebrityfunfacts"
CHANNELS = [CHANNEL_1, CHANNEL_2]

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

async def check_subscription(user_id: int):
    """Проверяет подписку на ВСЕ каналы из списка CHANNELS"""
    not_subscribed = []
    
    for channel in CHANNELS:
        try:
            logger.info(f"🔍 Проверяю канал {channel} для пользователя {user_id}")
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            
            if member.status in ['left', 'kicked']:
                not_subscribed.append(channel)
                logger.info(f"❌ Пользователь {user_id} НЕ подписан на {channel}")
            else:
                logger.info(f"✅ Пользователь {user_id} подписан на {channel}")
                
        except Exception as e:
            logger.error(f"⚠️ Ошибка при проверке {channel}: {e}")
            not_subscribed.append(channel)
    
    is_subscribed = len(not_subscribed) == 0
    logger.info(f"📊 Итог: подписан={is_subscribed}, не подписан на: {not_subscribed}")
    
    return is_subscribed, not_subscribed

def get_subscription_keyboard(not_subscribed):
    """Создает клавиатуру с кнопками для каждого канала"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for channel in not_subscribed:
        channel_name = channel.replace('@', '')
        btn = InlineKeyboardButton(
            text=f"📢 Подписаться на {channel_name}",
            url=f"https://t.me/{channel_name}"
        )
        keyboard.add(btn)
    
    check_btn = InlineKeyboardButton(
        text="✅ Я подписался",
        callback_data="check_sub"
    )
    keyboard.add(check_btn)
    
    return keyboard

def resize_image_if_needed(img):
    """Увеличивает маленькие изображения"""
    MIN_WIDTH = 800
    
    if img.width < MIN_WIDTH:
        new_width = MIN_WIDTH
        new_height = int(img.height * (MIN_WIDTH / img.width))
        logger.info(f"📏 Увеличиваем с {img.width}x{img.height} до {new_width}x{new_height}")
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
    return img

def create_meme_image(image_bytes: bytes, top_text: str, bottom_text: str) -> BytesIO:
    """
    Создает мем с текстом как в интернете - максимум 2 строки
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
        
        # Функция для разбиения текста на максимум 2 строки
        def split_into_lines(text, max_width, start_font_size):
            if not text:
                return [], start_font_size
            
            words = text.upper().split()
            if not words:
                return [], start_font_size
            
            # Сначала пробуем поместить всё в одну строку
            for font_size in range(start_font_size, 30, -2):
                try:
                    test_font = ImageFont.truetype(FONT_PATH, font_size)
                except:
                    test_font = ImageFont.load_default()
                
                full_text = " ".join(words)
                text_width = draw.textlength(full_text, font=test_font)
                
                if text_width <= max_width:
                    return [full_text], font_size
            
            # Если не влезло в одну строку, пробуем разбить на 2
            best_font_size = start_font_size
            best_lines = []
            
            for font_size in range(start_font_size, 30, -2):
                try:
                    test_font = ImageFont.truetype(FONT_PATH, font_size)
                except:
                    test_font = ImageFont.load_default()
                
                # Пробуем разные варианты разбиения
                found_good = False
                
                for i in range(1, len(words)):
                    line1 = " ".join(words[:i])
                    line2 = " ".join(words[i:])
                    
                    w1 = draw.textlength(line1, font=test_font)
                    w2 = draw.textlength(line2, font=test_font)
                    
                    if w1 <= max_width and w2 <= max_width:
                        best_lines = [line1, line2]
                        best_font_size = font_size
                        found_good = True
                        break
                
                if found_good:
                    break
            
            if best_lines:
                return best_lines, best_font_size
            
            # Если ничего не подошло - разбиваем примерно пополам
            mid = len(words) // 2
            return [" ".join(words[:mid]), " ".join(words[mid:])], 30
        
        # ===== УВЕЛИЧЕННЫЙ РАЗМЕР ТЕКСТА (12% от ширины) =====
        base_font_size = int(img.width * 0.12)  # 12% от ширины
        base_font_size = max(50, min(120, base_font_size))  # От 50 до 120 пикселей
        
        # Максимальная ширина текста
        max_text_width = int(img.width * 0.85)
        
        # Обрабатываем верхний текст
        top_lines = []
        top_font_size = base_font_size
        if top_text and top_text.strip():
            top_lines, top_font_size = split_into_lines(top_text, max_text_width, base_font_size)
            logger.info(f"📏 Верхний текст: размер {top_font_size}px, {len(top_lines)} строк")
        
        # Обрабатываем нижний текст
        bottom_lines = []
        bottom_font_size = base_font_size
        if bottom_text and bottom_text.strip():
            bottom_lines, bottom_font_size = split_into_lines(bottom_text, max_text_width, base_font_size)
            logger.info(f"📏 Нижний текст: размер {bottom_font_size}px, {len(bottom_lines)} строк")
        
        # Загружаем шрифты для каждого текста
        try:
            top_font = ImageFont.truetype(FONT_PATH, top_font_size) if top_lines else None
        except:
            top_font = None
        
        try:
            bottom_font = ImageFont.truetype(FONT_PATH, bottom_font_size) if bottom_lines else None
        except:
            bottom_font = None
        
        # ===== ОТСТУПЫ =====
        top_offset = 2  # Сверху 2px
        bottom_offset = 20  # Снизу 20px (чтобы не вылезал)
        
        # Рисуем верхний текст
        if top_lines and top_font:
            line_height = top_font_size + 10  # Межстрочный интервал
            y = top_offset
            
            for i, line in enumerate(top_lines):
                line_width = draw.textlength(line, font=top_font)
                x = (img.width - line_width) // 2
                line_y = y + (i * line_height)
                
                # Обводка 3px
                outline = 3
                for dx in range(-outline, outline + 1):
                    for dy in range(-outline, outline + 1):
                        if dx != 0 or dy != 0:
                            if (dx*dx + dy*dy) <= outline*outline + 1:
                                draw.text((x + dx, line_y + dy), line, font=top_font, fill='black')
                
                draw.text((x, line_y), line, font=top_font, fill='white')
        
        # Рисуем нижний текст
        if bottom_lines and bottom_font:
            line_height = bottom_font_size + 10
            total_height = len(bottom_lines) * line_height
            y = img.height - total_height - bottom_offset
            
            for i, line in enumerate(bottom_lines):
                line_width = draw.textlength(line, font=bottom_font)
                x = (img.width - line_width) // 2
                line_y = y + (i * line_height)
                
                outline = 3
                for dx in range(-outline, outline + 1):
                    for dy in range(-outline, outline + 1):
                        if dx != 0 or dy != 0:
                            if (dx*dx + dy*dy) <= outline*outline + 1:
                                draw.text((x + dx, line_y + dy), line, font=bottom_font, fill='black')
                
                draw.text((x, line_y), line, font=bottom_font, fill='white')
        
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

# ============= ОБРАБОТЧИКИ =============
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} запустил бота")
    
    is_subscribed, not_subscribed = await check_subscription(user_id)
    
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
        keyboard = get_subscription_keyboard(not_subscribed)
        channels_text = "\n".join([f"• {ch}" for ch in not_subscribed])
        await message.answer(
            f"❌ Чтобы пользоваться ботом, нужно подписаться на каналы:\n{channels_text}",
            reply_markup=keyboard
        )

@dp.callback_query_handler(lambda c: c.data == 'check_sub')
async def check_sub_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    
    is_subscribed, not_subscribed = await check_subscription(user_id)
    
    if is_subscribed:
        await bot.answer_callback_query(callback_query.id, text="✅ Подписка подтверждена!")
        await bot.send_message(
            user_id,
            "👋 Отлично! Теперь ты можешь создавать мемы.\n\n"
            "📝 Отправь мне картинку, и я скажу что делать дальше."
        )
    else:
        keyboard = get_subscription_keyboard(not_subscribed)
        channels_text = "\n".join([f"• {ch}" for ch in not_subscribed])
        
        await bot.answer_callback_query(
            callback_query.id, 
            text="❌ Подписка не найдена",
            show_alert=True
        )
        
        await bot.send_message(
            user_id,
            f"❌ Всё ещё не подписан на:\n{channels_text}",
            reply_markup=keyboard
        )

@dp.message_handler(content_types=ContentType.PHOTO)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} отправил фото")
    
    is_subscribed, not_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        keyboard = get_subscription_keyboard(not_subscribed)
        channels_text = "\n".join([f"• {ch}" for ch in not_subscribed])
        await message.answer(
            f"❌ Чтобы пользоваться ботом, нужно подписаться на каналы:\n{channels_text}",
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
        logger.error(f"❌ Ошибка: {e}")
        await message.answer("❌ Не удалось обработать фото")

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

@dp.message_handler(commands=['cancel'])
async def cancel_command(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]
        await message.answer("✅ Создание мема отменено")
    else:
        await message.answer("🤷 Нет активного процесса")

async def create_meme_from_data(user_id, bottom_text, message):
    top_text = user_data[user_id].get('top_text', '')
    image_bytes = user_data[user_id].get('image')
    
    if not image_bytes:
        await message.answer("❌ Ошибка")
        del user_data[user_id]
        return
    
    processing_msg = await message.answer("🔄 Создаю мем...")
    
    try:
        meme_image = create_meme_image(image_bytes, top_text, bottom_text)
        
        await message.answer_photo(
            photo=meme_image,
            caption="🎉 Твой мем готов!\n\nСоздай новый - отправь ещё картинку!"
        )
        
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await message.answer("❌ Не удалось создать мем")
    
    del user_data[user_id]

@dp.message_handler(lambda message: message.text and not message.text.startswith('/'))
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    
    is_subscribed, not_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        keyboard = get_subscription_keyboard(not_subscribed)
        channels_text = "\n".join([f"• {ch}" for ch in not_subscribed])
        await message.answer(
            f"❌ Чтобы пользоваться ботом, нужно подписаться на каналы:\n{channels_text}",
            reply_markup=keyboard
        )
        return
    
    if user_id not in user_data:
        await message.answer("❌ Сначала отправь картинку!")
        return
    
    current_stage = user_data[user_id].get('stage')
    
    if current_stage == 'waiting_top_text':
        if len(message.text) > 200:
            await message.answer("❌ Текст слишком длинный")
            return
            
        user_data[user_id]['top_text'] = message.text
        user_data[user_id]['stage'] = 'waiting_bottom_text'
        await message.answer(
            "📝 Теперь напиши текст для НИЖНЕЙ части мема\n"
            "(или отправь /skip чтобы пропустить)"
        )
        
    elif current_stage == 'waiting_bottom_text':
        if len(message.text) > 200:
            await message.answer("❌ Текст слишком длинный")
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
    
    logger.info("🌐 Веб-сервер запущен")
    await site.start()
    await asyncio.Event().wait()

async def main():
    asyncio.create_task(run_web_server())
    await asyncio.sleep(2)
    await bot.delete_webhook()
    logger.info("🤖 Бот запускается...")
    await dp.start_polling()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
