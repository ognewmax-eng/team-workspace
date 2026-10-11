"""Opt-in dashboard. Uses existing models; does not change stored preferences."""
from django.db.models import Q, Count, F
from django.shortcuts import render
from django.utils import timezone

from accounts.models import Notification
from tasks.models import Task
from schedule.models import ScheduleEvent, Lesson


def studio_dashboard(request):
    user = request.user
    now = timezone.localtime()
    today = now.date()
    can_use_team = user.is_director() or (user.is_head() and bool(user.department_id))
    team = can_use_team and request.GET.get('scope') == 'department'
    tasks = Task.objects.filter(is_archived=False).exclude(status='completed').exclude(event_work__event__workspace__phase='cancelled')
    if team:
        if not user.is_director():
            tasks = tasks.filter(Q(department_id=user.department_id) | Q(departments__id=user.department_id))
    else:
        tasks = tasks.filter(assigned_to=user)
    tasks = tasks.distinct()
    counts = tasks.aggregate(active=Count('pk', distinct=True),
                             overdue=Count('pk', filter=Q(deadline__lt=now), distinct=True))
    from schedule.planner import visible_events
    events = visible_events(user).distinct().select_related('department')
    today_events = events.filter(start_time__date=today).order_by('start_time')
    # Teaching timetable is separate from ScheduleEvent: include both honestly.
    lessons = Lesson.objects.filter(is_template=False, association__is_active=True,
                                    weekday=today.weekday()).select_related('association')
    if not user.is_director():
        if user.is_head() and user.department_id:
            lessons = lessons.filter(association__specialist__department_id=user.department_id)
        else:
            lessons = lessons.filter(association__specialist=user)
    agenda = [{'time': timezone.localtime(e.start_time).time(), 'title': e.title,
               'subtitle': e.location or (e.department.name if e.department_id else 'Общее расписание'),
               'event_id': e.pk} for e in today_events]
    agenda += [{'time': l.start_time, 'title': l.association.name,
                'subtitle': l.classroom or 'Занятие объединения', 'event_id': None} for l in lessons]
    agenda.sort(key=lambda item: item['time'])
    context = {
        'studio_now': now, 'studio_team': team, 'studio_can_use_team': can_use_team,
        'studio_active': counts['active'], 'studio_overdue': counts['overdue'],
        'studio_tasks': tasks.select_related('department').prefetch_related('assigned_to').order_by(F('deadline').asc(nulls_last=True), '-created_at')[:8],
        'studio_agenda': agenda[:8], 'studio_agenda_count': len(agenda),
        'studio_updates': Notification.objects.filter(user=user).order_by('-created_at')[:4],
        'studio_next_event': events.filter(start_time__gt=now).order_by('start_time').first(),
    }
    return render(request, 'accounts/dashboard_studio.html', context)
