"""Download registered attachments after authentication and object access checks."""
import logging
from urllib.parse import urlsplit, parse_qs, unquote

from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_safe

from .synology_storage import SynologyStorage, clean_name, signature


def can_read_file(user, name):
    if not user.is_authenticated or not user.is_active:
        return False
    from documents.models import Document
    from tasks.models import TaskFile
    from wiki.models import WikiArticleFile
    from events.models import MeropriyatieFile, ChecklistTask

    director = user.is_director()
    department_id = user.department_id
    from documents.workspace import visible_documents
    if visible_documents(user).filter(file=name).exists():
        return True
    for item in TaskFile.objects.filter(file=name).select_related('task'):
        task = item.task
        from tasks.workspace import visible_tasks
        if visible_tasks(user).filter(pk=task.pk).exists():
            return True
    from wiki.workspace import visible_articles, can_edit
    for item in WikiArticleFile.objects.filter(file=name, article__in=visible_articles(user)).select_related('article', 'state'):
        state = getattr(item, 'state', None)
        if not state or not state.is_archived or can_edit(user, item.article):
            return True
    for item in MeropriyatieFile.objects.filter(file=name).select_related('meropriyatie'):
        from events.collaboration import visible_events
        if visible_events(user).filter(pk=item.meropriyatie_id).exists():
            return True
    # New checklist uploads store this backend's relative signed URL.
    from django.urls import reverse
    path = reverse('synology_file', kwargs={'name': name})
    for url in ChecklistTask.objects.filter(file_url__startswith=path + '?').values_list('file_url', flat=True):
        parsed = urlsplit(url)
        if (unquote(parsed.path) == unquote(path)
                and parse_qs(parsed.query).get('sig') == [signature(name)]):
            # forum_checklist_view is available to all authenticated users.
            return True
    return False


@login_required
@require_safe
def synology_file(request, name):
    supplied_sig = request.GET.get('sig', '')
    try:
        name = clean_name(name)
        for _ in range(3):
            if constant_time_compare(supplied_sig, signature(name)):
                break
            decoded = unquote(name, encoding='utf-8', errors='strict')
            if decoded == name:
                raise Http404
            name = clean_name(decoded)
        else:
            raise Http404
    except (SuspiciousFileOperation, UnicodeDecodeError):
        raise Http404
        
    if not can_read_file(request.user, name):
        raise Http404
    try:
        from django.core.files.storage import default_storage
        stream = default_storage.open(name)
    except FileNotFoundError:
        raise Http404
    except OSError:
        logging.getLogger(__name__).error('Synology download failed')
        return HttpResponse('Файловое хранилище временно недоступно.', status=502)
    response = FileResponse(stream, as_attachment=True, filename=name.rsplit('/', 1)[-1],
                            content_type='application/octet-stream')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
