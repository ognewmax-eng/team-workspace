"""
Сервис для синхронизации с Google Calendar API.
"""
# ВАЖНО: Импортируем патч ПЕРВЫМ, до любых других импортов
try:
    from . import google_calendar_patch
except ImportError:
    # Если патч не доступен, пытаемся применить его здесь
    try:
        import importlib.metadata
        if not hasattr(importlib.metadata, 'packages_distributions'):
            try:
                import importlib_metadata
                importlib.metadata.packages_distributions = getattr(importlib_metadata, 'packages_distributions', lambda: {})
            except ImportError:
                importlib.metadata.packages_distributions = lambda: {}
    except:
        pass

import json
import logging
import sys
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse

# Безопасный импорт Google API

try:
    # Подавляем предупреждения о версии Python
    import warnings
    warnings.filterwarnings('ignore', category=FutureWarning)
    warnings.filterwarnings('ignore', message='.*packages_distributions.*')
    warnings.filterwarnings('ignore', message='.*non-supported Python version.*')
    
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google.auth.transport.requests import Request
    GOOGLE_API_AVAILABLE = True
except ImportError as e:
    GOOGLE_API_AVAILABLE = False
    Request = None
    logging.warning(f"Google API libraries не установлены: {str(e)}. Установите: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
except (AttributeError, Exception) as e:
    # Если все еще есть ошибки, пытаемся импортировать с полным подавлением предупреждений
    try:
        import warnings
        import sys
        # Полностью подавляем все предупреждения
        warnings.filterwarnings('ignore')
        
        # Пытаемся обойти проблему с packages_distributions
        if 'packages_distributions' in str(e):
            try:
                import importlib_metadata
                import importlib.metadata
                if not hasattr(importlib.metadata, 'packages_distributions'):
                    importlib.metadata.packages_distributions = lambda: {}
            except:
                pass
        
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from google.auth.transport.requests import Request
        GOOGLE_API_AVAILABLE = True
        logging.warning(f"Google API импортирован с обходом ошибки: {str(e)}")
    except Exception as import_error:
        GOOGLE_API_AVAILABLE = False
        Request = None
        logging.error(f"Не удалось импортировать Google API: {str(import_error)}. Установите: pip install --upgrade importlib-metadata>=4.0.0")

User = get_user_model()
logger = logging.getLogger(__name__)


class GoogleCalendarService:
    """
    Сервис для работы с Google Calendar API.
    """
    
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    REDIRECT_URI = None  # Будет установлен в настройках
    
    def __init__(self, user):
        """
        Инициализация сервиса для конкретного пользователя.
        
        Args:
            user: Объект пользователя Django
        """
        self.user = user
        self.credentials = None
        self.service = None
        self._load_credentials()
    
    def _load_credentials(self):
        """Загрузка credentials пользователя из базы данных."""
        if not GOOGLE_API_AVAILABLE:
            return
        
        if not self.user.google_calendar_credentials:
            return
        
        try:
            creds_data = json.loads(self.user.google_calendar_credentials)
            self.credentials = Credentials.from_authorized_user_info(creds_data, self.SCOPES)
            
            # Проверяем, нужно ли обновить токен
            if self.credentials.expired and self.credentials.refresh_token and Request:
                self.credentials.refresh(Request())
                self._save_credentials()
            
            # Создаем сервис для работы с API
            self.service = build('calendar', 'v3', credentials=self.credentials)
        except Exception as e:
            logger.error(f"Ошибка загрузки Google Calendar credentials для пользователя {self.user.username}: {str(e)}")
            self.credentials = None
            self.service = None
    
    def _save_credentials(self):
        """Сохранение credentials пользователя в базу данных."""
        if self.credentials:
            try:
                creds_dict = {
                    'token': self.credentials.token,
                    'refresh_token': self.credentials.refresh_token,
                    'token_uri': self.credentials.token_uri,
                    'client_id': self.credentials.client_id,
                    'client_secret': self.credentials.client_secret,
                    'scopes': self.credentials.scopes,
                }
                self.user.google_calendar_credentials = json.dumps(creds_dict)
                self.user.save(update_fields=['google_calendar_credentials'])
            except Exception as e:
                logger.error(f"Ошибка сохранения Google Calendar credentials: {str(e)}")
    
    def is_authenticated(self):
        """Проверка, авторизован ли пользователь в Google Calendar."""
        return self.service is not None and self.credentials is not None
    
    def get_authorization_url(self, request):
        """
        Получение URL для авторизации пользователя.
        
        Args:
            request: Django request объект
        
        Returns:
            str: URL для авторизации
        """
        if not GOOGLE_API_AVAILABLE:
            return None
        
        client_id = getattr(settings, 'GOOGLE_CALENDAR_CLIENT_ID', None)
        client_secret = getattr(settings, 'GOOGLE_CALENDAR_CLIENT_SECRET', None)
        
        if not client_id or not client_secret:
            logger.warning("Google Calendar credentials не настроены в settings.py")
            return None
        
        # Получаем redirect URI
        # Явно указываем путь, чтобы избежать конфликтов с дублированием URLs
        redirect_uri = request.build_absolute_uri('/google-calendar/callback/')
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=self.SCOPES,
            redirect_uri=redirect_uri
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # Сохраняем state и конфигурацию в сессии
        # Используем ручное сохранение вместо to_json() для совместимости со старыми версиями
        request.session['google_calendar_state'] = state
        request.session['google_calendar_client_config'] = {
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
        }
        request.session['google_calendar_scopes'] = self.SCOPES
        
        return authorization_url
    
    def handle_callback(self, request, code):
        """
        Обработка callback от Google OAuth.
        
        Args:
            request: Django request объект
            code: Код авторизации от Google
        
        Returns:
            bool: True если авторизация успешна
        """
        if not GOOGLE_API_AVAILABLE:
            return False
        
        try:
            state = request.session.get('google_calendar_state')
            client_config = request.session.get('google_calendar_client_config')
            scopes = request.session.get('google_calendar_scopes', self.SCOPES)
            redirect_uri = client_config.get('redirect_uri') if client_config else None
            
            if not state or not client_config or not redirect_uri:
                logger.error("Отсутствует state или конфигурация в сессии")
                return False
            
            # Восстанавливаем flow из сохраненной конфигурации
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": client_config['client_id'],
                        "client_secret": client_config['client_secret'],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [redirect_uri]
                    }
                },
                scopes=scopes,
                redirect_uri=redirect_uri
            )
            flow.fetch_token(code=code)
            
            self.credentials = flow.credentials
            self._save_credentials()
            
            # Создаем сервис
            self.service = build('calendar', 'v3', credentials=self.credentials)
            
            # Включаем синхронизацию для пользователя
            self.user.google_calendar_enabled = True
            self.user.save(update_fields=['google_calendar_enabled'])
            
            # Очищаем сессию
            request.session.pop('google_calendar_state', None)
            request.session.pop('google_calendar_client_config', None)
            request.session.pop('google_calendar_scopes', None)
            
            return True
        except Exception as e:
            logger.error(f"Ошибка обработки Google Calendar callback: {str(e)}")
            return False
    
    def create_event(self, title, description, start_time, end_time, location=None, attendees=None):
        """
        Создание события в Google Calendar.
        
        Args:
            title: Название события
            description: Описание события
            start_time: Время начала (datetime)
            end_time: Время окончания (datetime)
            location: Место проведения (опционально)
            attendees: Список email адресов участников (опционально)
        
        Returns:
            str: ID созданного события или None в случае ошибки
        """
        if not self.is_authenticated():
            logger.warning(f"Пользователь {self.user.username} не авторизован в Google Calendar")
            return None
        
        try:
            event = {
                'summary': title,
                'description': description or '',
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': str(timezone.get_current_timezone()),
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': str(timezone.get_current_timezone()),
                },
            }
            
            if location:
                event['location'] = location
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            created_event = self.service.events().insert(calendarId='primary', body=event).execute()
            event_id = created_event.get('id')
            
            logger.info(f"Создано событие в Google Calendar: {event_id} для пользователя {self.user.username}")
            return event_id
            
        except HttpError as e:
            logger.error(f"Ошибка создания события в Google Calendar: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании события в Google Calendar: {str(e)}")
            return None
    
    def update_event(self, event_id, title, description, start_time, end_time, location=None, attendees=None):
        """
        Обновление события в Google Calendar.
        
        Args:
            event_id: ID события в Google Calendar
            title: Новое название события
            description: Новое описание события
            start_time: Новое время начала (datetime)
            end_time: Новое время окончания (datetime)
            location: Новое место проведения (опционально)
            attendees: Новый список email адресов участников (опционально)
        
        Returns:
            bool: True если обновление успешно
        """
        if not self.is_authenticated():
            logger.warning(f"Пользователь {self.user.username} не авторизован в Google Calendar")
            return False
        
        try:
            # Получаем существующее событие
            event = self.service.events().get(calendarId='primary', eventId=event_id).execute()
            
            # Обновляем данные
            event['summary'] = title
            event['description'] = description or ''
            event['start'] = {
                'dateTime': start_time.isoformat(),
                'timeZone': str(timezone.get_current_timezone()),
            }
            event['end'] = {
                'dateTime': end_time.isoformat(),
                'timeZone': str(timezone.get_current_timezone()),
            }
            
            if location:
                event['location'] = location
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            self.service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            
            logger.info(f"Обновлено событие в Google Calendar: {event_id} для пользователя {self.user.username}")
            return True
            
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"Событие {event_id} не найдено в Google Calendar, создаем новое")
                # Создаем новое событие, если старое было удалено
                new_event_id = self.create_event(title, description, start_time, end_time, location, attendees)
                return new_event_id is not None
            logger.error(f"Ошибка обновления события в Google Calendar: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при обновлении события в Google Calendar: {str(e)}")
            return False
    
    def delete_event(self, event_id):
        """
        Удаление события из Google Calendar.
        
        Args:
            event_id: ID события в Google Calendar
        
        Returns:
            bool: True если удаление успешно
        """
        if not self.is_authenticated():
            logger.warning(f"Пользователь {self.user.username} не авторизован в Google Calendar")
            return False
        
        try:
            self.service.events().delete(calendarId='primary', eventId=event_id).execute()
            logger.info(f"Удалено событие из Google Calendar: {event_id} для пользователя {self.user.username}")
            return True
        except HttpError as e:
            if e.resp.status == 404:
                # Событие уже удалено, считаем успешным
                logger.info(f"Событие {event_id} уже удалено из Google Calendar")
                return True
            logger.error(f"Ошибка удаления события из Google Calendar: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при удалении события из Google Calendar: {str(e)}")
            return False
    
    def disconnect(self):
        """Отключение синхронизации с Google Calendar."""
        self.user.google_calendar_enabled = False
        self.user.google_calendar_credentials = None
        self.user.save(update_fields=['google_calendar_enabled', 'google_calendar_credentials'])
        self.credentials = None
        self.service = None


# Вспомогательные функции для синхронизации задач и событий

def sync_task_to_google_calendar(task, user=None):
    """
    Синхронизация задачи с Google Calendar.
    
    Args:
        task: Объект Task
        user: Пользователь, для которого синхронизировать (по умолчанию - исполнитель задачи)
    
    Returns:
        bool: True если синхронизация успешна
    """
    if not GOOGLE_API_AVAILABLE:
        return False
    
    # Определяем пользователя для синхронизации
    # Если не указан конкретный пользователь, синхронизируем для первого исполнителя
    if not user:
        assignees = list(task.assigned_to.all())
        if not assignees:
            return False
        user = assignees[0]
    
    if not user or not user.google_calendar_enabled:
        return False
    
    # Если нет дедлайна, не создаем событие
    if not task.deadline:
        return False
    
    service = GoogleCalendarService(user)
    if not service.is_authenticated():
        return False
    
    # Формируем описание
    description = f"Задача: {task.title}\n"
    if task.description:
        description += f"\n{task.description}\n"
    description += f"\nСтатус: {task.get_status_display()}\n"
    description += f"Приоритет: {task.get_priority_display()}\n"
    if task.department:
        description += f"Отдел: {task.department.name}\n"
    
    # URL задачи
    from django.urls import reverse
    task_url = reverse('task_detail', args=[task.id])
    description += f"\nСсылка: {task_url}"
    
    # Время начала - за час до дедлайна (или текущее время, если дедлайн близко)
    start_time = task.deadline - timedelta(hours=1)
    if start_time < timezone.now():
        start_time = timezone.now()
    
    end_time = task.deadline
    
    # Список участников (email создателя, если есть)
    attendees = []
    if task.created_by and task.created_by.email:
        attendees.append(task.created_by.email)
    
    try:
        if task.google_calendar_event_id:
            # Обновляем существующее событие
            success = service.update_event(
                task.google_calendar_event_id,
                f"📋 {task.title}",
                description,
                start_time,
                end_time,
                attendees=attendees if attendees else None
            )
            if not success:
                # Если обновление не удалось, создаем новое событие
                event_id = service.create_event(
                    f"📋 {task.title}",
                    description,
                    start_time,
                    end_time,
                    attendees=attendees if attendees else None
                )
                if event_id:
                    task.google_calendar_event_id = event_id
                    task.save(update_fields=['google_calendar_event_id'])
                    return True
        else:
            # Создаем новое событие
            event_id = service.create_event(
                f"📋 {task.title}",
                description,
                start_time,
                end_time,
                attendees=attendees if attendees else None
            )
            if event_id:
                task.google_calendar_event_id = event_id
                task.save(update_fields=['google_calendar_event_id'])
                return True
        
        return False
    except Exception as e:
        logger.error(f"Ошибка синхронизации задачи {task.id} с Google Calendar: {str(e)}")
        return False


def sync_schedule_event_to_google_calendar(schedule_event, user=None):
    """
    Синхронизация события расписания с Google Calendar.
    
    Args:
        schedule_event: Объект ScheduleEvent
        user: Пользователь, для которого синхронизировать (по умолчанию - создатель события)
    
    Returns:
        bool: True если синхронизация успешна
    """
    if not GOOGLE_API_AVAILABLE:
        return False
    
    # Определяем пользователя для синхронизации
    if not user:
        user = schedule_event.created_by
    
    if not user or not user.google_calendar_enabled:
        return False
    
    service = GoogleCalendarService(user)
    if not service.is_authenticated():
        return False
    
    # Формируем описание
    description = schedule_event.description or ''
    description += f"\n\nТип: {schedule_event.get_event_type_display()}\n"
    if schedule_event.department:
        description += f"Отдел: {schedule_event.department.name}\n"
    
    # URL события
    from django.urls import reverse
    event_url = reverse('schedule_event_detail', args=[schedule_event.id])
    description += f"\nСсылка: {event_url}"
    
    # Список участников (email участников)
    attendees = []
    for participant in schedule_event.participants.all():
        if participant.email:
            attendees.append(participant.email)
    
    try:
        if schedule_event.google_calendar_event_id:
            # Обновляем существующее событие
            success = service.update_event(
                schedule_event.google_calendar_event_id,
                schedule_event.title,
                description,
                schedule_event.start_time,
                schedule_event.end_time,
                location=schedule_event.location or None,
                attendees=attendees if attendees else None
            )
            if not success:
                # Если обновление не удалось, создаем новое событие
                event_id = service.create_event(
                    schedule_event.title,
                    description,
                    schedule_event.start_time,
                    schedule_event.end_time,
                    location=schedule_event.location or None,
                    attendees=attendees if attendees else None
                )
                if event_id:
                    schedule_event.google_calendar_event_id = event_id
                    schedule_event.save(update_fields=['google_calendar_event_id'])
                    return True
        else:
            # Создаем новое событие
            event_id = service.create_event(
                schedule_event.title,
                description,
                schedule_event.start_time,
                schedule_event.end_time,
                location=schedule_event.location or None,
                attendees=attendees if attendees else None
            )
            if event_id:
                schedule_event.google_calendar_event_id = event_id
                schedule_event.save(update_fields=['google_calendar_event_id'])
                return True
        
        return False
    except Exception as e:
        logger.error(f"Ошибка синхронизации события {schedule_event.id} с Google Calendar: {str(e)}")
        return False


def delete_task_from_google_calendar(task, user=None):
    """
    Удаление задачи из Google Calendar.
    
    Args:
        task: Объект Task
        user: Пользователь, для которого удалить (по умолчанию - исполнитель задачи)
    
    Returns:
        bool: True если удаление успешно
    """
    if not GOOGLE_API_AVAILABLE or not task.google_calendar_event_id:
        return False
    
    if not user:
        user = task.assigned_to.first()

    if not user or not user.google_calendar_enabled:
        return False
    
    service = GoogleCalendarService(user)
    if not service.is_authenticated():
        return False
    
    success = service.delete_event(task.google_calendar_event_id)
    if success:
        task.google_calendar_event_id = None
        task.save(update_fields=['google_calendar_event_id'])
    
    return success


def delete_schedule_event_from_google_calendar(schedule_event, user=None):
    """
    Удаление события расписания из Google Calendar.
    
    Args:
        schedule_event: Объект ScheduleEvent
        user: Пользователь, для которого удалить (по умолчанию - создатель события)
    
    Returns:
        bool: True если удаление успешно
    """
    if not GOOGLE_API_AVAILABLE or not schedule_event.google_calendar_event_id:
        return False
    
    if not user:
        user = schedule_event.created_by
    
    if not user or not user.google_calendar_enabled:
        return False
    
    service = GoogleCalendarService(user)
    if not service.is_authenticated():
        return False
    
    success = service.delete_event(schedule_event.google_calendar_event_id)
    if success:
        schedule_event.google_calendar_event_id = None
        schedule_event.save(update_fields=['google_calendar_event_id'])
    
    return success
