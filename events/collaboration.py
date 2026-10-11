"""Object access and version checks for event collaboration."""
import hashlib
import json
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Meropriyatie, EventWorkspace, EventTask, EventActivity


def visible_events(user):
    qs = Meropriyatie.objects.all()
    if user.is_director(): return qs
    scope = Q(responsible=user) | Q(workspace__participants=user) | Q(work_tasks__task__assigned_to=user)
    if user.department_id: scope |= Q(department_id=user.department_id)
    return qs.filter(scope).distinct()


def can_admin(user, event):
    return user.is_director() or (user.is_head() and bool(user.department_id) and user.department_id == event.department_id)


def can_manage(user, event):
    return can_admin(user, event) or event.responsible_id == user.pk


def can_work(user, event):
    return can_manage(user, event) or EventWorkspace.objects.filter(event=event, participants=user).exists()


def is_closed(event):
    if 'workspace' in event._state.fields_cache:
        ws = event._state.fields_cache['workspace']
        return bool(ws and ws.phase in ['completed','cancelled'])
    return EventWorkspace.objects.filter(event=event, phase__in=['completed','cancelled']).exists()


def team(event, active=True):
    scope = Q(event_teams__event=event) | Q(pk=event.responsible_id)
    qs = get_user_model().objects.filter(scope).distinct().select_related('department').order_by('last_name','first_name','username')
    return qs.filter(is_active=True) if active else qs


def event_version(event):
    workspace = EventWorkspace.objects.filter(event=event).first()
    data = [event.updated_at.isoformat(), event.responsible_id,
            workspace.phase if workspace else 'preparing', workspace.location if workspace else '',
            str(workspace.end_date) if workspace else '', str(workspace.updated_at) if workspace else '',
            sorted(workspace.participants.values_list('pk',flat=True)) if workspace else []]
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()


def linked_task(task):
    if 'event_work' in task._state.fields_cache: return task._state.fields_cache['event_work']
    return EventTask.objects.select_related('event').filter(task=task).first()


def log(event, user, message):
    EventActivity.objects.create(event=event, actor=user, message=message[:500])
