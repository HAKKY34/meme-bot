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
        
        # Функция для разбиения текста на 2 строки с подбором размера
        def split_into_two_lines(text, max_width, start_font_size):
            if not text:
                return [], start_font_size
            
            words = text.upper().split()
            if len(words) == 1:
                return [words[0]], start_font_size
            
            # Пробуем разные размеры шрифта, чтобы получить 2 строки
            for font_size in range(start_font_size, 30, -2):
                try:
                    test_font = ImageFont.truetype(FONT_PATH, font_size)
                except:
                    test_font = ImageFont.load_default()
                
                # Пробуем разные варианты разбиения на 2 строки
                best_lines = None
                best_diff = float('inf')
                
                # Пробуем разбить после каждого слова
                for i in range(1, len(words)):
                    line1 = " ".join(words[:i])
                    line2 = " ".join(words[i:])
                    
                    # Проверяем ширину каждой строки
                    w1 = draw.textlength(line1, font=test_font)
                    w2 = draw.textlength(line2, font=test_font)
                    
                    if w1 <= max_width and w2 <= max_width:
                        # Обе строки помещаются - идеально
                        return [line1, line2], font_size
                    elif w1 <= max_width or w2 <= max_width:
                        # Хотя бы одна помещается - считаем разницу
                        diff = abs(w1 - w2)
                        if diff < best_diff:
                            best_diff = diff
                            best_lines = [line1, line2]
                
                # Если нашли подходящее разбиение на этом размере
                if best_lines:
                    return best_lines, font_size
            
            # Если ничего не подошло, берем первый вариант с минимальным размером
            mid = len(words) // 2
            return [" ".join(words[:mid]), " ".join(words[mid:])], 30
        
        # Определяем базовый размер шрифта (чуть меньше, чтобы точно влезло)
        base_font_size = int(img.width * 0.09)
        base_font_size = max(40, min(100, base_font_size))
        
        # Максимальная ширина текста
        max_text_width = int(img.width * 0.85)
        
        # Обрабатываем верхний текст
        top_lines = []
        top_font_size = base_font_size
        if top_text and top_text.strip():
            top_lines, top_font_size = split_into_two_lines(top_text, max_text_width, base_font_size)
            logger.info(f"📏 Верхний текст: размер {top_font_size}px, {len(top_lines)} строк")
        
        # Обрабатываем нижний текст
        bottom_lines = []
        bottom_font_size = base_font_size
        if bottom_text and bottom_text.strip():
            bottom_lines, bottom_font_size = split_into_two_lines(bottom_text, max_text_width, base_font_size)
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
        top_offset = int(img.height * 0.03)
        bottom_offset = int(img.height * 0.03)
        
        # Рисуем верхний текст
        if top_lines and top_font:
            line_height = top_font_size + 8
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
            line_height = bottom_font_size + 8
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
