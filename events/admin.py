"""
Админ-панель для чек-листов форумов.
"""
from django.contrib import admin
from .models import ForumChecklist, ChecklistBlock, ChecklistTask, ChecklistTaskComment, Meropriyatie, MeropriyatieFile


@admin.register(ForumChecklist)
class ForumChecklistAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_by', 'get_progress', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_progress(self, obj):
        total = obj.get_total_tasks_count()
        completed = obj.get_completed_tasks_count()
        return f'{completed}/{total} ({obj.get_progress_percentage()}%)'
    get_progress.short_description = 'Прогресс'


class ChecklistTaskInline(admin.TabularInline):
    model = ChecklistTask
    extra = 1
    fields = ['title', 'status', 'responsible', 'is_completed', 'deadline', 'order']


@admin.register(ChecklistBlock)
class ChecklistBlockAdmin(admin.ModelAdmin):
    list_display = ['title', 'checklist', 'status', 'get_tasks_count', 'order']
    list_filter = ['status', 'checklist']
    search_fields = ['title']
    inlines = [ChecklistTaskInline]
    ordering = ['checklist', 'order']


@admin.register(ChecklistTask)
class ChecklistTaskAdmin(admin.ModelAdmin):
    list_display = ['title_short', 'block', 'status', 'responsible', 'is_completed', 'deadline']
    list_filter = ['status', 'is_completed', 'block', 'block__checklist']
    search_fields = ['title', 'responsible__username', 'responsible__first_name', 'responsible__last_name', 'comment']
    readonly_fields = ['created_at', 'updated_at']
    
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Задача'


@admin.register(ChecklistTaskComment)
class ChecklistTaskCommentAdmin(admin.ModelAdmin):
    list_display = ['task', 'author', 'text_short', 'created_at']
    list_filter = ['created_at', 'task__block__checklist']
    search_fields = ['text', 'author__username', 'author__first_name', 'author__last_name']
    readonly_fields = ['created_at', 'updated_at']
    
    def text_short(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_short.short_description = 'Комментарий'


class MeropriyatieFileInline(admin.TabularInline):
    model = MeropriyatieFile
    extra = 0


@admin.register(Meropriyatie)
class MeropriyatieAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_type', 'event_date', 'department', 'responsible', 'in_rosmol', 'in_moroshka']
    list_filter = ['event_type', 'department', 'in_rosmol', 'in_moroshka']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [MeropriyatieFileInline]
    date_hierarchy = 'event_date'
    list_select_related = ['department', 'responsible']


@admin.register(MeropriyatieFile)
class MeropriyatieFileAdmin(admin.ModelAdmin):
    list_display = ['meropriyatie', 'uploaded_by', 'uploaded_at']
    list_filter = ['uploaded_at']
