from aiogram import types
from aiogram.types import ChatMemberStatus
import logging

async def check_subscription(bot, user_id: int, channel_id: str) -> bool:
    """Проверяет, подписан ли пользователь на канал"""
    try:
        # Пробуем получить статус пользователя в канале
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        
        # Проверяем, является ли пользователь участником
        if member.status in [ChatMemberStatus.MEMBER, 
                           ChatMemberStatus.CREATOR, 
                           ChatMemberStatus.ADMINISTRATOR]:
            return True
        else:
            return False
            
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        # Если ошибка - считаем что не подписан
        return False

def get_subscription_keyboard(channel_id: str):
    """Создает клавиатуру с кнопкой подписки"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    channel_link = channel_id.replace('@', 'https://t.me/')
    subscribe_btn = types.InlineKeyboardButton(
        text="📢 Подписаться на канал", 
        url=channel_link
    )
    check_btn = types.InlineKeyboardButton(
        text="✅ Я подписался", 
        callback_data="check_sub"
    )
    keyboard.add(subscribe_btn, check_btn)
    return keyboard
