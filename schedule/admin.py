"""
Админ-панель для управления расписанием.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import ScheduleEvent, Association, Lesson, ScheduleTemplate


@admin.register(ScheduleEvent)
class ScheduleEventAdmin(admin.ModelAdmin):
    """Админ-панель для событий расписания."""
    list_display = ['title_short', 'event_type_badge', 'department_link', 'time_display', 'location_short', 'participants_count', 'status_badge', 'created_by_link']
    list_filter = ['event_type', 'department', 'start_time', 'created_at']
    search_fields = ['title', 'description', 'location']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start_time'
    filter_horizontal = ['participants']
    list_per_page = 25
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'event_type', 'department')
        }),
        ('Время и место', {
            'fields': ('start_time', 'end_time', 'location')
        }),
        ('Участники', {
            'fields': ('participants', 'created_by')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def title_short(self, obj):
        """Краткое название события."""
        title = obj.title[:30] + '...' if len(obj.title) > 30 else obj.title
        return format_html('<strong>📅 {}</strong>', title)
    title_short.short_description = 'Событие'

    def event_type_badge(self, obj):
        """Цветной бейдж типа события."""
        type_colors = {
            'lesson': '#17a2b8',    # Синий
            'meeting': '#ffc107',    # Желтый
            'event': '#28a745',      # Зеленый
            'task': '#6f42c1',       # Фиолетовый
            'other': '#6c757d'       # Серый
        }
        type_icons = {
            'lesson': '📚',
            'meeting': '🤝',
            'event': '🎉',
            'task': '✓',
            'other': '📌'
        }
        color = type_colors.get(obj.event_type, '#6c757d')
        icon = type_icons.get(obj.event_type, '📌')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_event_type_display()
        )
    event_type_badge.short_description = 'Тип'

    def department_link(self, obj):
        """Ссылка на отдел."""
        if obj.department:
            return format_html(
                '<a href="/admin/accounts/department/{}/change/">{}</a>',
                obj.department.id, obj.department.name
            )
        return '-'
    department_link.short_description = 'Отдел'

    def time_display(self, obj):
        """Отображение времени события."""
        start = obj.start_time.strftime('%d.%m.%Y %H:%M')
        end = obj.end_time.strftime('%H:%M')
        if obj.is_ongoing():
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">🟢 {} - {}</span>',
                start, end
            )
        elif obj.is_past():
            return format_html(
                '<span style="color: #6c757d;">⚫ {} - {}</span>',
                start, end
            )
        return format_html('🔵 {} - {}', start, end)
    time_display.short_description = 'Время'

    def location_short(self, obj):
        """Краткое место проведения."""
        if obj.location:
            location = obj.location[:20] + '...' if len(obj.location) > 20 else obj.location
            return format_html('📍 {}', location)
        return format_html('<span style="color: #6c757d;">Не указано</span>')
    location_short.short_description = 'Место'

    def participants_count(self, obj):
        """Количество участников."""
        count = obj.participants.count()
        return format_html('👥 {}', count)
    participants_count.short_description = 'Участников'

    def status_badge(self, obj):
        """Статус события."""
        if obj.is_past():
            return format_html(
                '<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 3px;">⚫ Завершено</span>'
            )
        elif obj.is_ongoing():
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">🟢 Идет сейчас</span>'
            )
        return format_html(
            '<span style="background-color: #17a2b8; color: white; padding: 3px 8px; border-radius: 3px;">🔵 Предстоит</span>'
        )
    status_badge.short_description = 'Статус'

    def created_by_link(self, obj):
        """Ссылка на создателя."""
        if obj.created_by:
            return format_html(
                '<a href="/admin/accounts/user/{}/change/">{}</a>',
                obj.created_by.id, obj.created_by.get_full_name() or obj.created_by.username
            )
        return '-'
    created_by_link.short_description = 'Создал'


@admin.register(Association)
class AssociationAdmin(admin.ModelAdmin):
    """Админ-панель для объединений."""
    list_display = ['name', 'color_display', 'specialist', 'department', 'is_active', 'lessons_count']
    list_filter = ['department', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def color_display(self, obj):
        """Отображение цвета."""
        return format_html(
            '<div style="width: 30px; height: 30px; background-color: {}; border: 1px solid #ccc; border-radius: 3px;"></div>',
            obj.color
        )
    color_display.short_description = 'Цвет'
    
    def lessons_count(self, obj):
        """Количество занятий."""
        count = obj.lessons.filter(is_template=False).count()
        return format_html('📚 {}', count)
    lessons_count.short_description = 'Занятий'


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    """Админ-панель для занятий."""
    list_display = ['association', 'weekday_display', 'time_display', 'classroom', 'is_template']
    list_filter = ['weekday', 'is_template', 'association', 'created_at']
    search_fields = ['association__name', 'classroom', 'note']
    readonly_fields = ['created_at', 'updated_at']
    
    def weekday_display(self, obj):
        """Отображение дня недели."""
        return dict(Lesson.WEEKDAY_CHOICES)[obj.weekday]
    weekday_display.short_description = 'День недели'
    
    def time_display(self, obj):
        """Отображение времени."""
        return f'{obj.start_time.strftime("%H:%M")} - {obj.end_time.strftime("%H:%M")}'
    time_display.short_description = 'Время'


@admin.register(ScheduleTemplate)
class ScheduleTemplateAdmin(admin.ModelAdmin):
    """Админ-панель для шаблонов расписания."""
    list_display = ['name', 'association', 'created_by', 'lessons_count', 'created_at']
    list_filter = ['association', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def lessons_count(self, obj):
        """Количество занятий в шаблоне."""
        count = obj.lessons.count()
        return format_html('📚 {}', count)
    lessons_count.short_description = 'Занятий'

