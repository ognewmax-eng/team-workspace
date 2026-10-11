"""Explicit, signed confirmation for director-only bulk archive/restore."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import OperationalError, transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from accounts.models import ActivityLog
from .models import Task
from .workspace import filtered_tasks, task_version, visible_tasks

LIMIT = 500
SALT = 'yamolod.bulk-archive.v7'


def blocked_parents(tasks):
    """Keep completed parents visible if any active descendant is unfinished."""
    roots = {task.pk for task in tasks}
    parents = {task.pk: task.parent_task_id for task in tasks}
    frontier = set(roots)
    visited = set()
    unfinished = []
    blocked = set()
    while frontier:
        children = Task.objects.filter(parent_task_id__in=frontier).values('pk', 'parent_task_id', 'status', 'is_archived')
        next_frontier = set()
        for child in children:
            parents[child['pk']] = child['parent_task_id']
            if not child['is_archived'] and child['status'] != 'completed': unfinished.append(child['pk'])
            next_frontier.add(child['pk'])
        visited.update(frontier)
        frontier = next_frontier - visited
    for child_id in unfinished:
        parent_id = parents.get(child_id)
        seen = set()
        while parent_id and parent_id not in seen:
            seen.add(parent_id)
            if parent_id in roots: blocked.add(parent_id)
            parent_id = parents.get(parent_id)
    return blocked


def preview(request, tasks, operation, total):
    blocked = blocked_parents(tasks) if operation == 'archive' else set()
    eligible = [task for task in tasks if task.pk not in blocked]
    token = signing.dumps({'user': request.user.pk, 'operation': operation,
                           'items': [[t.pk, task_version(t)] for t in eligible]}, salt=SALT, compress=True)
    return render(request, 'tasks/archive_confirm.html', {
        'archive_items': eligible, 'archive_blocked': [t for t in tasks if t.pk in blocked],
        'archive_token': token, 'archive_operation': operation,
        'archive_total': total, 'archive_limit': LIMIT, 'archive_more': total > LIMIT})


@login_required
@require_http_methods(['GET', 'POST'])
def bulk_archive(request):
    if not request.user.is_director():
        return HttpResponseForbidden('Архивировать и восстанавливать задачи может только директор.')
    if request.method == 'POST' and request.POST.get('confirm') == '1':
        try:
            data = signing.loads(request.POST.get('token', ''), salt=SALT, max_age=900)
            items = data['items']
            operation = data['operation']
            if data['user'] != request.user.pk or operation not in ['archive', 'restore'] or not 0 < len(items) <= LIMIT:
                raise ValueError
            expected = dict(items)
            if len(expected) != len(items) or any(not isinstance(pk, int) for pk in expected): raise ValueError
        except (signing.BadSignature, ValueError, KeyError, TypeError):
            return HttpResponseBadRequest('Подтверждение недействительно или устарело. Выберите задачи заново.')
        try:
            with transaction.atomic():
                tasks = list(Task.objects.select_for_update().filter(pk__in=expected).order_by('pk').prefetch_related('assignments'))
                stale = len(tasks) != len(expected) or any(task_version(t) != expected[t.pk] for t in tasks)
                stale = stale or any((t.is_archived if operation == 'archive' else not t.is_archived) or
                                      (operation == 'archive' and t.status != 'completed') for t in tasks)
                if operation == 'archive' and blocked_parents(tasks): stale = True
                if stale:
                    return render(request, 'tasks/archive_conflict.html', status=409)
                Task.objects.filter(pk__in=expected).update(is_archived=operation == 'archive', updated_at=timezone.now())
                label = 'Отправлена в архив' if operation == 'archive' else 'Возвращена из архива'
                ActivityLog.objects.bulk_create([ActivityLog(
                    user=request.user, action='update', content_type='Task', object_id=t.pk,
                    object_repr=t.title[:200], description=label + ' (массовое действие)',
                    url=request.build_absolute_uri()[:500], method='POST') for t in tasks])
        except OperationalError:
            return render(request, 'tasks/archive_conflict.html', status=409)
        messages.success(request, ('В архив перенесено задач: ' if operation == 'archive' else 'Из архива возвращено задач: ') + str(len(tasks)) + '. Файлы и комментарии сохранены.')
        return redirect('task_archive' if operation == 'archive' else 'task_list')

    operation = request.POST.get('operation', 'archive') if request.method == 'POST' else 'archive'
    if operation not in ['archive', 'restore']: return HttpResponseBadRequest('Неизвестное действие.')
    if request.method == 'POST':
        values = request.POST.getlist('task_ids')
        if not values or len(values) > LIMIT or any(not v.isascii() or not v.isdigit() or len(v) > 12 for v in values):
            return HttpResponseBadRequest('Выберите от 1 до %s задач.' % LIMIT)
        ids = {int(v) for v in values}
        qs = visible_tasks(request.user).filter(pk__in=ids, is_archived=operation == 'restore')
        if operation == 'archive': qs = qs.filter(status='completed')
        tasks = list(qs.order_by('pk').prefetch_related('assignments'))
        if len(tasks) != len(ids):
            return HttpResponseBadRequest('Некоторые задачи уже изменились или не подходят для действия. Обновите список.')
        return preview(request, tasks, operation, len(tasks))
    qs, _, _ = filtered_tasks(request)
    qs = qs.filter(status='completed')
    total = qs.count()
    return preview(request, list(qs[:LIMIT]), operation, total)
