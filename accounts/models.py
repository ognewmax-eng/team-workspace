"""
Модели для системы аутентификации и управления пользователями.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator


class Department(models.Model):
    """
    Модель отдела учреждения.
    """
    name = models.CharField(
        max_length=200,
        verbose_name='Название отдела',
        unique=True
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание отдела'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    """
    Расширенная модель пользователя с ролями и привязкой к отделам.
    """
    ROLE_CHOICES = [
        ('director', 'Директор'),
        ('head', 'Начальник отдела'),
        ('specialist', 'Специалист'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='specialist',
        verbose_name='Роль'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name='Отдел'
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Номер телефона должен быть в формате: '+999999999'. До 15 цифр."
        )],
        verbose_name='Телефон'
    )
    position = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Должность'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата регистрации'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    telegram_chat_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        verbose_name='Telegram Chat ID',
        help_text='ID чата в Telegram для отправки уведомлений'
    )
    google_calendar_credentials = models.TextField(
        null=True,
        blank=True,
        verbose_name='Google Calendar Credentials',
        help_text='JSON-данные для доступа к Google Calendar API (хранится в зашифрованном виде)'
    )
    google_calendar_enabled = models.BooleanField(
        default=False,
        verbose_name='Синхронизация с Google Calendar',
        help_text='Включить автоматическую синхронизацию с Google Calendar'
    )
    
    # Настройки дизайна
    theme = models.CharField(
        max_length=20,
        choices=[
            ('light', 'Светлая'),
            ('dark', 'Темная'),
            ('auto', 'Автоматически'),
        ],
        default='light',
        verbose_name='Тема оформления',
        help_text='Выберите тему оформления интерфейса'
    )
    primary_color = models.CharField(
        max_length=7,
        default='#2563eb',
        verbose_name='Основной цвет',
        help_text='Основной цвет интерфейса в формате HEX (например, #2563eb)'
    )
    accent_color = models.CharField(
        max_length=7,
        default='#FF6B35',
        verbose_name='Акцентный цвет',
        help_text='Акцентный цвет для выделения элементов в формате HEX (например, #FF6B35)'
    )
    font_size = models.CharField(
        max_length=10,
        choices=[
            ('small', 'Маленький'),
            ('medium', 'Средний'),
            ('large', 'Большой'),
        ],
        default='medium',
        verbose_name='Размер шрифта',
        help_text='Размер шрифта интерфейса'
    )
    compact_mode = models.BooleanField(
        default=False,
        verbose_name='Компактный режим',
        help_text='Уменьшить отступы и размеры элементов для более компактного отображения'
    )
    design_style = models.CharField(
        max_length=20,
        choices=[
            ('modern', 'Современный'),
            ('simple', 'Упрощенный'),
        ],
        default='modern',
        verbose_name='Стиль дизайна',
        help_text='Выберите стиль оформления интерфейса. Упрощенный стиль рекомендуется для новых пользователей.'
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    def is_director(self):
        """Проверка, является ли пользователь директором."""
        return self.role == 'director'

    def is_head(self):
        """Проверка, является ли пользователь начальником отдела."""
        return self.role == 'head'

    def is_specialist(self):
        """Проверка, является ли пользователь специалистом."""
        return self.role == 'specialist'

    def can_manage_department(self, department):
        """
        Проверка, может ли пользователь управлять отделом.
        Директор может управлять всеми отделами, начальник - только своим.
        """
        if self.is_director():
            return True
        if self.is_head() and self.department == department:
            return True
        return False

    def get_unread_notifications_count(self):
        """Получить количество непрочитанных уведомлений."""
        return self.notifications.filter(is_read=False).count()


class UserWorkProfile(models.Model):
    """Optional work information shared with authenticated colleagues."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='work_profile', verbose_name='Сотрудник')
    about = models.TextField(blank=True, max_length=2000, verbose_name='О себе')
    responsibilities = models.TextField(blank=True, max_length=2000, verbose_name='Зоны ответственности')
    skills = models.TextField(blank=True, max_length=1000, verbose_name='Навыки и компетенции')
    projects = models.TextField(blank=True, max_length=1500, verbose_name='Текущие проекты и направления')
    work_schedule = models.CharField(blank=True, max_length=250, verbose_name='Рабочий график')
    workplace = models.CharField(blank=True, max_length=200, verbose_name='Площадка и кабинет')
    contact_preferences = models.CharField(blank=True, max_length=350, verbose_name='Как со мной связаться')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Рабочий профиль'
        verbose_name_plural = 'Рабочие профили'

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class ActivityLog(models.Model):
    """
    Модель для логирования действий пользователей на сайте.
    """
    ACTION_CHOICES = [
        ('view', 'Просмотр'),
        ('create', 'Создание'),
        ('update', 'Обновление'),
        ('delete', 'Удаление'),
        ('login', 'Вход'),
        ('logout', 'Выход'),
        ('download', 'Скачивание'),
        ('upload', 'Загрузка'),
        ('other', 'Другое'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
        verbose_name='Пользователь'
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        default='other',
        verbose_name='Действие'
    )
    content_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Тип объекта',
        help_text='Например: Task, Event, WikiArticle'
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='ID объекта'
    )
    object_repr = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Объект',
        help_text='Строковое представление объекта'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание действия'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP адрес'
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name='User Agent'
    )
    url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='URL'
    )
    method = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='HTTP метод',
        help_text='GET, POST, PUT, DELETE и т.д.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата и время'
    )

    class Meta:
        verbose_name = 'Действие пользователя'
        verbose_name_plural = 'Действия пользователей'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        user_str = self.user.get_full_name() if self.user else 'Анонимный'
        action_str = self.get_action_display()
        obj_str = self.object_repr or f'{self.content_type}#{self.object_id}' if self.content_type else ''
        return f'{user_str} - {action_str} {obj_str}'.strip()

    @classmethod
    def log_action(cls, user=None, action='other', content_type='', object_id=None, 
                   object_repr='', description='', request=None):
        """
        Утилита для логирования действия.
        
        Args:
            user: Пользователь, выполнивший действие
            action: Тип действия (view, create, update, delete и т.д.)
            content_type: Тип объекта (например, 'Task', 'Event')
            object_id: ID объекта
            object_repr: Строковое представление объекта
            description: Описание действия
            request: HTTP запрос (для получения IP, User-Agent, URL)
        """
        ip_address = None
        user_agent = ''
        url = ''
        method = ''
        
        if request:
            # Получаем IP адрес
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            url = request.build_absolute_uri()[:500]  # Ограничиваем длину
            method = request.method
        
        return cls.objects.create(
            user=user if user and user.is_authenticated else None,
            action=action,
            content_type=content_type,
            object_id=object_id,
            object_repr=object_repr,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            url=url,
            method=method
        )


class Notification(models.Model):
    """
    Модель уведомлений для пользователей.
    """
    NOTIFICATION_TYPES = [
        ('task_assigned', 'Вам назначена задача'),
        ('task_comment', 'Новый комментарий к задаче'),
        ('task_status_changed', 'Изменен статус задачи'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Пользователь'
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        verbose_name='Тип уведомления'
    )
    message = models.TextField(
        verbose_name='Сообщение'
    )
    related_task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name='Связанная задача'
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name='Прочитано'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.get_notification_type_display()}'

    def mark_as_read(self):
        """Отметить уведомление как прочитанное."""
        self.is_read = True
        self.save(update_fields=['is_read'])

# Registered here so Django discovers the mailing models without another app.
from .mailing_models import EmailCampaign, EmailDelivery
