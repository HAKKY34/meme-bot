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

def create_meme_image(image_bytes: bytes, top_text: str, bottom_text: str) -> BytesIO:
    """
    Создает мем с текстом сверху и снизу (текст по центру, с переносом строк)
    """
    try:
        # Открываем изображение
        img = Image.open(BytesIO(image_bytes)).convert('RGBA')
        logger.info(f"✅ Изображение загружено: размер {img.width}x{img.height}")
        
        # Создаем копию для рисования
        img_with_text = img.copy()
        draw = ImageDraw.Draw(img_with_text)
        
        # Функция для разбиения текста на строки
        def split_text_into_lines(text, font, max_width):
            words = text.upper().split()
            if not words:
                return []
            
            lines = []
            current_line = words[0]
            
            for word in words[1:]:
                # Проверяем ширину с новым словом
                test_line = current_line + " " + word
                test_width = draw.textlength(test_line, font=font)
                
                if test_width <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            
            lines.append(current_line)
            return lines
        
        # Функция для подбора размера шрифта
        def get_best_font_size(text, max_width, max_height, start_size=60):
            if not text:
                return 40
            
            # Пробуем разные размеры шрифта
            for size in range(start_size, 20, -2):
                try:
                    test_font = ImageFont.truetype(FONT_PATH, size)
                    lines = split_text_into_lines(text, test_font, max_width)
                    
                    # Проверяем, помещается ли текст по высоте
                    total_height = len(lines) * (size + 5)
                    if total_height <= max_height:
                        return size
                except:
                    continue
            
            return 20
        
        # Определяем максимальную ширину текста (90% от ширины картинки)
        max_text_width = int(img.width * 0.9)
        max_text_height_top = int(img.height * 0.3)  # 30% высоты для верхнего текста
        max_text_height_bottom = int(img.height * 0.3)  # 30% высоты для нижнего текста
        
        # Определяем размер шрифта для верхнего текста
        if top_text:
            top_font_size = get_best_font_size(top_text, max_text_width, max_text_height_top)
            top_font = ImageFont.truetype(FONT_PATH, top_font_size)
            top_lines = split_text_into_lines(top_text, top_font, max_text_width)
        else:
            top_lines = []
        
        # Определяем размер шрифта для нижнего текста
        if bottom_text:
            bottom_font_size = get_best_font_size(bottom_text, max_text_width, max_text_height_bottom)
            bottom_font = ImageFont.truetype(FONT_PATH, bottom_font_size)
            bottom_lines = split_text_into_lines(bottom_text, bottom_font, max_text_width)
        else:
            bottom_lines = []
        
        # Функция для рисования текста с обводкой
        def draw_text_lines(lines, font, start_y, align_top=True):
            if not lines:
                return
            
            line_height = font.size + 5
            total_height = len(lines) * line_height
            
            # Определяем начальную Y координату
            if align_top:
                y = max(10, start_y)
            else:
                y = img.height - total_height - max(10, start_y)
            
            # Рисуем каждую строку
            for i, line in enumerate(lines):
                # Получаем ширину строки
                line_width = draw.textlength(line, font=font)
                
                # Центрируем по горизонтали
                x = (img.width - line_width) // 2
                
                # Y координата для текущей строки
                line_y = y + (i * line_height)
                
                # Рисуем обводку (черный)
                outline_range = max(2, int(font.size * 0.08))
                for dx in range(-outline_range, outline_range + 1):
                    for dy in range(-outline_range, outline_range + 1):
                        if dx != 0 or dy != 0:
                            try:
                                draw.text((x + dx, line_y + dy), line, font=font, fill='black')
                            except:
                                pass
                
                # Рисуем основной текст (белый)
                try:
                    draw.text((x, line_y), line, font=font, fill='white')
                except Exception as e:
                    logger.error(f"Ошибка при рисовании текста: {e}")
        
        # Рисуем верхний текст
        if top_lines:
            draw_text_lines(top_lines, top_font, 10, align_top=True)
            logger.info(f"✅ Верхний текст нарисован ({len(top_lines)} строк)")
        
        # Рисуем нижний текст
        if bottom_lines:
            draw_text_lines(bottom_lines, bottom_font, 10, align_top=False)
            logger.info(f"✅ Нижний текст нарисован ({len(bottom_lines)} строк)")
        
        # Сохраняем в байты
        output = BytesIO()
        img_with_text.save(output, format='PNG', optimize=True)
        output.seek(0)
        
        logger.info("✅ Мем успешно создан")
        return output
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при создании мема: {e}")
        logger.error(traceback.format_exc())
        raise e

# ============= КОД ДЛЯ RENDER =============
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
    
    # Держим сервер запущенным
    await asyncio.Event().wait()
# ============================================

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
            "2. Напиши текст для верхней части\n"
            "3. Напиши текст для нижней части\n\n"
            "✨ Текст автоматически:\n"
            "• Центрируется\n"
            "• Переносится на новую строку\n"
            "• Не выходит за границы\n\n"
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
            "(или отправь /cancel чтобы отменить)"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке фото: {e}")
        await message.answer("❌ Не удалось обработать фото. Попробуй другую картинку.")

@dp.message_handler(commands=['cancel'])
async def cancel_command(message: types.Message):
    """Отмена создания мема"""
    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]
        await message.answer("✅ Создание мема отменено. Можешь начать заново с отправки картинки.")
    else:
        await message.answer("🤷 Нет активного процесса создания мема.")

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
        if len(message.text) > 200:  # Увеличил лимит, так как текст может быть длинным
            await message.answer("❌ Текст слишком длинный! Максимум 200 символов.")
            return
            
        user_data[user_id]['top_text'] = message.text
        user_data[user_id]['stage'] = 'waiting_bottom_text'
        await message.answer(
            "📝 Теперь напиши текст для НИЖНЕЙ части мема\n"
            "(или отправь /cancel чтобы отменить)"
        )
        logger.info(f"Пользователь {user_id} ввел верхний текст: {message.text[:30]}...")
        
    elif current_stage == 'waiting_bottom_text':
        # Получаем нижний текст и создаем мем
        if len(message.text) > 200:
            await message.answer("❌ Текст слишком длинный! Максимум 200 символов.")
            return
            
        bottom_text = message.text
        top_text = user_data[user_id].get('top_text', '')
        image_bytes = user_data[user_id].get('image')
        
        if not image_bytes or not top_text:
            await message.answer("❌ Что-то пошло не так. Начни заново с отправки картинки.")
            del user_data[user_id]
            return
        
        logger.info(f"Пользователь {user_id} ввел нижний текст: {bottom_text[:30]}...")
        
        # Отправляем сообщение о начале обработки
        processing_msg = await message.answer("🔄 Создаю мем... (это может занять несколько секунд)")
        
        try:
            # Создаем мем
            logger.info(f"Начинаю создание мема для пользователя {user_id}")
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

async def main():
    """Основная функция запуска бота"""
    # Запускаем HTTP сервер для Health Check в фоне
    asyncio.create_task(run_web_server())
    
    # Даем серверу время запуститься
    await asyncio.sleep(2)
    
    # Удаляем вебхук на всякий случай
    await bot.delete_webhook()
    
    # Небольшая пауза после удаления вебхука
    await asyncio.sleep(1)
    
    # Запускаем бота
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
