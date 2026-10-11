"""
Management команда для настройки Telegram webhook.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import requests
import logging

logger = logging.getLogger(__name__)

# Проверка доступности библиотеки (не критично для этой команды, но для информации)
try:
    from telegram import Update
    TELEGRAM_BOT_AVAILABLE = True
except ImportError:
    TELEGRAM_BOT_AVAILABLE = False


class Command(BaseCommand):
    help = 'Настройка Telegram webhook'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='URL для webhook (по умолчанию берется из ALLOWED_HOSTS)',
        )
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Удалить webhook (установить пустой URL)',
        )

    def handle(self, *args, **options):
        if not TELEGRAM_BOT_AVAILABLE:
            self.stdout.write(
                self.style.WARNING('⚠️  python-telegram-bot не установлен, но команда все равно выполнится.')
            )
            self.stdout.write('Для работы интерактивного бота установите: pip install python-telegram-bot')
        
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not bot_token:
            self.stdout.write(
                self.style.ERROR('❌ TELEGRAM_BOT_TOKEN не настроен в settings.py')
            )
            return

        # Удаление webhook
        if options['remove']:
            url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
            data = {'url': ''}
            
            try:
                response = requests.post(url, json=data, timeout=10)
                result = response.json()
                
                if result.get('ok'):
                    self.stdout.write(
                        self.style.SUCCESS('✅ Webhook удален')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Ошибка при удалении webhook: {result.get("description", "Неизвестная ошибка")}')
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Ошибка: {str(e)}')
                )
            return

        # Определяем URL для webhook
        if options['url']:
            webhook_url = options['url']
        else:
            # Берем первый домен из ALLOWED_HOSTS
            allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
            if allowed_hosts:
                domain = allowed_hosts[0]
                # Убираем www если есть
                if domain.startswith('www.'):
                    domain = domain[4:]
                # Для продакшена всегда используем HTTPS
                # Для DEBUG режима можно использовать HTTP, но Telegram требует HTTPS
                protocol = 'https'  # Всегда HTTPS для webhook
                # Проверяем, как подключены accounts.urls в project_plan/urls.py
                # Если accounts.urls подключен в корне (path('', include('accounts.urls'))),
                # то путь будет /telegram/webhook/, а не /accounts/telegram/webhook/
                # Проверяем это, пытаясь определить структуру URL
                webhook_url = f"{protocol}://{domain}/telegram/webhook/"
            else:
                self.stdout.write(
                    self.style.ERROR('❌ ALLOWED_HOSTS не настроен. Укажите URL через --url')
                )
                return

        # Показываем, какой URL будет использован
        self.stdout.write(f"🔗 URL для webhook: {webhook_url}")
        
        # Проверяем, что URL использует HTTPS (Telegram требует HTTPS)
        if not webhook_url.startswith('https://'):
            self.stdout.write(
                self.style.WARNING('⚠️  ВНИМАНИЕ: Telegram требует HTTPS для webhook!')
            )
            self.stdout.write(
                self.style.WARNING('   Убедитесь, что ваш сайт доступен по HTTPS.')
            )
        
        # Проверяем доступность URL (опционально)
        self.stdout.write("🔍 Проверка доступности URL...")
        try:
            test_response = requests.get(webhook_url, timeout=5, allow_redirects=True)
            self.stdout.write(f"   Статус ответа: {test_response.status_code}")
            if test_response.status_code == 503:
                self.stdout.write(
                    self.style.WARNING('   ⚠️  URL доступен, но возвращает 503 (библиотека не установлена)')
                )
        except requests.exceptions.RequestException as e:
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  Не удалось проверить доступность URL: {str(e)}')
            )
            self.stdout.write(
                self.style.WARNING('   Убедитесь, что URL доступен из интернета.')
            )
        
        url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
        data = {'url': webhook_url}

        self.stdout.write("\n📤 Отправка запроса в Telegram...")
        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            
            # Показываем полный ответ для отладки
            if not result.get('ok'):
                error_code = result.get('error_code', 'N/A')
                error_description = result.get('description', 'Неизвестная ошибка')
                parameters = result.get('parameters', {})
                
                self.stdout.write(
                    self.style.ERROR(f'\n❌ Ошибка при настройке webhook:')
                )
                self.stdout.write(
                    self.style.ERROR(f'   Код ошибки: {error_code}')
                )
                self.stdout.write(
                    self.style.ERROR(f'   Описание: {error_description}')
                )
                
                if parameters:
                    self.stdout.write(f'   Дополнительные параметры: {parameters}')
                
                # Полезные советы в зависимости от ошибки
                if '400' in str(error_code) or 'Bad Request' in error_description:
                    self.stdout.write(
                        self.style.WARNING('\n💡 Возможные причины:')
                    )
                    self.stdout.write(
                        self.style.WARNING('   1. URL недоступен из интернета')
                    )
                    self.stdout.write(
                        self.style.WARNING('   2. URL не использует HTTPS')
                    )
                    self.stdout.write(
                        self.style.WARNING('   3. Проблемы с SSL сертификатом')
                    )
                    self.stdout.write(
                        self.style.WARNING('   4. Неверный формат URL')
                    )
                    self.stdout.write(
                        self.style.WARNING('\n   Проверьте:')
                    )
                    self.stdout.write(
                        self.style.WARNING(f'   - Доступен ли URL: {webhook_url}')
                    )
                    self.stdout.write(
                        self.style.WARNING('   - Используется ли HTTPS')
                    )
                    self.stdout.write(
                        self.style.WARNING('   - Валиден ли SSL сертификат')
                    )
                
                return
            
            # Успешная настройка
            self.stdout.write(
                self.style.SUCCESS(f'\n✅ Webhook успешно установлен!')
            )
            self.stdout.write(
                self.style.SUCCESS(f'   URL: {webhook_url}')
            )
            
            # Проверяем информацию о webhook
            info_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
            info_response = requests.get(info_url, timeout=10)
            if info_response.json().get('ok'):
                webhook_info = info_response.json().get('result', {})
                pending_count = webhook_info.get('pending_update_count', 0)
                last_error = webhook_info.get('last_error_message')
                last_error_date = webhook_info.get('last_error_date')
                
                self.stdout.write(f"\n📊 Информация о webhook:")
                self.stdout.write(f"   Ожидающих обновлений: {pending_count}")
                
                if last_error:
                    self.stdout.write(
                        self.style.WARNING(f'   Последняя ошибка: {last_error}')
                    )
                    if last_error_date:
                        from datetime import datetime
                        error_time = datetime.fromtimestamp(last_error_date)
                        self.stdout.write(
                            self.style.WARNING(f'   Дата ошибки: {error_time.strftime("%Y-%m-%d %H:%M:%S")}')
                        )
                
        except requests.exceptions.HTTPError as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ HTTP ошибка: {str(e)}')
            )
            if hasattr(e.response, 'text'):
                self.stdout.write(f'   Ответ сервера: {e.response.text[:200]}')
        except requests.exceptions.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Ошибка при настройке webhook: {str(e)}')
            )
        except Exception as e:
            logger.error(f"Ошибка при настройке webhook: {str(e)}", exc_info=True)
            self.stdout.write(
                self.style.ERROR(f'\n❌ Неожиданная ошибка: {str(e)}')
            )
