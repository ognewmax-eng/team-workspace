"""
Сервис для отправки уведомлений через Telegram Bot API.
"""
import logging
from django.conf import settings
from django.contrib.auth import get_user_model

# Безопасный импорт requests
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logging.warning("Модуль 'requests' не установлен. Telegram уведомления будут отключены. Установите: pip install requests")

User = get_user_model()
logger = logging.getLogger(__name__)


class TelegramBotService:
    """
    Сервис для работы с Telegram Bot API.
    """
    
    def __init__(self):
        self.bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
    
    def is_configured(self):
        """Проверка, настроен ли бот."""
        return self.bot_token is not None and self.api_url is not None
    
    def send_message(self, chat_id, message, parse_mode='HTML'):
        """
        Отправка сообщения пользователю в Telegram.
        
        Args:
            chat_id: ID чата пользователя в Telegram
            message: Текст сообщения
            parse_mode: Режим парсинга (HTML или Markdown)
        
        Returns:
            bool: True если сообщение отправлено успешно, False в противном случае
        """
        if not REQUESTS_AVAILABLE:
            logger.warning("Модуль 'requests' не установлен. Установите: pip install requests")
            return False
        
        if not self.is_configured():
            logger.warning("Telegram bot не настроен. Установите TELEGRAM_BOT_TOKEN в settings.py")
            return False
        
        if not chat_id:
            logger.warning(f"Не указан chat_id для отправки сообщения")
            return False
        
        url = f"{self.api_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                logger.info(f"Сообщение успешно отправлено в Telegram (chat_id: {chat_id})")
                return True
            else:
                error_description = result.get('description', 'Неизвестная ошибка')
                logger.error(f"Ошибка отправки сообщения в Telegram: {error_description}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при отправке сообщения в Telegram: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке сообщения в Telegram: {str(e)}")
            return False
    
    def send_notification(self, user, message, task=None):
        """
        Отправка уведомления пользователю в Telegram.
        
        Args:
            user: Объект пользователя Django
            message: Текст уведомления
            task: Связанная задача (опционально)
        
        Returns:
            bool: True если уведомление отправлено успешно
        """
        if not user or not user.telegram_chat_id:
            return False
        
        # Форматируем сообщение с информацией о задаче
        formatted_message = self._format_notification(message, task)
        
        return self.send_message(user.telegram_chat_id, formatted_message)
    
    def _format_notification(self, message, task=None):
        """
        Форматирование уведомления для Telegram.
        
        Args:
            message: Базовое сообщение
            task: Связанная задача (опционально)
        
        Returns:
            str: Отформатированное сообщение
        """
        formatted = f"🔔 <b>Уведомление</b>\n\n{message}"
        
        if task:
            # Добавляем информацию о задаче
            priority_emoji = {
                'low': '🟢',
                'medium': '🟡',
                'high': '🟠',
                'urgent': '🔴'
            }
            priority = priority_emoji.get(task.priority, '⚪')
            
            formatted += f"\n\n📋 <b>Задача:</b> {task.title}"
            formatted += f"\n{priority} <b>Приоритет:</b> {task.get_priority_display()}"
            formatted += f"\n📊 <b>Статус:</b> {task.get_status_display()}"
            
            if task.deadline:
                from django.utils import timezone
                from django.utils.formats import date_format
                deadline_str = date_format(task.deadline, "DATETIME_FORMAT")
                formatted += f"\n⏰ <b>Дедлайн:</b> {deadline_str}"
        
        return formatted
    
    def get_bot_info(self):
        """
        Получение информации о боте.
        
        Returns:
            dict: Информация о боте или None в случае ошибки
        """
        if not REQUESTS_AVAILABLE:
            logger.warning("Модуль 'requests' не установлен. Установите: pip install requests")
            return None
        
        if not self.is_configured():
            return None
        
        url = f"{self.api_url}/getMe"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                return result.get('result')
            else:
                logger.error(f"Ошибка получения информации о боте: {result.get('description')}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении информации о боте: {str(e)}")
            return None


# Глобальный экземпляр сервиса
telegram_service = TelegramBotService()


def send_telegram_notification(user, message, task=None):
    """
    Вспомогательная функция для отправки уведомления в Telegram.
    
    Args:
        user: Пользователь Django
        message: Текст уведомления
        task: Связанная задача (опционально)
    
    Returns:
        bool: True если уведомление отправлено успешно
    """
    return telegram_service.send_notification(user, message, task)
