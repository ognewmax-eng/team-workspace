"""
Модели для системы управления задачами.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Department

User = get_user_model()


class Task(models.Model):
    """
    Модель задачи с привязкой к отделам и исполнителям.
    """
    STATUS_CHOICES = [
        ('assigned', 'Назначено'),
        ('in_progress', 'В работе'),
        ('pending', 'На проверке'),
        ('completed', 'Завершено'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('urgent', 'Срочный'),
    ]

    title = models.CharField(
        max_length=200,
        verbose_name='Название задачи'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='assigned',
        verbose_name='Статус'
    )
    status_locked_by_director = models.BooleanField(
        default=False,
        verbose_name='Статус зафиксирован руководителем',
        help_text='Если включено, статус задачи не изменяется автоматически по статусам исполнителей'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name='Приоритет'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='Отдел (основной)',
        help_text='Основной отдел задачи (для совместимости; заполняется первым из выбранных отделов)'
    )
    departments = models.ManyToManyField(
        Department,
        related_name='task_set',
        blank=True,
        verbose_name='Отделы',
        help_text='Отделы, к которым относится задача (можно выбрать несколько)'
    )
    assigned_to = models.ManyToManyField(
        User,
        through='TaskAssignee',
        related_name='assigned_tasks',
        blank=True,
        verbose_name='Исполнители',
        help_text='Можно выбрать несколько исполнителей из разных отделов'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks',
        verbose_name='Создал'
    )
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дедлайн'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата завершения'
    )
    google_calendar_event_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Google Calendar Event ID',
        help_text='ID события в Google Calendar для синхронизации'
    )
    parent_task = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subtasks',
        verbose_name='Родительская задача',
        help_text='Выберите родительскую задачу, если это подзадача'
    )
    is_epic = models.BooleanField(
        default=False,
        verbose_name='Epic задача',
        help_text='Большая задача с функциями из чек-листа'
    )
    is_archived = models.BooleanField(
        default=False,
        verbose_name='В архиве',
        help_text='Архивированные задачи скрыты из общего списка и канбана'
    )

    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def is_overdue(self):
        """Проверка, просрочена ли задача."""
        if self.deadline and self.status != 'completed':
            return timezone.now() > self.deadline
        return False

    def get_absolute_url(self):
        """Получить URL задачи."""
        from django.urls import reverse
        return reverse('task_detail', args=[self.id])

    def get_subtasks(self):
        """Получить все подзадачи."""
        return self.subtasks.all()
    
    def get_progress_percentage(self):
        """Получить процент выполнения задачи на основе подзадач."""
        subtasks = self.get_subtasks()
        if not subtasks.exists():
            # Если нет подзадач, считаем по статусу самой задачи
            if self.status == 'completed':
                return 100
            elif self.status == 'in_progress':
                return 50
            elif self.status == 'assigned':
                return 25
            else:
                return 0
        
        # Считаем процент на основе завершенных подзадач
        completed_count = subtasks.filter(status='completed').count()
        total_count = subtasks.count()
        if total_count > 0:
            return int((completed_count / total_count) * 100)
        return 0
    
    def is_parent_task(self):
        """Проверка, является ли задача родительской (имеет подзадачи)."""
        return self.subtasks.exists()
    
    def can_be_parent(self, task_id=None):
        """Проверка, может ли задача быть родительской (не создает циклических зависимостей)."""
        if task_id is None:
            task_id = self.id
        if not task_id:
            return True
        
        # Проверяем, не является ли выбранная задача подзадачей текущей
        current = self
        while current.parent_task:
            if current.parent_task.id == task_id:
                return False
            current = current.parent_task
        return True

    def save(self, *args, **kwargs):
        """Автоматическое заполнение completed_at при завершении."""
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status != 'completed':
            self.completed_at = None
        super().save(*args, **kwargs)

    def update_aggregate_status(self):
        """
        Пересчитать общий статус задачи по статусам исполнителей.
        Завершено — только если все исполнители в статусе completed.
        Всегда читает назначения из БД, чтобы не использовать устаревший
        prefetch_related-кэш после сохранения TaskAssignee.
        """
        # Если статус явно зафиксирован руководителем, не изменяем его автоматически
        if self.status_locked_by_director:
            return
        assignments = TaskAssignee.objects.filter(task=self)
        total = assignments.count()
        if total == 0:
            return
        completed_count = assignments.filter(status='completed').count()
        if completed_count == total:
            self.status = 'completed'
            if not self.completed_at:
                self.completed_at = timezone.now()
        elif (assignments.filter(status='pending').exists()
              and not assignments.exclude(status__in=['pending', 'completed']).exists()):
            # Ready for review when every remaining assignee has submitted their part.
            self.status = 'pending'
            self.completed_at = None
        elif assignments.filter(status='in_progress').exists() or assignments.filter(status='pending').exists():
            self.status = 'in_progress'
            self.completed_at = None
        else:
            self.status = 'assigned'
            self.completed_at = None
        self.save(update_fields=['status', 'completed_at'])


class TaskAssignee(models.Model):
    """
    Назначение исполнителя на задачу с персональным статусом.
    Каждый исполнитель отмечает свой статус отдельно.
    """
    ASSIGNEE_STATUS_CHOICES = [
        ('assigned', 'Назначено'),
        ('in_progress', 'В работе'),
        ('pending', 'На проверке'),
        ('completed', 'Завершено'),
    ]
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='Задача'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='task_assignments',
        verbose_name='Исполнитель'
    )
    status = models.CharField(
        max_length=20,
        choices=ASSIGNEE_STATUS_CHOICES,
        default='assigned',
        verbose_name='Статус исполнителя'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата завершения'
    )

    class Meta:
        verbose_name = 'Назначение на задачу'
        verbose_name_plural = 'Назначения на задачи'
        unique_together = [['task', 'user']]
        ordering = ['task', 'user']

    def __str__(self):
        return f'{self.user} — {self.task.title}'

    def save(self, *args, **kwargs):
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status != 'completed':
            self.completed_at = None
        super().save(*args, **kwargs)


class TaskComment(models.Model):
    """
    Комментарии к задачам.
    """
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Задача'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='task_comments',
        verbose_name='Автор'
    )
    text = models.TextField(
        verbose_name='Текст комментария'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Комментарий к задаче'
        verbose_name_plural = 'Комментарии к задачам'
        ordering = ['-created_at']

    def __str__(self):
        return f'Комментарий от {self.author} к задаче "{self.task.title}"'


class TaskFile(models.Model):
    """
    Прикрепленные файлы к задачам.
    """
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='Задача'
    )
    file = models.FileField(
        upload_to='task_files/%Y/%m/%d/',
        verbose_name='Файл'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='uploaded_files',
        verbose_name='Загрузил'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата загрузки'
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Описание файла'
    )

    class Meta:
        verbose_name = 'Файл задачи'
        verbose_name_plural = 'Файлы задач'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.file.name} (к задаче "{self.task.title}")'


class TaskTemplate(models.Model):
    """
    Шаблоны для создания задач.
    """
    TEMPLATE_TYPE_CHOICES = [
        ('simple', 'Обычная задача'),
        ('mass', 'Массовая задача'),
        ('epic', 'Epic'),
    ]

    name = models.CharField(
        max_length=100,
        verbose_name='Название шаблона'
    )
    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPE_CHOICES,
        verbose_name='Тип шаблона'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='Шаблон по умолчанию'
    )

    class Meta:
        verbose_name = 'Шаблон задачи'
        verbose_name_plural = 'Шаблоны задач'
        ordering = ['is_default', 'name']

    def __str__(self):
        return self.name

