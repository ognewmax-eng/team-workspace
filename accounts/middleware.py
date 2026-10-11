"""
Middleware для автоматического логирования действий пользователей.
"""
from django.utils.deprecation import MiddlewareMixin
from .models import ActivityLog
import re


class ActivityLogMiddleware(MiddlewareMixin):
    """
    Middleware для автоматического логирования HTTP запросов.
    """
    # URL-паттерны, которые не нужно логировать
    EXCLUDED_PATHS = [
        r'^/static/',
        r'^/media/',
        r'^/admin/jsi18n/',
        r'^/favicon\.ico',
        r'^/__debug__/',
    ]
    
    # HTTP методы, которые нужно логировать
    LOGGED_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
    
    # URL-паттерны для определения типа действия
    ACTION_PATTERNS = {
        r'/create/': 'create',
        r'/add/': 'create',
        r'/update/': 'update',
        r'/edit/': 'update',
        r'/delete/': 'delete',
        r'/remove/': 'delete',
        r'/download/': 'download',
        r'/upload/': 'upload',
    }
    
    def process_response(self, request, response):
        """
        Обрабатывает ответ и логирует действие, если необходимо.
        """
        # Пропускаем исключенные пути
        if self._should_exclude_path(request.path):
            return response
        
        # Логируем только определенные методы и успешные ответы
        if request.method in self.LOGGED_METHODS and 200 <= response.status_code < 400:
            # Определяем тип действия по URL
            action = self._detect_action(request.path, request.method)
            
            # Определяем тип контента по URL
            content_type = self._detect_content_type(request.path)
            
            # Получаем информацию об объекте из URL
            object_id = self._extract_object_id(request.path)
            
            # Формируем описание
            description = self._build_description(request, action, content_type)
            
            # Логируем действие
            try:
                ActivityLog.log_action(
                    user=request.user if hasattr(request, 'user') else None,
                    action=action,
                    content_type=content_type,
                    object_id=object_id,
                    object_repr=self._get_object_repr(content_type, object_id),
                    description=description,
                    request=request
                )
            except Exception:
                # Игнорируем ошибки логирования, чтобы не нарушить работу сайта
                pass
        
        return response
    
    def _should_exclude_path(self, path):
        """Проверяет, нужно ли исключить путь из логирования."""
        for pattern in self.EXCLUDED_PATHS:
            if re.match(pattern, path):
                return True
        return False
    
    def _detect_action(self, path, method):
        """Определяет тип действия по URL и методу."""
        # Проверяем паттерны в URL
        for pattern, action in self.ACTION_PATTERNS.items():
            if pattern in path:
                return action
        
        # Определяем по методу
        method_actions = {
            'POST': 'create',
            'PUT': 'update',
            'PATCH': 'update',
            'DELETE': 'delete',
        }
        return method_actions.get(method, 'other')
    
    def _detect_content_type(self, path):
        """Определяет тип контента по URL."""
        # Извлекаем название приложения и модели из URL
        path_parts = [p for p in path.split('/') if p]
        
        if len(path_parts) >= 1:
            app_name = path_parts[0]
            # Маппинг названий приложений на модели
            app_to_model = {
                'tasks': 'Task',
                'events': 'Event',
                'wiki': 'WikiArticle',
                'schedule': 'ScheduleEvent',
                'accounts': 'User',
            }
            return app_to_model.get(app_name, '')
        
        return ''
    
    def _extract_object_id(self, path):
        """Извлекает ID объекта из URL."""
        # Ищем числовые значения в URL
        path_parts = [p for p in path.split('/') if p]
        for part in path_parts:
            if part.isdigit():
                return int(part)
        return None
    
    def _get_object_repr(self, content_type, object_id):
        """Получает строковое представление объекта."""
        if not content_type or not object_id:
            return ''
        
        try:
            # Импортируем модель по названию
            # Оптимизация: используем только() для загрузки минимальных полей
            if content_type == 'Task':
                from tasks.models import Task
                obj = Task.objects.only('title', 'id').filter(id=object_id).first()
            elif content_type == 'WikiArticle':
                from wiki.models import WikiArticle
                obj = WikiArticle.objects.only('title', 'id').filter(id=object_id).first()
            elif content_type == 'ScheduleEvent':
                from schedule.models import ScheduleEvent
                obj = ScheduleEvent.objects.only('title', 'id').filter(id=object_id).first()
            elif content_type == 'User':
                from accounts.models import User
                obj = User.objects.only('username', 'first_name', 'last_name', 'id').filter(id=object_id).first()
            else:
                return ''
            
            if obj:
                return str(obj)
        except Exception:
            # Игнорируем ошибки, чтобы не нарушить работу сайта
            pass
        
        return ''
    
    def _build_description(self, request, action, content_type):
        """Формирует описание действия."""
        parts = []
        
        if content_type:
            parts.append(content_type)
        
        action_names = {
            'create': 'создан',
            'update': 'обновлен',
            'delete': 'удален',
            'download': 'скачан',
            'upload': 'загружен',
        }
        parts.append(action_names.get(action, action))
        
        return ' '.join(parts) if parts else ''
