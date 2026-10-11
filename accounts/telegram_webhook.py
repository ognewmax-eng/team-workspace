"""
Django view для обработки webhook от Telegram.
Версия с глобальным event loop и общим Application.
"""
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import logging
import asyncio
import threading
import time

# Безопасный импорт telegram библиотеки
try:
    from telegram import Update
    from telegram.error import NetworkError
    from accounts.telegram_bot_handler import TelegramBotHandler
    TELEGRAM_BOT_AVAILABLE = True
except ImportError:
    TELEGRAM_BOT_AVAILABLE = False
    logging.warning("Модуль 'python-telegram-bot' не установлен. Telegram webhook будет недоступен. Установите: pip install python-telegram-bot")

logger = logging.getLogger(__name__)

# Глобальные переменные
_bot_handler = None
_bot_handler_lock = threading.Lock()
_loop = None
_loop_thread = None
_loop_lock = threading.Lock()

def _run_loop(loop):
    """Запуск event loop в отдельном потоке."""
    asyncio.set_event_loop(loop)
    loop.run_forever()

def init_global_loop():
    """Инициализация глобального event loop в отдельном потоке."""
    global _loop, _loop_thread
    
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            # Создаем новый loop
            _loop = asyncio.new_event_loop()
            
            # Запускаем loop в отдельном потоке
            _loop_thread = threading.Thread(
                target=_run_loop,
                args=(_loop,),
                daemon=True,
                name="TelegramBotEventLoop"
            )
            _loop_thread.start()
            
            # Даем время на запуск
            time.sleep(0.1)
            
            logger.info("✅ Глобальный event loop запущен в отдельном потоке")
    
    return _loop

def get_bot_handler():
    """Получение экземпляра обработчика бота с инициализацией в глобальном loop."""
    if not TELEGRAM_BOT_AVAILABLE:
        raise ImportError("python-telegram-bot не установлен. Установите: pip install python-telegram-bot")
    
    global _bot_handler, _loop
    
    with _bot_handler_lock:
        if _bot_handler is None:
            bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
            if not bot_token:
                raise ValueError("TELEGRAM_BOT_TOKEN не настроен в settings.py")
            
            # Инициализируем глобальный loop
            _loop = init_global_loop()
            
            # Создаем обработчик бота
            _bot_handler = TelegramBotHandler(bot_token)
            
            # Инициализируем application в глобальном loop
            if not _bot_handler.application.running:
                logger.debug("Инициализация Application в глобальном loop...")
                
                # Используем run_coroutine_threadsafe для инициализации
                future = asyncio.run_coroutine_threadsafe(
                    _bot_handler.application.initialize(),
                    _loop
                )
                
                try:
                    future.result(timeout=10.0)
                    logger.info("✅ Application инициализирован в глобальном loop")
                except Exception as e:
                    logger.error(f"Ошибка инициализации Application: {str(e)}", exc_info=True)
                    raise
    
    return _bot_handler

def process_update_sync(update_data, bot_handler):
    """Синхронная обработка обновления в глобальном event loop."""
    try:
        # Десериализуем update
        update = Update.de_json(update_data, bot_handler.application.bot)
        
        if update is None:
            raise ValueError("Не удалось десериализовать Update из webhook данных.")
        
        # Получаем глобальный loop
        loop = init_global_loop()
        
        # Используем run_coroutine_threadsafe для выполнения в глобальном loop
        # Это позволяет HTTP клиенту работать в постоянном loop, избегая проблем
        # с закрытием loop во время выполнения HTTP запросов
        future = asyncio.run_coroutine_threadsafe(
            _process_update_async(update, bot_handler),
            loop
        )
        
        # Ждем завершения с таймаутом
        try:
            future.result(timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning("Таймаут обработки обновления (30 секунд)")
            # Все равно считаем успешным, чтобы Telegram не слал повторно
        except Exception as e:
            logger.error(f"Ошибка при обработке обновления: {str(e)}", exc_info=True)
            raise
            
    except Exception as e:
        logger.error(f"Ошибка в process_update_sync: {str(e)}", exc_info=True)
        raise

async def _process_update_async(update, bot_handler):
    """Асинхронная обработка обновления."""
    try:
        # Логируем тип обновления для отладки
        if update.message:
            logger.debug(f"Обрабатываем сообщение: '{update.message.text}' от пользователя {update.effective_user.id}")
        elif update.callback_query:
            logger.debug(f"Обрабатываем callback_query: '{update.callback_query.data}' от пользователя {update.effective_user.id}")
        
        # Обрабатываем обновление
        await bot_handler.application.process_update(update)
        
        logger.debug("process_update завершен успешно")
        
        # Даем время на выполнение HTTP-запросов
        # Глобальный loop не закрывается, поэтому HTTP клиент может
        # спокойно завершить все операции
        await asyncio.sleep(0.5)
        
    except Exception as e:
        logger.error(f"Ошибка в _process_update_async: {str(e)}", exc_info=True)
        raise

@csrf_exempt
def telegram_webhook(request):
    """Обработка webhook от Telegram с использованием глобального event loop."""
    if not TELEGRAM_BOT_AVAILABLE:
        logger.error("python-telegram-bot не установлен. Webhook недоступен.")
        return HttpResponse('Telegram bot library not installed', status=503)
    
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    
    try:
        # Логируем входящий запрос
        logger.info("=" * 80)
        logger.info("Получен webhook запрос от Telegram")
        
        # Парсим данные
        try:
            update_data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {str(e)}")
            return HttpResponse('Invalid JSON', status=400)
        
        # Логируем тип обновления
        update_id = update_data.get('update_id')
        if 'message' in update_data:
            user_id = update_data.get('message', {}).get('from', {}).get('id')
            text = update_data.get('message', {}).get('text', '')
            logger.info(f"Обновление {update_id}: сообщение от пользователя {user_id}: {text[:100]}")
        elif 'callback_query' in update_data:
            user_id = update_data.get('callback_query', {}).get('from', {}).get('id')
            data = update_data.get('callback_query', {}).get('data', '')
            logger.info(f"Обновление {update_id}: callback query от пользователя {user_id}: {data[:100]}")
        else:
            logger.info(f"Обновление {update_id}: тип {list(update_data.keys())}")
        
        # Получаем обработчик бота
        bot_handler = get_bot_handler()
        
        # Обрабатываем обновление
        try:
            process_update_sync(update_data, bot_handler)
            logger.info(f"✅ Webhook {update_id} обработан успешно")
        except NetworkError as e:
            # Если это ошибка сети из-за закрытия loop, логируем но считаем успешным
            if "Event loop is closed" in str(e):
                logger.warning(f"⚠️  HTTP запросы не завершились полностью для обновления {update_id}")
                logger.info(f"✅ Webhook {update_id} обработан (HTTP запросы в фоне)")
            else:
                logger.error(f"❌ Ошибка сети при обработке webhook {update_id}: {str(e)}", exc_info=True)
                # Все равно возвращаем OK, чтобы Telegram не слал повторно
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке webhook {update_id}: {str(e)}", exc_info=True)
            # Все равно возвращаем OK, чтобы Telegram не слал повторно
        
        logger.info("=" * 80)
        return HttpResponse('OK')
        
    except ImportError as e:
        logger.error(f"Ошибка импорта: {str(e)}", exc_info=True)
        return HttpResponse('Telegram bot library not installed', status=503)
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {str(e)}", exc_info=True)
        return HttpResponse('Configuration error', status=500)
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
        return HttpResponse('OK')  # Всегда возвращаем OK для Telegram
