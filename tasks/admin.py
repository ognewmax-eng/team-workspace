"""
Админ-панель для управления задачами.
"""
from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from .models import Task, TaskComment, TaskFile, TaskTemplate, TaskAssignee


class TaskAssigneeInline(admin.TabularInline):
    """Инлайн для назначений исполнителей с персональным статусом."""
    model = TaskAssignee
    extra = 0
    raw_id_fields = ['user']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Админ-панель для задач."""
    list_display = ['title_short', 'status', 'status_badge', 'priority_badge', 'department_link', 'assigned_to_link', 'parent_task_link', 'subtasks_count', 'deadline_display', 'is_overdue_display', 'created_at']
    list_filter = ['status', 'priority', 'department', 'parent_task', 'created_at', 'deadline']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    date_hierarchy = 'created_at'
    list_per_page = 50
    list_editable = ['status']  # Быстрое изменение статуса
    inlines = [TaskAssigneeInline]
    list_select_related = ['department', 'parent_task', 'created_by']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('assigned_to').annotate(ui_subtasks_count=Count('subtasks', distinct=True))

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'status', 'status_locked_by_director', 'priority')
        }),
        ('Назначение', {
            'fields': ('department', 'created_by')
        }),
        ('Сроки', {
            'fields': ('deadline', 'created_at', 'updated_at', 'completed_at')
        }),
        ('Иерархия', {
            'fields': ('parent_task',),
            'description': 'Выберите родительскую задачу, если это подзадача'
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Если статус задачи изменён через админку, автоматически включаем фиксацию статуса.
        Поле status_locked_by_director выведено в форму — его можно снять, чтобы снова
        разрешить автоматический пересчёт по статусам исполнителей.
        """
        if change and form is not None and 'status' in form.changed_data:
            obj.status_locked_by_director = True
        super().save_model(request, obj, form, change)

    def title_short(self, obj):
        """Краткое название задачи."""
        title = obj.title[:40] + '...' if len(obj.title) > 40 else obj.title
        return format_html('<strong>📋 {}</strong>', title)
    title_short.short_description = 'Задача'

    def status_badge(self, obj):
        """Цветной бейдж статуса."""
        status_colors = {
            'pending': '#ffc107',    # Желтый
            'assigned': '#17a2b8',   # Голубой
            'in_progress': '#0d6efd', # Синий
            'completed': '#28a745'    # Зеленый
        }
        status_icons = {
            'pending': '⏳',
            'assigned': '👤',
            'in_progress': '🔄',
            'completed': '✅'
        }
        color = status_colors.get(obj.status, '#6c757d')
        icon = status_icons.get(obj.status, '❓')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_badge.short_description = 'Статус'

    def priority_badge(self, obj):
        """Цветной бейдж приоритета."""
        priority_colors = {
            'urgent': '#dc3545',   # Красный
            'high': '#fd7e14',     # Оранжевый
            'medium': '#17a2b8',   # Синий
            'low': '#6c757d'       # Серый
        }
        priority_icons = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🔵',
            'low': '⚪'
        }
        color = priority_colors.get(obj.priority, '#6c757d')
        icon = priority_icons.get(obj.priority, '⚪')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_priority_display()
        )
    priority_badge.short_description = 'Приоритет'

    def department_link(self, obj):
        """Ссылка на отдел."""
        if obj.department:
            return format_html(
                '<a href="/admin/accounts/department/{}/change/">{}</a>',
                obj.department.id, obj.department.name
            )
        return '-'
    department_link.short_description = 'Отдел'

    def assigned_to_link(self, obj):
        """Ссылки на исполнителей."""
        assignees = obj.assigned_to.all()
        if assignees:
            return format_html_join(', ', '<a href="{}">{}</a>',
                ((reverse('admin:accounts_user_change', args=[assignee.pk]), assignee.get_full_name() or assignee.username) for assignee in assignees))
        return format_html('<span style="color: #6c757d;">Не назначен</span>')
    assigned_to_link.short_description = 'Исполнители'

    def deadline_display(self, obj):
        """Отображение дедлайна."""
        if obj.deadline:
            if obj.deadline < timezone.now() and obj.status != 'completed':
                return format_html(
                    '<span style="color: #dc3545; font-weight: bold;">⚠️ {}</span>',
                    obj.deadline.strftime('%d.%m.%Y %H:%M')
                )
            return obj.deadline.strftime('%d.%m.%Y %H:%M')
        return format_html('<span style="color: #6c757d;">Не установлен</span>')
    deadline_display.short_description = 'Дедлайн'

    def is_overdue_display(self, obj):
        """Отображение просроченных задач."""
        if obj.is_overdue():
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">⚠️ Просрочено</span>'
            )
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">✓ В срок</span>'
        )
    is_overdue_display.short_description = 'Статус дедлайна'

    def parent_task_link(self, obj):
        """Ссылка на родительскую задачу."""
        if obj.parent_task:
            return format_html(
                '<a href="/admin/tasks/task/{}/change/">📋 {}</a>',
                obj.parent_task.id, obj.parent_task.title[:30]
            )
        return format_html('<span style="color: #6c757d;">—</span>')
    parent_task_link.short_description = 'Родительская задача'

    def subtasks_count(self, obj):
        """Количество подзадач."""
        count = obj.ui_subtasks_count if hasattr(obj, 'ui_subtasks_count') else obj.subtasks.count()
        if count > 0:
            return format_html(
                '<span style="background-color: #17a2b8; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">📋 {}</span>',
                count
            )
        return format_html('<span style="color: #6c757d;">—</span>')
    subtasks_count.short_description = 'Подзадачи'


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    """Админ-панель для комментариев."""
    list_display = ['task_link', 'author_link', 'text_short', 'created_at']
    list_filter = ['created_at']
    search_fields = ['text', 'task__title', 'author__username']
    readonly_fields = ['created_at']
    list_per_page = 25

    def task_link(self, obj):
        """Ссылка на задачу."""
        return format_html(
            '<a href="/admin/tasks/task/{}/change/">📋 {}</a>',
            obj.task.id, obj.task.title[:30]
        )
    task_link.short_description = 'Задача'

    def author_link(self, obj):
        """Ссылка на автора."""
        return format_html(
            '<a href="/admin/accounts/user/{}/change/">{}</a>',
            obj.author.id, obj.author.get_full_name() or obj.author.username
        )
    author_link.short_description = 'Автор'

    def text_short(self, obj):
        """Краткий текст комментария."""
        text = obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
        return format_html('💬 {}', text)
    text_short.short_description = 'Комментарий'


@admin.register(TaskFile)
class TaskFileAdmin(admin.ModelAdmin):
    """Админ-панель для файлов задач."""
    list_display = ['task_link', 'file_link', 'uploaded_by_link', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['task__title', 'description', 'file']
    readonly_fields = ['uploaded_at']
    list_per_page = 25

    def task_link(self, obj):
        """Ссылка на задачу."""
        return format_html(
            '<a href="/admin/tasks/task/{}/change/">📋 {}</a>',
            obj.task.id, obj.task.title[:30]
        )
    task_link.short_description = 'Задача'

    def file_link(self, obj):
        """Ссылка на файл."""
        filename = obj.file.name.split('/')[-1]
        return format_html(
            '<a href="{}" target="_blank">📎 {}</a>',
            obj.file.url, filename[:30]
        )
    file_link.short_description = 'Файл'

    def uploaded_by_link(self, obj):
        """Ссылка на загрузившего."""
        return format_html(
            '<a href="/admin/accounts/user/{}/change/">{}</a>',
            obj.uploaded_by.id, obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        )
    uploaded_by_link.short_description = 'Загрузил'


@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    """Админ-панель для шаблонов задач."""
    list_display = ['name', 'template_type', 'is_default', 'description_short']
    list_filter = ['template_type', 'is_default']
    search_fields = ['name', 'description']
    list_editable = ['is_default']
    
    def description_short(self, obj):
        """Краткое описание шаблона."""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Описание'
