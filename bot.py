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
BOT_USERNAME = "@yourownmemes_bot"  # Водяной знак

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

def add_watermark(draw, img_width, img_height):
    """Добавляет водяной знак (юзернейм бота) по центру справа с прозрачностью 5%"""
    try:
        # Маленький шрифт для водяного знака
        watermark_font = ImageFont.truetype(FONT_PATH, int(img_height * 0.025))  # Еще меньше
        
        # Текст водяного знака
        watermark_text = BOT_USERNAME
        
        # Получаем размер текста
        text_width = draw.textlength(watermark_text, font=watermark_font)
        text_height = watermark_font.size
        
        # Позиция: по центру вертикали, справа с отступом
        x = img_width - text_width - 8
        y = (img_height - text_height) // 2
        
        # Рисуем с прозрачностью 5%
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), watermark_text, font=watermark_font, fill='black')
        
        # Основной текст с прозрачностью 5%
        draw.text((x, y), watermark_text, font=watermark_font, fill=(255, 255, 255, 13))
        
        logger.info("✅ Водяной знак добавлен")
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении водяного знака: {e}")

def create_meme_image(image_bytes: bytes, top_text: str, bottom_text: str) -> BytesIO:
    """
    Создает мем с текстом сверху и снизу
    """
    try:
        # Открываем изображение
        img = Image.open(BytesIO(image_bytes)).convert('RGBA')
        logger.info(f"✅ Изображение загружено: размер {img.width}x{img.height}")
        
        # Создаем копию для рисования
        img_with_text = img.copy()
        draw = ImageDraw.Draw(img_with_text, 'RGBA')
        
        # Функция для разбиения текста на строки
        def split_text_into_lines(text, font, max_width):
            words = text.upper().split()
            if not words:
                return []
            
            lines = []
            current_line = words[0]
            
            for word in words[1:]:
                test_line = current_line + " " + word
                test_width = draw.textlength(test_line, font=font)
                
                if test_width <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            
            lines.append(current_line)
            return lines
        
        # РАЗМЕР ШРИФТА - ТЕПЕРЬ МАЛЕНЬКИЙ!
        def get_font_size(img_width):
            # Фиксированный небольшой размер относительно картинки
            # Для широких картинок - не больше 50px
            base_size = int(img_width * 0.05)  # 5% от ширины
            return max(30, min(50, base_size))  # От 30 до 50 пикселей
        
        # Ширина текста - 60% от картинки (чтобы не расползался)
        max_text_width = int(img.width * 0.6)
        
        # ПОЛНАЯ ПЕРЕРАБОТКА РИСОВАНИЯ ТЕКСТА
        def draw_text_block(text, is_top=True):
            if not text or not text.strip():
                return
            
            text = text.upper()
            
            # Получаем размер шрифта
            font_size = get_font_size(img.width)
            
            try:
                current_font = ImageFont.truetype(FONT_PATH, font_size)
            except:
                current_font = ImageFont.load_default()
            
            # Разбиваем на строки
            words = text.split()
            if not words:
                return
            
            lines = []
            current_line = words[0]
            
            for word in words[1:]:
                test_line = current_line + " " + word
                test_width = draw.textlength(test_line, font=current_font)
                
                if test_width <= max_text_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            lines.append(current_line)
            
            # Высота строки
            line_height = font_size + 5
            total_height = len(lines) * line_height
            
            # Жесткие отступы от краев (чтобы не закрывать картинку)
            top_margin = int(img.height * 0.05)  # 5% от высоты сверху
            bottom_margin = int(img.height * 0.05)  # 5% от высоты снизу
            
            # Определяем позицию Y
            if is_top:
                y = top_margin
                # Если текст слишком высокий - уменьшаем
                if y + total_height > img.height * 0.25:  # Не выше 25% картинки
                    y = top_margin
            else:
                y = img.height - total_height - bottom_margin
                # Если текст слишком высокий - поднимаем
                if y < img.height * 0.75:  # Не ниже 75% картинки
                    y = img.height - total_height - bottom_margin
            
            # Рисуем каждую строку
            for i, line in enumerate(lines):
                # Ширина строки
                line_width = draw.textlength(line, font=current_font)
                
                # Центрируем
                x = (img.width - line_width) // 2
                
                # Y для текущей строки
                line_y = y + (i * line_height)
                
                # Обводка толщиной 2px (совсем тонкая)
                outline_range = 2
                for dx in range(-outline_range, outline_range + 1):
                    for dy in range(-outline_range, outline_range + 1):
                        if dx != 0 or dy != 0:
                            if (dx*dx + dy*dy) <= outline_range*outline_range + 1:
                                try:
                                    draw.text((x + dx, line_y + dy), line, font=current_font, fill='black')
                                except:
                                    pass
                
                # Основной текст
                try:
                    draw.text((x, line_y), line, font=current_font, fill='white')
                except:
                    pass
        
        # Рисуем верхний текст
        if top_text and top_text.strip():
            draw_text_block(top_text, is_top=True)
            logger.info(f"✅ Верхний текст нарисован")
        
        # Рисуем нижний текст
        if bottom_text and bottom_text.strip():
            draw_text_block(bottom_text, is_top=False)
            logger.info(f"✅ Нижний текст нарисован")
        
        # Добавляем водяной знак
        add_watermark(draw, img.width, img.height)
        
        # Сохраняем
        output = BytesIO()
        img_with_text.save(output, format='PNG', optimize=True)
        output.seek(0)
        
        logger.info("✅ Мем успешно создан")
        return output
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        logger.error(traceback.format_exc())
        raise e

# ============= ВСЕ ОБРАБОТЧИКИ (без изменений) =============
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} запустил бота")
    
    # Проверяем подписку
    is_subscribed = await check_subscription(bot, user_id, CHANNEL_ID)
    
    if is_subscribed:
        await message.answer(
            "👋 Привет! Я бот для создания мемов.\n\n"
            "📝 Как пользоваться:\n"
            "1. Отправь мне картинку\n"
            "2. Напиши текст для верхней части (можно пропустить)\n"
            "3. Напиши текст для нижней части (можно пропустить)\n\n"
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
    logger.info(f"Пользователь {user_id} отправил фото")
    
    # Проверяем подписку
    is_subscribed = await check_subscription(bot, user_id, CHANNEL_ID)
    
    if not is_subscribed:
        keyboard = get_subscription_keyboard(CHANNEL_ID)
        await message.answer(
            "❌ Чтобы пользоваться ботом, нужно подписаться на канал @shtoporch",
            reply_markup=keyboard
        )
        return
    
    try:
        # Получаем фото максимального размера
        photo = message.photo[-1]
        
        # Скачиваем фото
        file_info = await bot.get_file(photo.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        image_bytes = downloaded_file.getvalue()
        
        logger.info(f"✅ Фото скачано, размер: {len(image_bytes)} байт")
        
        # Сохраняем фото во временное хранилище
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
    """Пропустить ввод текста"""
    user_id = message.from_user.id
    
    if user_id not in user_data:
        await message.answer("❌ Сначала отправь картинку!")
        return
    
    current_stage = user_data[user_id].get('stage')
    
    if current_stage == 'waiting_top_text':
        # Пропускаем верхний текст
        user_data[user_id]['top_text'] = ''
        user_data[user_id]['stage'] = 'waiting_bottom_text'
        await message.answer(
            "📝 Теперь напиши текст для НИЖНЕЙ части мема\n"
            "(или отправь /skip чтобы пропустить, или /cancel чтобы отменить)"
        )
    elif current_stage == 'waiting_bottom_text':
        # Пропускаем нижний текст и создаем мем
        await create_meme_from_data(user_id, '', message)
    else:
        await message.answer("❌ Непонятная команда. Напиши /cancel и начни заново.")

@dp.message_handler(commands=['cancel'])
async def cancel_command(message: types.Message):
    """Отмена создания мема"""
    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]
        await message.answer("✅ Создание мема отменено. Можешь начать заново с отправки картинки.")
    else:
        await message.answer("🤷 Нет активного процесса создания мема.")

async def create_meme_from_data(user_id, bottom_text, message):
    """Создает мем из данных пользователя"""
    top_text = user_data[user_id].get('top_text', '')
    image_bytes = user_data[user_id].get('image')
    
    if not image_bytes:
        await message.answer("❌ Что-то пошло не так. Начни заново с отправки картинки.")
        del user_data[user_id]
        return
    
    # Отправляем сообщение о начале обработки
    processing_msg = await message.answer("🔄 Создаю мем... (это может занять несколько секунд)")
    
    try:
        # Создаем мем
        logger.info(f"Начинаю создание мема для пользователя {user_id}")
        logger.info(f"Верхний текст: '{top_text}', Нижний текст: '{bottom_text}'")
        
        meme_image = create_meme_image(image_bytes, top_text, bottom_text)
        
        # Отправляем результат
        await message.answer_photo(
            photo=meme_image,
            caption="🎉 Твой мем готов!\n\nСоздай новый - отправь ещё картинку!"
        )
        logger.info(f"✅ Мем отправлен пользователю {user_id}")
        
        # Удаляем сообщение о обработке
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания мема для пользователя {user_id}: {e}")
        logger.error(traceback.format_exc())
        await message.answer(
            "❌ Не удалось создать мем.\n"
            "Возможные причины:\n"
            "• Слишком большая картинка\n"
            "• Неподдерживаемый формат\n"
            "• Проблема со шрифтом\n\n"
            "Попробуй другую картинку или напиши /start"
        )
    
    # Очищаем данные пользователя
    del user_data[user_id]

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
            "❌ Сначала отправь картинку!\n"
            "Или напиши /start чтобы начать"
        )
        return
    
    current_stage = user_data[user_id].get('stage')
    
    if current_stage == 'waiting_top_text':
        # Сохраняем верхний текст и ждем нижний
        if len(message.text) > 200:
            await message.answer("❌ Текст слишком длинный! Максимум 200 символов.")
            return
            
        user_data[user_id]['top_text'] = message.text
        user_data[user_id]['stage'] = 'waiting_bottom_text'
        await message.answer(
            "📝 Теперь напиши текст для НИЖНЕЙ части мема\n"
            "(или отправь /skip чтобы пропустить, или /cancel чтобы отменить)"
        )
        logger.info(f"Пользователь {user_id} ввел верхний текст: {message.text[:30]}...")
        
    elif current_stage == 'waiting_bottom_text':
        # Получаем нижний текст и создаем мем
        if len(message.text) > 200:
            await message.answer("❌ Текст слишком длинный! Максимум 200 символов.")
            return
        
        await create_meme_from_data(user_id, message.text, message)

async def handle_health(request):
    """Обработчик для проверки здоровья"""
    return web.Response(text="Бот работает!")

async def run_web_server():
    """Запускает веб-сервер на порту 10000"""
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
    """Основная функция запуска бота"""
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
