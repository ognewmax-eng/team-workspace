"""Expose v4/v5 service records as read-only admin views."""
from django.contrib import admin


class ReadOnlyRecordAdmin(admin.ModelAdmin):
    actions = None
    list_per_page = 30
    record_title = 'Служебные записи'

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields] + [field.name for field in self.model._meta.many_to_many]

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def changelist_view(self, request, extra_context=None):
        context = {'title': self.record_title}
        context.update(extra_context or {})
        return super().changelist_view(request, extra_context=context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        context = {'title': 'Просмотр: ' + self.record_title}
        context.update(extra_context or {})
        return super().change_view(request, object_id, form_url, extra_context=context)

    @admin.display(description='В архиве', boolean=True)
    def archived(self, obj): return obj.is_archived

    @admin.display(description='Состояние')
    def phase_label(self, obj): return obj.get_phase_display()

    @admin.display(description='Этап')
    def stage_label(self, obj): return obj.get_stage_display()

    @admin.display(description='Версия до изменения')
    def revision_title(self, obj): return obj.title

    @admin.display(description='Действие')
    def message_text(self, obj): return obj.message

    @admin.display(description='Комментарий')
    def note_text(self, obj): return obj.text[:100] + ('…' if len(obj.text) > 100 else '')


class ArchivedStateFilter(admin.SimpleListFilter):
    title = 'Архив'
    parameter_name = 'archive'
    def lookups(self, request, model_admin): return [('1', 'В архиве'), ('0', 'Действующие')]
    def queryset(self, request, queryset):
        if self.value() in ('0', '1'): return queryset.filter(is_archived=self.value() == '1')
        return queryset


def install_record_admins(site):
    from events.models import EventWorkspace, EventTask, EventNote, EventActivity
    from documents.models import DocumentState
    from wiki.models import WikiState, WikiFileState, WikiRevision
    specs = [
        (EventWorkspace, 'Команды мероприятий', ['event', 'phase_label', 'location', 'end_date', 'updated_at'], ['event__title', 'location'], ['phase'], ['event']),
        (EventTask, 'Задачи мероприятий', ['event', 'task', 'stage_label'], ['event__title', 'task__title'], ['stage'], ['event', 'task']),
        (EventNote, 'Обсуждения мероприятий', ['event', 'author', 'note_text', 'created_at'], ['event__title', 'text', 'author__username'], ['created_at'], ['event', 'author']),
        (EventActivity, 'Действия в мероприятиях', ['event', 'actor', 'message_text', 'created_at'], ['event__title', 'message', 'actor__username'], ['created_at'], ['event', 'actor']),
        (DocumentState, 'Архив документов', ['document', 'archived', 'updated_at'], ['document__title'], [ArchivedStateFilter], ['document']),
        (WikiState, 'Архив статей', ['article', 'archived', 'updated_at'], ['article__title'], [ArchivedStateFilter], ['article']),
        (WikiFileState, 'Скрытые вложения статей', ['attachment', 'archived'], ['attachment__file', 'attachment__article__title'], [ArchivedStateFilter], ['attachment__article']),
        (WikiRevision, 'Версии статей', ['article', 'revision_title', 'saved_by', 'saved_at'], ['title', 'article__title'], ['saved_at'], ['article', 'saved_by']),
    ]
    for model, title, display, search, filters, related in specs:
        if site.is_registered(model): continue
        cls = type(model.__name__ + 'RecordAdmin', (ReadOnlyRecordAdmin,), dict(
            record_title=title, list_display=display, search_fields=search, list_filter=filters, list_select_related=related,
            ordering=['-pk'], __module__=__name__))
        site.register(model, cls)
