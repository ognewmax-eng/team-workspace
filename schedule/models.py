"""
Модели для системы расписания и календаря.
"""
from django.db import models
from django.contrib.auth import get_user_model
from accounts.models import Department

User = get_user_model()


class ScheduleEvent(models.Model):
    """
    Модель события в расписании (занятия, мероприятия и т.д.).
    """
    EVENT_TYPE_CHOICES = [
        ('lesson', 'Занятие'),
        ('meeting', 'Встреча'),
        ('event', 'Мероприятие'),
        ('task', 'Задача'),
        ('other', 'Другое'),
    ]

    title = models.CharField(
        max_length=200,
        verbose_name='Название'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default='lesson',
        verbose_name='Тип события'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='schedule_events',
        verbose_name='Отдел'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_events',
        verbose_name='Создал'
    )
    start_time = models.DateTimeField(
        verbose_name='Время начала'
    )
    end_time = models.DateTimeField(
        verbose_name='Время окончания'
    )
    location = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Место проведения'
    )
    participants = models.ManyToManyField(
        User,
        blank=True,
        related_name='participating_events',
        verbose_name='Участники'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    google_calendar_event_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Google Calendar Event ID',
        help_text='ID события в Google Calendar для синхронизации'
    )
    related_task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='schedule_events',
        verbose_name='Связанная задача',
        help_text='Задача, для которой создано это событие расписания'
    )
    related_meropriyatie = models.ForeignKey(
        'events.Meropriyatie',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_events',
        verbose_name='Связанное мероприятие'
    )

    class Meta:
        verbose_name = 'Событие расписания'
        verbose_name_plural = 'События расписания'
        ordering = ['start_time']

    def __str__(self):
        return f'{self.title} ({self.start_time.strftime("%d.%m.%Y %H:%M")})'

    def is_past(self):
        """Проверка, прошло ли событие."""
        from django.utils import timezone
        return timezone.now() > self.end_time

    def is_ongoing(self):
        """Проверка, происходит ли событие сейчас."""
        from django.utils import timezone
        now = timezone.now()
        return self.start_time <= now <= self.end_time


class Association(models.Model):
    """
    Модель объединения (кружок, секция и т.д.).
    """
    name = models.CharField(
        max_length=200,
        verbose_name='Название объединения'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    color = models.CharField(
        max_length=7,
        default='#3b82f6',
        verbose_name='Цвет',
        help_text='Цвет в формате HEX (например, #3b82f6)'
    )
    specialist = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='associations',
        verbose_name='Специалист',
        help_text='Специалист отдела, который ведет это объединение'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='associations',
        verbose_name='Отдел'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активно'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Объединение'
        verbose_name_plural = 'Объединения'
        ordering = ['name']

    def __str__(self):
        return self.name


class Lesson(models.Model):
    """
    Модель занятия в расписании.
    """
    WEEKDAY_CHOICES = [
        (0, 'Понедельник'),
        (1, 'Вторник'),
        (2, 'Среда'),
        (3, 'Четверг'),
        (4, 'Пятница'),
        (5, 'Суббота'),
        (6, 'Воскресенье'),
    ]

    association = models.ForeignKey(
        Association,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name='Объединение'
    )
    weekday = models.IntegerField(
        choices=WEEKDAY_CHOICES,
        verbose_name='День недели'
    )
    start_time = models.TimeField(
        verbose_name='Время начала'
    )
    end_time = models.TimeField(
        verbose_name='Время окончания'
    )
    classroom = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Аудитория'
    )
    note = models.TextField(
        blank=True,
        verbose_name='Примечание'
    )
    is_template = models.BooleanField(
        default=False,
        verbose_name='Шаблон',
        help_text='Является ли это занятие частью шаблона'
    )
    template = models.ForeignKey(
        'ScheduleTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lessons',
        verbose_name='Шаблон',
        help_text='Шаблон, к которому относится это занятие (если is_template=True)'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Занятие'
        verbose_name_plural = 'Занятия'
        ordering = ['weekday', 'start_time']

    def __str__(self):
        weekday_name = dict(self.WEEKDAY_CHOICES)[self.weekday]
        return f'{self.association.name} - {weekday_name} {self.start_time.strftime("%H:%M")}'

    def get_duration_minutes(self):
        """Получить продолжительность занятия в минутах."""
        start = self.start_time
        end = self.end_time
        start_minutes = start.hour * 60 + start.minute
        end_minutes = end.hour * 60 + end.minute
        
        # Если время окончания меньше времени начала (не должно происходить при валидации),
        # возвращаем 0 или отрицательное значение (будет обработано в views)
        duration = end_minutes - start_minutes
        
        # Защита от отрицательных значений (если end < start)
        if duration < 0:
            # Это может произойти, если занятие переходит через полночь
            # В нашем случае это ошибка данных, возвращаем 0
            return 0
        
        return duration


class ScheduleTemplate(models.Model):
    """
    Модель шаблона расписания.
    """
    name = models.CharField(
        max_length=200,
        verbose_name='Название шаблона'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    association = models.ForeignKey(
        Association,
        on_delete=models.CASCADE,
        related_name='templates',
        verbose_name='Объединение',
        help_text='Объединение, для которого создан шаблон'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates',
        verbose_name='Создал'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Шаблон расписания'
        verbose_name_plural = 'Шаблоны расписания'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.association.name})'

