"""One calculation path for the dashboard and its Excel report."""
from datetime import datetime, time, timedelta
from django import forms
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from accounts.models import Department, User
from tasks.models import Task, TaskAssignee
from events.models import Meropriyatie


class AnalyticsFilterForm(forms.Form):
    period = forms.ChoiceField(label='Период', choices=[('30', '30 дней'), ('90', '90 дней'), ('14', '14 дней'), ('custom', 'Свои даты')])
    start = forms.DateField(label='С', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(label='По', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    department = forms.ChoiceField(label='Отдел', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].choices = [('', 'Все отделы')] + [(str(d.pk), d.name) for d in Department.objects.order_by('name')]
        for field in self.fields.values(): field.widget.attrs['class'] = 'form-control'

    def clean(self):
        data = super().clean()
        today = timezone.localdate()
        if data.get('period') == 'custom':
            start, end = data.get('start'), data.get('end')
            if not start or not end: raise forms.ValidationError('Укажите обе даты периода.')
            if end < start: raise forms.ValidationError('Начало периода должно быть не позже конца.')
            if (end - start).days >= 366: raise forms.ValidationError('Выберите период не длиннее 366 дней.')
            if end > today: raise forms.ValidationError('Конец отчётного периода не может быть в будущем.')
        else:
            start, end = today - timedelta(days=int(data.get('period') or '30') - 1), today
        data['start'], data['end'] = start, end
        return data


def report(data):
    now = timezone.now()
    start, end = data['start'], data['end']
    begin = timezone.make_aware(datetime.combine(start, time.min))
    finish = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min))
    qs = Task.objects.filter(is_archived=False).exclude(event_work__event__workspace__phase='cancelled')
    dept_id = data.get('department')
    if dept_id: qs = qs.filter(Q(department_id=dept_id) | Q(departments__pk=dept_id)).distinct()
    stats = qs.aggregate(total=Count('pk', distinct=True), completed=Count('pk', filter=Q(status='completed'), distinct=True),
        assigned=Count('pk', filter=Q(status='assigned'), distinct=True), in_progress=Count('pk', filter=Q(status='in_progress'), distinct=True),
        pending=Count('pk', filter=Q(status='pending'), distinct=True), overdue=Count('pk', filter=Q(deadline__lt=now) & ~Q(status='completed'), distinct=True),
        completed_period=Count('pk', filter=Q(status='completed', completed_at__gte=begin, completed_at__lt=finish), distinct=True),
        created_period=Count('pk', filter=Q(created_at__gte=begin, created_at__lt=finish), distinct=True),
        no_deadline=Count('pk', filter=Q(deadline__isnull=True) & ~Q(status='completed'), distinct=True),
        unassigned=Count('pk', filter=Q(assigned_to__isnull=True) & ~Q(status='completed'), distinct=True))
    stats['active'] = stats['assigned'] + stats['in_progress'] + stats['pending']
    stats['completion_rate'] = round(100 * stats['completed'] / stats['total'], 1) if stats['total'] else 0
    departments = Department.objects.filter(pk=dept_id) if dept_id else Department.objects.all()
    members = dict(User.objects.filter(is_active=True).values('department_id').annotate(n=Count('pk')).values_list('department_id', 'n'))
    dept_stats = []
    for dep in departments.order_by('name'):
        scope = qs.filter(Q(department=dep) | Q(departments=dep))
        counts = scope.aggregate(total=Count('pk', distinct=True), active=Count('pk', filter=~Q(status='completed'), distinct=True),
            completed=Count('pk', filter=Q(status='completed'), distinct=True), overdue=Count('pk', filter=Q(deadline__lt=now) & ~Q(status='completed'), distinct=True))
        counts.update(department=dep, members=members.get(dep.pk, 0))
        counts['completion_rate'] = round(100 * counts['completed'] / counts['total'], 1) if counts['total'] else 0
        dept_stats.append(counts)
    assignments = Q(task_assignments__task_id__in=qs.values('pk'))
    active = assignments & ~Q(task_assignments__task__status='completed') & ~Q(task_assignments__status='completed')
    completed = assignments & Q(task_assignments__status='completed', task_assignments__completed_at__gte=begin, task_assignments__completed_at__lt=finish)
    people = User.objects.filter(is_active=True)
    if dept_id: people = people.filter(department_id=dept_id)
    people = list(people.select_related('department').annotate(
        active_count=Count('task_assignments', filter=active, distinct=True),
        overdue_count=Count('task_assignments', filter=active & Q(task_assignments__task__deadline__lt=now), distinct=True),
        completed_count=Count('task_assignments', filter=completed, distinct=True)
    ).order_by('-overdue_count', '-active_count', 'last_name', 'username'))
    daily_created = {row['day']: row['n'] for row in qs.filter(created_at__gte=begin, created_at__lt=finish).annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('pk', distinct=True))}
    daily_completed = {row['day']: row['n'] for row in qs.filter(status='completed', completed_at__gte=begin, completed_at__lt=finish).annotate(day=TruncDate('completed_at')).values('day').annotate(n=Count('pk', distinct=True))}
    maximum = max([1] + list(daily_created.values()) + list(daily_completed.values()))
    daily = []
    for i in range((end - start).days + 1):
        day = start + timedelta(days=i)
        created, done = daily_created.get(day, 0), daily_completed.get(day, 0)
        daily.append(dict(day=day, created=created, completed=done, created_height=round(100 * created / maximum), completed_height=round(100 * done / maximum)))
    status_rows = [{'label': label, 'count': stats[key]} for key, label in [('assigned', 'Назначена'), ('in_progress', 'В работе'), ('pending', 'На проверке'), ('completed', 'Завершена')]]
    blockers = list(qs.exclude(status='completed').filter(deadline__lt=now).select_related('department').order_by('deadline', 'pk')[:20])
    events = Meropriyatie.objects.all()
    if dept_id: events = events.filter(department_id=dept_id)
    in_period = Q(event_date__gte=begin, event_date__lt=finish)
    event_stats = events.aggregate(
        period=Count('pk', filter=in_period),
        completed=Count('pk', filter=in_period & Q(workspace__phase='completed')),
        cancelled=Count('pk', filter=in_period & Q(workspace__phase='cancelled')),
        upcoming=Count('pk', filter=Q(event_date__gte=now) & (Q(workspace__isnull=True) | Q(workspace__phase__in=['preparing', 'ready'])))
    )
    upcoming = list(events.filter(event_date__gte=now).exclude(workspace__phase__in=['completed', 'cancelled']).select_related('department').order_by('event_date', 'pk')[:5])
    return dict(stats=stats, department_stats=dept_stats, people=people, daily=daily, status_rows=status_rows,
        blockers=blockers, start=start, end=end, department_id=dept_id,
        event_stats=event_stats, upcoming_events=upcoming,
        department_name=Department.objects.get(pk=dept_id).name if dept_id else 'Все отделы')
