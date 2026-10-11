"""
Админ-панель для управления пользователями и отделами.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models import User, Department, Notification, ActivityLog, UserWorkProfile


class WorkProfileInline(admin.StackedInline):
    model = UserWorkProfile
    extra = 0
    max_num = 1
    can_delete = False
    readonly_fields = ('updated_at',)
    fields = ('about', 'responsibilities', 'skills', 'projects', 'work_schedule', 'workplace', 'contact_preferences', 'updated_at')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Админ-панель для отделов."""
    list_display = ['name', 'description_short', 'member_count', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']
    list_per_page = 25

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(ui_member_count=Count('members', distinct=True))

    def description_short(self, obj):
        """Краткое описание отдела."""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Описание'

    def member_count(self, obj):
        """Количество сотрудников в отделе."""
        count = obj.ui_member_count if hasattr(obj, 'ui_member_count') else obj.members.count()
        if count > 0:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">👥 {}</span>',
                count
            )
        return format_html('<span style="color: #6c757d;">👥 0</span>')
    member_count.short_description = 'Сотрудников'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Расширенная админ-панель для пользователей."""
    list_display = ['username', 'email', 'get_full_name_display', 'role_badge', 'department_link', 'telegram_status', 'is_active_badge', 'created_at', 'pending_approval']
    list_filter = ['role', 'department', 'is_active', 'is_staff', 'is_superuser', 'created_at']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone']
    readonly_fields = ['created_at', 'updated_at', 'last_login', 'date_joined']
    list_per_page = 25
    date_hierarchy = 'created_at'
    actions = ['activate_users', 'deactivate_users']
    list_select_related = ['department']
    inlines = [WorkProfileInline]

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Дополнительная информация', {
            'fields': ('role', 'department', 'phone', 'position')
        }),
        ('Telegram', {
            'fields': ('telegram_chat_id',),
            'description': 'ID чата в Telegram для отправки уведомлений. Получите его, отправив команду /start боту.'
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Дополнительная информация', {
            'fields': ('role', 'department', 'phone', 'position', 'email', 'first_name', 'last_name')
        }),
    )

    def get_full_name_display(self, obj):
        """Отображение полного имени с иконкой."""
        full_name = obj.get_full_name()
        if full_name:
            return format_html('👤 {}', full_name)
        return format_html('👤 {}', obj.username)
    get_full_name_display.short_description = 'Пользователь'

    def role_badge(self, obj):
        """Цветной бейдж роли."""
        colors = {
            'director': '#dc3545',  # Красный
            'head': '#ffc107',      # Желтый
            'specialist': '#17a2b8' # Синий
        }
        icons = {
            'director': '👑',
            'head': '⭐',
            'specialist': '👨‍💼'
        }
        color = colors.get(obj.role, '#6c757d')
        icon = icons.get(obj.role, '👤')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_role_display()
        )
    role_badge.short_description = 'Роль'

    def department_link(self, obj):
        """Ссылка на отдел."""
        if obj.department:
            return format_html(
                '<a href="/admin/accounts/department/{}/change/">{}</a>',
                obj.department.id, obj.department.name
            )
        return format_html('<span style="color: #6c757d;">Не назначен</span>')
    department_link.short_description = 'Отдел'

    def is_active_badge(self, obj):
        """Цветной бейдж активности."""
        if obj.is_active:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Активен</span>'
            )
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">✗ Неактивен</span>'
        )
    is_active_badge.short_description = 'Статус'

    def pending_approval(self, obj):
        """Индикатор ожидания одобрения."""
        if not obj.is_active:
            return format_html(
                '<a href="{}" class="badge bg-warning">Неактивен</a>', reverse('pending_registrations')
            )
        return '-'
    pending_approval.short_description = 'Одобрение'

    def telegram_status(self, obj):
        """Статус подключения Telegram."""
        if obj.telegram_chat_id:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Подключен</span>'
            )
        return format_html(
            '<span style="color: #6c757d;">✗ Не подключен</span>'
        )
    telegram_status.short_description = 'Telegram'

    def activate_users(self, request, queryset):
        """Массовое активирование пользователей."""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} пользователей активировано.')
    activate_users.short_description = 'Активировать выбранных пользователей'

    def deactivate_users(self, request, queryset):
        """Массовое деактивирование пользователей."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} пользователей деактивировано.')
    deactivate_users.short_description = 'Деактивировать выбранных пользователей'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Админ-панель для уведомлений."""
    list_display = ['user', 'notification_type_display', 'message_short', 'is_read_badge', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'user__email', 'message']
    readonly_fields = ['created_at']
    list_per_page = 50
    date_hierarchy = 'created_at'
    actions = ['mark_as_read', 'mark_as_unread']

    def notification_type_display(self, obj):
        """Отображение типа уведомления с иконкой."""
        icons = {
            'task_assigned': '📋',
            'task_comment': '💬',
            'task_status_changed': '🔄',
        }
        icon = icons.get(obj.notification_type, '🔔')
        return f'{icon} {obj.get_notification_type_display()}'
    notification_type_display.short_description = 'Тип'

    def message_short(self, obj):
        """Краткое сообщение."""
        if len(obj.message) > 60:
            return obj.message[:60] + '...'
        return obj.message
    message_short.short_description = 'Сообщение'

    def is_read_badge(self, obj):
        """Бейдж прочитанности."""
        if obj.is_read:
            return format_html('<span style="color: #6c757d;">✓ Прочитано</span>')
        return format_html('<span style="color: #007bff; font-weight: bold;">● Непрочитано</span>')
    is_read_badge.short_description = 'Статус'

    def mark_as_read(self, request, queryset):
        """Отметить как прочитанные."""
        count = queryset.update(is_read=True)
        self.message_user(request, f'{count} уведомлений отмечено как прочитанные.')
    mark_as_read.short_description = 'Отметить как прочитанные'

    def mark_as_unread(self, request, queryset):
        """Отметить как непрочитанные."""
        count = queryset.update(is_read=False)
        self.message_user(request, f'{count} уведомлений отмечено как непрочитанные.')
    mark_as_unread.short_description = 'Отметить как непрочитанные'


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Админ-панель для логов действий пользователей."""
    list_display = ['user_link', 'action_badge', 'content_type_display', 'object_link', 
                    'description_short', 'ip_address', 'method_badge', 'created_at']
    list_filter = ['action', 'content_type', 'method', 'created_at', 'user']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name',
                     'description', 'object_repr', 'url', 'ip_address']
    readonly_fields = ['user', 'action', 'content_type', 'object_id', 'object_repr',
                      'description', 'ip_address', 'user_agent', 'url', 'method', 'created_at']
    list_per_page = 50
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'action', 'created_at')
        }),
        ('Объект', {
            'fields': ('content_type', 'object_id', 'object_repr', 'description')
        }),
        ('HTTP запрос', {
            'fields': ('method', 'url', 'ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Ссылка на пользователя."""
        if obj.user:
            url = reverse('admin:accounts_user_change', args=[obj.user.id])
            return format_html(
                '<a href="{}">👤 {}</a>',
                url, obj.user.get_full_name() or obj.user.username
            )
        return format_html('<span style="color: #6c757d;">Анонимный</span>')
    user_link.short_description = 'Пользователь'
    
    def action_badge(self, obj):
        """Цветной бейдж действия."""
        colors = {
            'create': '#28a745',  # Зеленый
            'update': '#ffc107',  # Желтый
            'delete': '#dc3545',  # Красный
            'view': '#17a2b8',   # Синий
            'login': '#6f42c1',  # Фиолетовый
            'logout': '#6c757d', # Серый
            'download': '#20c997', # Бирюзовый
            'upload': '#fd7e14',   # Оранжевый
        }
        icons = {
            'create': '➕',
            'update': '✏️',
            'delete': '🗑️',
            'view': '👁️',
            'login': '🔐',
            'logout': '🚪',
            'download': '⬇️',
            'upload': '⬆️',
        }
        color = colors.get(obj.action, '#6c757d')
        icon = icons.get(obj.action, '📝')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_action_display()
        )
    action_badge.short_description = 'Действие'
    
    def content_type_display(self, obj):
        """Отображение типа контента."""
        if obj.content_type:
            return format_html('<strong>{}</strong>', obj.content_type)
        return format_html('<span style="color: #6c757d;">-</span>')
    content_type_display.short_description = 'Тип объекта'
    
    def object_link(self, obj):
        """Ссылка на объект (если возможно)."""
        if obj.object_id and obj.content_type:
            try:
                # Пытаемся создать ссылку на объект в админке
                app_label = 'accounts'
                if obj.content_type == 'Task':
                    app_label = 'tasks'
                    model_name = 'task'
                elif obj.content_type == 'Event':
                    app_label = 'events'
                    model_name = 'event'
                elif obj.content_type == 'WikiArticle':
                    app_label = 'wiki'
                    model_name = 'wikiarticle'
                elif obj.content_type == 'ScheduleEvent':
                    app_label = 'schedule'
                    model_name = 'scheduleevent'
                elif obj.content_type == 'User':
                    app_label = 'accounts'
                    model_name = 'user'
                else:
                    return format_html('<code>{}</code>', obj.object_repr or f'#{obj.object_id}')
                
                url = reverse(f'admin:{app_label}_{model_name}_change', args=[obj.object_id])
                return format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    url, obj.object_repr or f'#{obj.object_id}'
                )
            except Exception:
                return format_html('<code>{}</code>', obj.object_repr or f'#{obj.object_id}')
        elif obj.object_repr:
            return format_html('<code>{}</code>', obj.object_repr)
        return format_html('<span style="color: #6c757d;">-</span>')
    object_link.short_description = 'Объект'
    
    def description_short(self, obj):
        """Краткое описание."""
        if obj.description:
            if len(obj.description) > 60:
                return obj.description[:60] + '...'
            return obj.description
        return format_html('<span style="color: #6c757d;">-</span>')
    description_short.short_description = 'Описание'
    
    def method_badge(self, obj):
        """Бейдж HTTP метода."""
        colors = {
            'GET': '#17a2b8',
            'POST': '#28a745',
            'PUT': '#ffc107',
            'PATCH': '#ffc107',
            'DELETE': '#dc3545',
        }
        color = colors.get(obj.method, '#6c757d')
        if obj.method:
            return format_html(
                '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold; font-size: 11px;">{}</span>',
                color, obj.method
            )
        return format_html('<span style="color: #6c757d;">-</span>')
    method_badge.short_description = 'Метод'
    
    def has_add_permission(self, request):
        """Запрещаем ручное создание логов."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Запрещаем редактирование логов."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Разрешаем удаление только суперпользователям."""
        return request.user.is_superuser

# Keep the mailing workflow in its own module; existing account screens are unchanged.
from . import mailing_admin
