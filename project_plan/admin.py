from django.conf import settings
"""Navigation for the existing AdminSite; registrations and Django permissions stay in place."""
from types import MethodType
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.urls import reverse

SECTIONS = [
    ('team', 'Сотрудники и отделы', 'Пользователи, структура и права доступа', [
        ('accounts.user', 'Сотрудники'), ('accounts.department', 'Отделы'), ('auth.group', 'Группы доступа')]),
    ('work', 'Работа команды', 'Задачи, мероприятия и подготовка форумов', [
        ('tasks.task', 'Задачи'), ('events.meropriyatie', 'Мероприятия'), ('events.forumchecklist', 'Чек-листы форумов'),
        ('events.checklistblock', 'Блоки чек-листов'), ('events.checklisttask', 'Пункты чек-листов'), ('tasks.tasktemplate', 'Шаблоны задач')]),
    ('calendar', 'Календарь и занятия', 'Объединения, учебные недели и события', [
        ('schedule.association', 'Объединения'), ('schedule.lesson', 'Занятия'),
        ('schedule.scheduletemplate', 'Шаблоны расписания'), ('schedule.scheduleevent', 'События календаря')]),
    ('materials', 'Материалы', 'Документы, база знаний и вложения', [
        ('documents.document', 'Документы'), ('wiki.wikiarticle', 'Статьи базы знаний'),
        ('wiki.wikiarticlefile', 'Файлы статей'), ('tasks.taskfile', 'Файлы задач'), ('events.meropriyatiefile', 'Файлы мероприятий')]),
    ('service', 'Служебные записи', 'Состояния, связи, обсуждения и история изменений', [
        ('events.eventworkspace', 'Команды мероприятий'), ('events.eventtask', 'Задачи мероприятий'),
        ('events.eventnote', 'Обсуждения мероприятий'), ('events.eventactivity', 'Действия в мероприятиях'),
        ('documents.documentstate', 'Архив документов'), ('wiki.wikistate', 'Архив статей'),
        ('wiki.wikifilestate', 'Скрытые вложения статей'), ('wiki.wikirevision', 'Версии статей'),
        ('tasks.taskcomment', 'Комментарии задач'), ('events.checklisttaskcomment', 'Комментарии чек-листов')]),
    ('settings', 'Настройки и журнал', 'Уведомления, технические настройки и действия', [
        ('accounts.notification', 'Уведомления'), ('accounts.activitylog', 'Журнал сайта'), ('admin_interface.theme', 'Темы Admin Interface')]),
]


def sections(apps, path):
    """Group only the models already permitted by AdminSite.get_app_list()."""
    remaining = {}
    for app in apps:
        for item in app['models']:
            model = item['model']
            key = model._meta.label_lower
            remaining[key] = dict(item, key=key)
    result = []
    for code, title, description, entries in SECTIONS:
        models = []
        for key, label in entries:
            if key not in remaining: continue
            item = remaining.pop(key)
            item['name'] = label
            item['current'] = bool(item.get('admin_url') and path.startswith(item['admin_url']))
            item['search_text'] = title + ' ' + label
            models.append(item)
        if models:
            result.append(dict(code=code, title=title, description=description, models=models,
                expanded=code != 'service' or any(item['current'] for item in models)))
    # Extensions keep their links instead of disappearing from the menu.
    for app in apps:
        models = [remaining.pop(item['model']._meta.label_lower) for item in app['models'] if item['model']._meta.label_lower in remaining]
        if models:
            for item in models:
                item['current'] = bool(item.get('admin_url') and path.startswith(item['admin_url']))
                item['search_text'] = str(app['name']) + ' ' + str(item['name'])
            result.append(dict(code=app['app_label'], title=app['name'], description='Дополнительные разделы', models=models, expanded=True))
    return result


def configure_admin():
    site = admin.site
    if getattr(site, '_yamolod_configured', False): return
    from .admin_records import install_record_admins
    install_record_admins(site)
    previous_context = site.each_context
    def each_context(self, request):
        context = previous_context(request)
        context['admin_sections'] = sections(context['available_apps'], request.path)
        if request.path == reverse('admin:index') and context['has_permission']:
            links = {item['key']: item for section in context['admin_sections'] for item in section['models']}
            cards = []
            for key, label in [('accounts.user', 'Сотрудники'), ('tasks.task', 'Задачи'),
                               ('events.meropriyatie', 'Мероприятия'), ('wiki.wikiarticle', 'Статьи')]:
                item = links.get(key)
                if item and item.get('admin_url'):
                    model_admin = self._registry[item['model']]
                    cards.append(dict(label=label, count=model_admin.get_queryset(request).count(), url=item['admin_url']))
            context['admin_overview'] = cards
            context['admin_recent'] = LogEntry.objects.filter(user_id=request.user.pk).select_related('content_type').order_by('-action_time')[:8]
        return context
    site.each_context = MethodType(each_context, site)
    site.site_header = settings.SITE_NAME + ' · Администрирование'
    site.site_title = settings.SITE_NAME + ' · Управление'
    site.index_title = 'Панель управления'
    site.index_template = 'admin/workspace_index.html'
    site._yamolod_configured = True
