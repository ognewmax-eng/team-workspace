"""
Модели для чек-листов форумов и мероприятий.
"""
from django.db import models
from django.contrib.auth import get_user_model
from accounts.models import Department

User = get_user_model()


class ForumChecklist(models.Model):
    """
    Чек-лист для планирования крупного форума.
    """
    title = models.CharField(
        max_length=200,
        verbose_name='Название форума',
        default='Планирование форума'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_forum_checklists',
        verbose_name='Создал'
    )
    participants = models.ManyToManyField(
        User,
        related_name='forum_checklists',
        verbose_name='Участники команды',
        help_text='Выберите участников команды из зарегистрированных пользователей',
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    related_task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forum_checklists',
        verbose_name='Связанная задача',
        help_text='Epic задача, для которой создан этот чек-лист'
    )

    class Meta:
        verbose_name = 'Чек-лист'
        verbose_name_plural = 'Чек-листы'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_total_tasks_count(self):
        """Получить общее количество задач."""
        return ChecklistTask.objects.filter(block__checklist=self).count()

    def get_completed_tasks_count(self):
        """Получить количество выполненных задач."""
        return ChecklistTask.objects.filter(
            block__checklist=self,
            is_completed=True
        ).count()

    def get_progress_percentage(self):
        """Получить процент выполнения."""
        total = self.get_total_tasks_count()
        if total == 0:
            return 0
        completed = self.get_completed_tasks_count()
        return int((completed / total) * 100)
    
    def get_participants_display(self):
        """Получить список имен участников для отображения."""
        return [user.get_full_name() or user.username for user in self.participants.all()]


class ChecklistBlock(models.Model):
    """
    Блок чек-листа (например, "Концепция", "Оргкомитет").
    """
    BLOCK_STATUS_CHOICES = [
        ('not_started', 'Не начато'),
        ('in_progress', 'В работе'),
        ('on_review', 'На согласовании'),
        ('approved', 'Утверждено'),
    ]

    checklist = models.ForeignKey(
        ForumChecklist,
        on_delete=models.CASCADE,
        related_name='blocks',
        verbose_name='Чек-лист'
    )
    title = models.CharField(
        max_length=200,
        verbose_name='Название блока'
    )
    order = models.IntegerField(
        default=0,
        verbose_name='Порядок отображения'
    )
    status = models.CharField(
        max_length=20,
        choices=BLOCK_STATUS_CHOICES,
        default='not_started',
        verbose_name='Статус блока'
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
        verbose_name = 'Блок чек-листа'
        verbose_name_plural = 'Блоки чек-листа'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f'{self.title} ({self.checklist.title})'

    def get_tasks_count(self):
        """Получить количество задач в блоке."""
        return self.tasks.count()

    def get_completed_tasks_count(self):
        """Получить количество выполненных задач."""
        return self.tasks.filter(is_completed=True).count()

    def calculate_status(self):
        """Автоматически вычислить статус блока на основе задач."""
        tasks = self.tasks.all()
        if not tasks.exists():
            return 'not_started'
        
        completed = tasks.filter(is_completed=True).count()
        total = tasks.count()
        
        if completed == total:
            return 'approved'
        elif completed > 0:
            # Проверяем, есть ли задачи "На проверке"
            if tasks.filter(status='on_review').exists():
                return 'on_review'
            return 'in_progress'
        else:
            return 'not_started'


class ChecklistTask(models.Model):
    """
    Задача в блоке чек-листа.
    """
    TASK_STATUS_CHOICES = [
        ('not_started', 'Не начато'),
        ('in_progress', 'В работе'),
        ('on_review', 'На проверке'),
        ('completed', 'Выполнено'),
    ]

    block = models.ForeignKey(
        ChecklistBlock,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='Блок'
    )
    title = models.TextField(
        verbose_name='Текст задачи'
    )
    is_completed = models.BooleanField(
        default=False,
        verbose_name='Выполнено'
    )
    status = models.CharField(
        max_length=20,
        choices=TASK_STATUS_CHOICES,
        default='not_started',
        verbose_name='Статус задачи'
    )
    responsible = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responsible_checklist_tasks',
        verbose_name='Ответственный'
    )
    comment = models.TextField(
        blank=True,
        verbose_name='Комментарий'
    )
    comment_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время отправки комментария'
    )
    file_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Имя файла'
    )
    file_url = models.URLField(
        blank=True,
        verbose_name='URL файла'
    )
    file_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время отправки файла'
    )
    deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name='Срок выполнения'
    )
    order = models.IntegerField(
        default=0,
        verbose_name='Порядок отображения'
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
        verbose_name = 'Задача чек-листа'
        verbose_name_plural = 'Задачи чек-листа'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f'{self.title[:50]}...' if len(self.title) > 50 else self.title

    def is_overdue(self):
        """Проверка, просрочена ли задача."""
        if not self.deadline or self.is_completed or self.status == 'completed':
            return False
        from django.utils import timezone
        return self.deadline < timezone.now().date()


class ChecklistTaskComment(models.Model):
    """
    Комментарий к задаче чек-листа.
    """
    task = models.ForeignKey(
        ChecklistTask,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Задача'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='checklist_task_comments',
        verbose_name='Автор'
    )
    text = models.TextField(
        verbose_name='Текст комментария'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата и время создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата и время обновления'
    )

    class Meta:
        verbose_name = 'Комментарий к задаче'
        verbose_name_plural = 'Комментарии к задачам'
        ordering = ['created_at']

    def __str__(self):
        return f'Комментарий от {self.author} к задаче {self.task.id}'


class Meropriyatie(models.Model):
    """
    Мероприятие отдела (МЗ, внеплановое). Создаётся начальником отдела.
    """
    EVENT_TYPE_CHOICES = [
        ('mz', 'МЗ'),
        ('vneplan', 'Внеплановое'),
    ]

    title = models.CharField(max_length=300, verbose_name='Название мероприятия')
    description = models.TextField(blank=True, verbose_name='Описание')
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default='mz',
        verbose_name='Тип мероприятия'
    )
    event_date = models.DateTimeField(null=True, blank=True, verbose_name='Точная дата проведения')
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='meropriyatiya',
        verbose_name='Отдел'
    )
    responsible = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responsible_meropriyatiya',
        verbose_name='Ответственный'
    )
    in_rosmol = models.BooleanField(
        default=False,
        verbose_name='Занесено в АИС «Росмолодёжь»'
    )
    rosmol_link = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Ссылка на мероприятие в АИС «Росмолодёжь»'
    )
    in_moroshka = models.BooleanField(
        default=False,
        verbose_name='Занесено в «Морошку»'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_meropriyatiya',
        verbose_name='Создал'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Мероприятие'
        verbose_name_plural = 'Мероприятия'
        ordering = ['-event_date', '-created_at']

    def __str__(self):
        return self.title


class MeropriyatieFile(models.Model):
    """Файл, прикреплённый к мероприятию."""
    meropriyatie = models.ForeignKey(
        Meropriyatie,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='Мероприятие'
    )
    file = models.FileField(upload_to='meropriyatiya/%Y/%m/%d/', verbose_name='Файл')
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='meropriyatie_uploads',
        verbose_name='Загрузил'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')
    description = models.CharField(max_length=200, blank=True, verbose_name='Описание')

    class Meta:
        verbose_name = 'Файл мероприятия'
        verbose_name_plural = 'Файлы мероприятий'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.file.name} (к мероприятию "{self.meropriyatie.title}")'


class EventWorkspace(models.Model):
    """Collaboration settings kept separately to preserve old event records."""
    PHASE_CHOICES = [('preparing', 'Подготовка'), ('ready', 'Готово к проведению'),
                     ('completed', 'Завершено'), ('cancelled', 'Отменено')]
    event = models.OneToOneField(Meropriyatie, on_delete=models.CASCADE, related_name='workspace')
    participants = models.ManyToManyField(User, blank=True, related_name='event_teams', verbose_name='Команда')
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default='preparing')
    location = models.CharField(max_length=200, blank=True, verbose_name='Место проведения')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='Окончание мероприятия')
    updated_at = models.DateTimeField(auto_now=True)


class EventTask(models.Model):
    STAGE_CHOICES = [('preparation', 'Подготовка'), ('delivery', 'Проведение'), ('followup', 'Итоги')]
    event = models.ForeignKey(Meropriyatie, on_delete=models.PROTECT, related_name='work_tasks')
    task = models.OneToOneField('tasks.Task', on_delete=models.CASCADE, related_name='event_work')
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='preparation')


class EventNote(models.Model):
    event = models.ForeignKey(Meropriyatie, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class EventActivity(models.Model):
    event = models.ForeignKey(Meropriyatie, on_delete=models.CASCADE, related_name='activity')
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    message = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


# Imported separately so earlier models remain readable during deployment.
from .planning_models import EventPlan, EventBudget, EventBudgetLine, EventBudgetApproval, EventImportBatch, EventImportRecord
