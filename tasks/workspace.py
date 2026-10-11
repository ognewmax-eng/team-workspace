"""Shared task scope, validated filters and presentation data."""
import hashlib
import json
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Q, Count, F, Case, When, Value, IntegerField
from django.utils import timezone
from accounts.models import Department
from django.contrib.auth import get_user_model
from events.models import ChecklistTask
from .models import Task


def visible_tasks(user):
    qs = Task.objects.all()
    if user.is_director():
        return qs
    scope = Q(assigned_to=user) | Q(created_by=user) | Q(event_work__event__responsible=user) | Q(event_work__event__workspace__participants=user)
    if user.is_head() and user.department_id:
        scope |= Q(department_id=user.department_id) | Q(departments__id=user.department_id)
    return qs.filter(scope).distinct()


def can_edit_task(user, task):
    from events.collaboration import linked_task, can_manage, is_closed
    link = linked_task(task)
    if link:
        return not task.is_archived and not is_closed(link.event) and can_manage(user, link.event)
    return not task.is_archived and (user.is_director() or task.created_by_id == user.pk
            or (user.is_head() and bool(user.department_id)
                and (task.department_id == user.department_id
                     or any(d.pk == user.department_id for d in task.departments.all()))))


def task_version(task):
    assignments = sorted((a.pk, a.user_id, a.status) for a in task.assignments.all())
    data = [task.status, task.updated_at.isoformat(), task.is_archived,
            task.status_locked_by_director, assignments]
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()


def query_url(request, **changes):
    query = request.GET.copy()
    for key, value in changes.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = str(value)
    return '?' + query.urlencode()


def filtered_tasks(request, board=False, archived=False):
    user = request.user
    now = timezone.now()
    today = timezone.localdate()
    base = visible_tasks(user).filter(is_archived=archived)
    if not archived: base = base.exclude(event_work__event__workspace__phase='cancelled')
    f = {key: request.GET.get(key, '').strip() for key in
         ['search', 'department', 'assigned_to', 'status', 'priority', 'deadline', 'sort']}
    if f['status'] == 'overdue':
        f['status'] = ''; f['deadline'] = 'overdue'
    if f['status'] not in dict(Task.STATUS_CHOICES): f['status'] = ''
    if f['priority'] not in dict(Task.PRIORITY_CHOICES): f['priority'] = ''
    if f['deadline'] not in ['overdue', 'today', 'week', 'none']: f['deadline'] = ''
    if f['sort'] not in ['deadline', 'newest', 'priority']: f['sort'] = 'deadline'
    for key in ['department', 'assigned_to']:
        if not f[key].isascii() or not f[key].isdigit() or len(f[key]) > 12:
            f[key] = ''
    qs = base
    if f['search']: qs = qs.filter(Q(title__icontains=f['search']) | Q(description__icontains=f['search']))
    if f['department']: qs = qs.filter(Q(department_id=f['department']) | Q(departments__id=f['department']))
    if f['assigned_to']: qs = qs.filter(assigned_to__id=f['assigned_to'])
    if request.GET.get('mine') == '1': qs = qs.filter(assigned_to=user)
    if f['status']: qs = qs.filter(status=f['status'])
    if f['priority']: qs = qs.filter(priority=f['priority'])
    if f['deadline'] == 'overdue': qs = qs.filter(deadline__lt=now).exclude(status='completed')
    elif f['deadline'] == 'today': qs = qs.filter(deadline__date=today)
    elif f['deadline'] == 'week': qs = qs.filter(deadline__date__gte=today, deadline__date__lte=today + timedelta(days=6))
    elif f['deadline'] == 'none': qs = qs.filter(deadline__isnull=True)
    if request.GET.get('only_parents') == '1': qs = qs.filter(subtasks__isnull=False)
    if board and request.GET.get('show_subtasks') != '1': qs = qs.filter(parent_task__isnull=True)
    qs = qs.distinct().select_related('department', 'created_by', 'event_work__event__workspace').prefetch_related(
        'assigned_to', 'departments', 'assignments__user').annotate(
        attachment_count=Count('files', distinct=True), comment_count=Count('comments', distinct=True))
    if f['sort'] == 'newest': qs = qs.order_by('-created_at', '-pk')
    elif f['sort'] == 'priority':
        qs = qs.annotate(priority_order=Case(When(priority='urgent', then=Value(0)), When(priority='high', then=Value(1)), When(priority='medium', then=Value(2)), default=Value(3), output_field=IntegerField())).order_by('priority_order', F('deadline').asc(nulls_last=True), '-pk')
    else: qs = qs.order_by(F('deadline').asc(nulls_last=True), '-pk')
    return qs, f, base


def workspace_context(request, board=False, archived=False):
    user = request.user
    now = timezone.now()
    today = timezone.localdate()
    qs, f, base = filtered_tasks(request, board, archived)
    def enrich(task):
        task.ui_assignment = next((a for a in task.assignments.all() if a.user_id == user.pk), None)
        from events.collaboration import linked_task, is_closed
        link = linked_task(task)
        closed = bool(link and is_closed(link.event))
        task.ui_can_change = not task.is_archived and not closed and (task.ui_assignment is not None or user.is_director())
        task.ui_can_edit = can_edit_task(user, task)
        task.ui_bulk_select = user.is_director() and (archived or task.status == 'completed')
        task.ui_version = task_version(task)
        task.ui_done = sum(a.status == 'completed' for a in task.assignments.all())
        task.ui_total = len(task.assignments.all())
        return task
    if user.is_director():
        departments = Department.objects.all()
        users = get_user_model().objects.filter(is_active=True)
    else:
        departments = Department.objects.filter(pk=user.department_id) if user.department_id else Department.objects.none()
        users = get_user_model().objects.filter(is_active=True, department_id=user.department_id) if user.department_id else get_user_model().objects.filter(pk=user.pk)
    stats = base.aggregate(total=Count('pk', distinct=True), overdue=Count('pk', filter=Q(deadline__lt=now) & ~Q(status='completed'), distinct=True), active=Count('pk', filter=~Q(status='completed'), distinct=True), completed=Count('pk', filter=Q(status='completed'), distinct=True))
    context = {'filters': f, 'departments': departments, 'users': users,
               'status_choices': Task.STATUS_CHOICES, 'priority_choices': Task.PRIORITY_CHOICES,
               'workspace_stats': stats, 'is_archive': archived,
               'completed_query': query_url(request, status='completed', page=None), 'workspace_count': qs.count(),
               'filter_query': request.GET.urlencode(),
               'mine_active': request.GET.get('mine') == '1',
               'show_subtasks': request.GET.get('show_subtasks') == '1',
               'only_parents': request.GET.get('only_parents') == '1',
               'board_mode': board}
    if board:
        columns = []
        for status, label in Task.STATUS_CHOICES:
            subset = qs.filter(status=status)
            count = subset.count()
            columns.append({'status': status, 'label': label, 'count': count,
                            'tasks': [enrich(t) for t in subset[:60]],
                            'more': count > 60,
                            'list_query': query_url(request, status=status, page=None)})
        context['board_columns'] = columns
    else:
        page = Paginator(qs, 25).get_page(request.GET.get('page'))
        context['tasks'] = [enrich(t) for t in page]
        context['task_page'] = page
        context['task_previous'] = query_url(request, page=page.previous_page_number()) if page.has_previous() else None
        context['task_next'] = query_url(request, page=page.next_page_number()) if page.has_next() else None
        checks = ChecklistTask.objects.none() if archived else ChecklistTask.objects.filter(responsible=user).select_related('block__checklist')
        if f['search']: checks = checks.filter(Q(title__icontains=f['search']) | Q(comment__icontains=f['search']))
        mapping = {'assigned':'not_started', 'in_progress':'in_progress', 'pending':'on_review', 'completed':'completed'}
        if f['status']: checks = checks.filter(status=mapping[f['status']])
        if f['priority'] or request.GET.get('only_parents') == '1': checks = checks.none()
        if f['assigned_to'] and int(f['assigned_to']) != user.pk: checks = checks.none()
        if f['department']: checks = checks.filter(responsible__department_id=f['department'])
        if f['deadline'] == 'overdue': checks = checks.filter(deadline__lt=today, is_completed=False).exclude(status='completed')
        elif f['deadline'] == 'today': checks = checks.filter(deadline=today)
        elif f['deadline'] == 'week': checks = checks.filter(deadline__gte=today, deadline__lte=today + timedelta(days=6))
        elif f['deadline'] == 'none': checks = checks.filter(deadline__isnull=True)
        check_page = Paginator(checks.order_by(F('deadline').asc(nulls_last=True), 'pk'), 10).get_page(request.GET.get('check_page'))
        context['checklist_tasks'] = check_page
        context['check_previous'] = query_url(request, check_page=check_page.previous_page_number()) if check_page.has_previous() else None
        context['check_next'] = query_url(request, check_page=check_page.next_page_number()) if check_page.has_next() else None
    return context
