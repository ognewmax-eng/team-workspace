"""Calendar projection and safe management of recurring weekly lessons."""
import hashlib
import json
import logging
from datetime import datetime, date, timedelta
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction, OperationalError
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_GET

from accounts.models import Department
from tasks.workspace import visible_tasks
from .models import ScheduleEvent, Association, Lesson, ScheduleTemplate


def visible_associations(user):
    qs = Association.objects.filter(is_active=True)
    if user.is_director(): return qs
    scope = Q(specialist=user)
    if user.is_head() and user.department_id: scope |= Q(department_id=user.department_id)
    return qs.filter(scope).distinct()


def visible_events(user):
    qs = ScheduleEvent.objects.all()
    if not user.is_director():
        scope = Q(created_by=user) | Q(participants=user)
        if user.department_id: scope |= Q(department_id=user.department_id)
        from events.collaboration import visible_events as visible_meropriyatiya
        scope |= Q(related_meropriyatie__in=visible_meropriyatiya(user))
        qs = qs.filter(scope).distinct()
    return qs.filter(Q(related_task__isnull=True) | Q(related_task__in=visible_tasks(user))).exclude(related_meropriyatie__workspace__phase='cancelled').exclude(related_task__event_work__event__workspace__phase='cancelled')


def can_edit_event(user, event):
    if event.related_task_id or event.related_meropriyatie_id: return False
    return user.is_director() or event.created_by_id == user.pk or (user.is_head() and user.department_id == event.department_id)


def own_association(user, pk):
    if user.is_director(): raise Http404
    return get_object_or_404(Association, pk=pk, specialist=user, is_active=True)


def numeric(value):
    value = str(value or '')
    if not value.isascii() or not value.isdigit() or len(value) > 12:
        raise ValidationError('Некорректный идентификатор.')
    return int(value)


def parse_day(value, default=None):
    try:
        parsed = date.fromisoformat(str(value)[:10])
        if not 1900 <= parsed.year <= 2100: raise ValueError
        return parsed
    except (ValueError, TypeError):
        if default is not None: return default
        raise ValidationError('Некорректная дата.')


def lesson_data(lesson):
    return {'id': lesson.pk, 'weekday': lesson.weekday, 'start_time': lesson.start_time.strftime('%H:%M'),
            'end_time': lesson.end_time.strftime('%H:%M'), 'classroom': lesson.classroom, 'note': lesson.note,
            'association_name': lesson.association.name, 'version': version(lesson)}


def version(lesson):
    payload = [lesson.pk, lesson.association_id, lesson.weekday, str(lesson.start_time), str(lesson.end_time), lesson.classroom, lesson.note, str(lesson.updated_at)]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def week_version(association):
    values = [(l.pk, version(l)) for l in association.lessons.filter(is_template=False).order_by('pk')]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def check_version(expected, actual):
    if expected and not constant_time_compare(str(expected), actual):
        raise StaleChange('Расписание изменилось. Обновите страницу перед повторной попыткой.')


class StaleChange(Exception): pass


def api(methods):
    def decorate(fn):
        @login_required
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods: return JsonResponse({'success': False, 'error': 'Метод не разрешён.'}, status=405)
            try:
                data = json.loads(request.body or '{}')
                if not isinstance(data, dict): raise ValidationError('Ожидался объект данных.')
                with transaction.atomic():
                    # All lesson mutations share a lock; SQLite serializes writes itself.
                    Department.objects.select_for_update().order_by('pk').first()
                    return fn(request, data, *args, **kwargs)
            except Http404:
                return JsonResponse({'success': False, 'error': 'Объект не найден или недоступен.'}, status=404)
            except (StaleChange, OperationalError) as exc:
                msg = str(exc) if isinstance(exc, StaleChange) else 'Расписание сейчас изменяется. Обновите страницу и повторите.'
                return JsonResponse({'success': False, 'error': msg}, status=409)
            except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
                msg = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Проверьте формат данных.'
                return JsonResponse({'success': False, 'error': msg}, status=400)
        return wrapped
    return decorate


def normalized_room(room): return ' '.join(room.split()).casefold()


def validate_lesson(lesson, skip_ids=(), proposed=()):
    if isinstance(lesson.weekday, bool) or not 0 <= lesson.weekday <= 6:
        raise ValidationError('День недели должен быть от понедельника до воскресенья.')
    if lesson.end_time <= lesson.start_time: raise ValidationError('Окончание должно быть позже начала в тот же день.')
    if len(lesson.classroom) > 200 or len(lesson.note) > 4000: raise ValidationError('Слишком длинная аудитория или примечание.')
    candidates = Lesson.objects.filter(is_template=False, weekday=lesson.weekday,
                                       start_time__lt=lesson.end_time, end_time__gt=lesson.start_time,
                                       association__is_active=True).exclude(pk__in=skip_ids).select_related('association')
    for other in list(candidates) + list(proposed):
        if other.weekday != lesson.weekday or other.end_time <= lesson.start_time or other.start_time >= lesson.end_time: continue
        if other.association.specialist_id == lesson.association.specialist_id:
            raise ValidationError('В это время у преподавателя уже есть занятие.')
        if normalized_room(lesson.classroom) and normalized_room(other.classroom) == normalized_room(lesson.classroom):
            raise ValidationError('Эта аудитория уже занята в выбранное время.')


def assign_fields(lesson, data):
    if 'weekday' in data:
        if isinstance(data['weekday'], bool): raise ValidationError('Некорректный день недели.')
        if str(data['weekday']) not in [str(i) for i in range(7)]: raise ValidationError('Некорректный день недели.')
        lesson.weekday = int(data['weekday'])
    for key in ['start_time', 'end_time']:
        if key in data: setattr(lesson, key, datetime.strptime(str(data[key]), '%H:%M').time())
    for key in ['classroom', 'note']:
        if key in data:
            if not isinstance(data[key], str): raise ValidationError('Текстовое поле заполнено неверно.')
            setattr(lesson, key, data[key].strip())
    if not lesson.start_time or not lesson.end_time: raise ValidationError('Укажите начало и окончание занятия.')


@api(['POST'])
def create_lesson(request, data):
    association = own_association(request.user, numeric(data.get('association_id')))
    check_version(data.get('schedule_version'), week_version(association))
    lesson = Lesson(association=association, weekday=0, is_template=False)
    if 'weekday' not in data: raise ValidationError('Выберите день недели.')
    assign_fields(lesson, data); validate_lesson(lesson); lesson.save()
    return JsonResponse({'success': True, 'lesson': lesson_data(lesson)})


@api(['POST'])
def update_lesson(request, data, lesson_id):
    lesson = get_object_or_404(Lesson.objects.select_related('association'), pk=lesson_id, is_template=False)
    own_association(request.user, lesson.association_id); check_version(data.get('version'), version(lesson))
    assign_fields(lesson, data); validate_lesson(lesson, skip_ids=[lesson.pk]); lesson.save()
    return JsonResponse({'success': True, 'lesson': lesson_data(lesson)})


@api(['POST'])
def move_lesson(request, data, lesson_id):
    lesson = get_object_or_404(Lesson.objects.select_related('association'), pk=lesson_id, is_template=False)
    own_association(request.user, lesson.association_id); check_version(data.get('version'), version(lesson))
    start = datetime.strptime(str(data.get('start_time')), '%H:%M').time()
    duration = lesson.get_duration_minutes()
    minute = start.hour * 60 + start.minute + duration
    if duration <= 0 or minute >= 24 * 60: raise ValidationError('Перенос выходит за границы дня. Продолжительность не сокращена.')
    data = dict(data, end_time='%02d:%02d' % (minute // 60, minute % 60))
    assign_fields(lesson, data); validate_lesson(lesson, skip_ids=[lesson.pk]); lesson.save()
    return JsonResponse({'success': True, 'lesson': lesson_data(lesson)})


@api(['POST'])
def duplicate_lesson(request, data, lesson_id):
    original = get_object_or_404(Lesson.objects.select_related('association'), pk=lesson_id, is_template=False)
    own_association(request.user, original.association_id); check_version(data.get('version'), version(original))
    lesson = Lesson(association=original.association, weekday=original.weekday, start_time=original.start_time,
                    end_time=original.end_time, classroom=original.classroom, note=original.note, is_template=False)
    assign_fields(lesson, data); validate_lesson(lesson); lesson.save()
    return JsonResponse({'success': True, 'lesson': lesson_data(lesson)})


@api(['DELETE'])
def delete_lesson(request, data, lesson_id):
    lesson = get_object_or_404(Lesson.objects.select_related('association'), pk=lesson_id, is_template=False)
    own_association(request.user, lesson.association_id); check_version(data.get('version'), version(lesson))
    lesson.delete(); return JsonResponse({'success': True})


def snapshot(association, user, name, description=''):
    lessons = list(association.lessons.filter(is_template=False))
    if not lessons: raise ValidationError('Нет занятий для сохранения в шаблон.')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200: raise ValidationError('Название шаблона: от 1 до 200 символов.')
    if not isinstance(description, str) or len(description) > 4000: raise ValidationError('Слишком длинное описание.')
    template = ScheduleTemplate.objects.create(association=association, created_by=user, name=name.strip(), description=description)
    for lesson in lessons:
        Lesson.objects.create(association=association, weekday=lesson.weekday, start_time=lesson.start_time,
                              end_time=lesson.end_time, classroom=lesson.classroom, note=lesson.note, is_template=True, template=template)
    return template


@api(['POST'])
def create_template(request, data):
    association = own_association(request.user, numeric(data.get('association_id')))
    check_version(data.get('schedule_version'), week_version(association))
    template = snapshot(association, request.user, data.get('name'), data.get('description', ''))
    return JsonResponse({'success': True, 'template': {'id': template.pk, 'name': template.name, 'lessons_count': template.lessons.count()}})


@api(['POST'])
def apply_template(request, data):
    association = own_association(request.user, numeric(data.get('association_id')))
    check_version(data.get('schedule_version'), week_version(association))
    template = get_object_or_404(ScheduleTemplate, pk=numeric(data.get('template_id')), association=association)
    replace = data.get('replace_existing', False)
    if not isinstance(replace, bool): raise ValidationError('Неверный режим применения шаблона.')
    originals = list(association.lessons.filter(is_template=False))
    skip = [l.pk for l in originals] if replace else []
    proposed = []
    for item in template.lessons.order_by('weekday', 'start_time'):
        new = Lesson(association=association, weekday=item.weekday, start_time=item.start_time,
                     end_time=item.end_time, classroom=item.classroom, note=item.note, is_template=False)
        validate_lesson(new, skip_ids=skip, proposed=proposed); proposed.append(new)
    if not proposed: raise ValidationError('Шаблон пуст. Расписание не изменено.')
    backup = None
    if replace and originals:
        backup = snapshot(association, request.user, 'До замены · ' + timezone.localtime().strftime('%d.%m.%Y %H:%M'))
        association.lessons.filter(is_template=False).delete()
    for new in proposed: new.save()
    return JsonResponse({'success': True, 'lessons': [lesson_data(l) for l in proposed], 'backup_template': backup.pk if backup else None})


@api(['POST'])
def clear_schedule(request, data):
    association = own_association(request.user, numeric(data.get('association_id')))
    check_version(data.get('schedule_version'), week_version(association))
    backup = snapshot(association, request.user, 'До очистки · ' + timezone.localtime().strftime('%d.%m.%Y %H:%M'))
    deleted, _ = association.lessons.filter(is_template=False).delete()
    return JsonResponse({'success': True, 'deleted_count': deleted, 'backup_template': backup.pk})


@api(['DELETE'])
def delete_template(request, data, template_id):
    template = get_object_or_404(ScheduleTemplate, pk=template_id)
    own_association(request.user, template.association_id)
    template.delete(); return JsonResponse({'success': True})


@login_required
@require_GET
def template_preview(request, template_id):
    template = get_object_or_404(ScheduleTemplate, pk=template_id, association__in=visible_associations(request.user))
    return JsonResponse({'name': template.name, 'lessons': [lesson_data(l) for l in template.lessons.select_related('association')]})


def calendar_data(request):
    today = timezone.localdate()
    start = parse_day(request.GET.get('start') or request.GET.get('date') or (today - timedelta(days=today.weekday())).isoformat())
    end = parse_day(request.GET.get('end') or (start + timedelta(days=7)).isoformat())
    if end <= start or (end-start).days > 62: raise ValidationError('Выберите период от 1 до 62 дней.')
    associations = visible_associations(request.user).select_related('specialist','department')
    events = visible_events(request.user).select_related('department')
    department = request.GET.get('department'); teacher = request.GET.get('teacher'); association = request.GET.get('association')
    if department:
        pk = numeric(department); associations = associations.filter(department_id=pk); events = events.filter(department_id=pk)
    if teacher:
        pk = numeric(teacher); associations = associations.filter(specialist_id=pk); events = events.filter(Q(participants__id=pk)|Q(created_by_id=pk)).distinct()
    if association:
        associations = associations.filter(pk=numeric(association)); events = events.none()
    if request.GET.get('mine') == '1':
        associations = associations.filter(specialist=request.user); events = events.filter(Q(created_by=request.user)|Q(participants=request.user)).distinct()
    layers = request.GET.getlist('layer') if request.GET.get('layers_set') == '1' else (request.GET.getlist('layer') or ['lesson','meeting','event','task','other'])
    events = events.filter(event_type__in=layers)
    if request.GET.get('finished') != '1': events = events.exclude(related_task__status='completed').exclude(related_task__is_archived=True)
    begin = timezone.make_aware(datetime.combine(start, datetime.min.time()))
    finish = timezone.make_aware(datetime.combine(end, datetime.min.time()))
    events = events.filter(start_time__lt=finish, end_time__gt=begin)
    result=[]
    colors={'lesson':'#6a86bc','meeting':'#b18a50','event':'#629a82','task':'#9470c0','other':'#858ba0'}
    for event in events:
        result.append({'id':'event-%s'%event.pk,'title':event.title,
                       'start':timezone.localtime(event.start_time).strftime('%Y-%m-%dT%H:%M:%S'),
                       'end':timezone.localtime(event.end_time).strftime('%Y-%m-%dT%H:%M:%S'),
                       'url':reverse('schedule_event_detail',args=[event.pk]),'backgroundColor':colors.get(event.event_type,'#858ba0'),
                       'borderColor':colors.get(event.event_type,'#858ba0'),
                       'extendedProps':{'type':event.get_event_type_display(),'location':event.location,'kind':'event','description':event.description}})
    if 'lesson' in layers:
        lessons=list(Lesson.objects.filter(association__in=associations,is_template=False).select_related('association'))
        for offset in range((end-start).days):
            day=start+timedelta(days=offset)
            for lesson in lessons:
                if lesson.weekday!=day.weekday(): continue
                result.append({'id':'lesson-%s-%s'%(lesson.pk,day),'title':lesson.association.name,
                               'start':'%sT%s'%(day,lesson.start_time.strftime('%H:%M:%S')),
                               'end':'%sT%s'%(day,lesson.end_time.strftime('%H:%M:%S')),
                               'url':reverse('lessons_schedule')+'?association=%s&lesson=%s'%(lesson.association_id,lesson.pk),
                               'backgroundColor':colors['lesson'],'borderColor':colors['lesson'],
                               'extendedProps':{'type':'Занятие · типовая неделя','kind':'lesson','location':lesson.classroom,'description':lesson.note}})
    if len(result)>3000: raise ValidationError('Слишком много событий. Сузьте период или выберите отдел.')
    return sorted(result,key=lambda item:item['start'])


def calendar_context(request):
    associations = visible_associations(request.user).select_related('specialist','department')
    departments = Department.objects.all() if request.user.is_director() else Department.objects.filter(pk=request.user.department_id)
    from django.contrib.auth import get_user_model
    teachers=get_user_model().objects.filter(pk__in=associations.values('specialist_id')).order_by('last_name','first_name')
    initial=parse_day(request.GET.get('date'), default=timezone.localdate())
    if request.GET.get('month') and request.GET.get('year'):
        try: initial=date(int(request.GET['year']),int(request.GET['month']),1)
        except (ValueError,OverflowError): pass
    return {'associations':associations,'departments':departments,'teachers':teachers,
            'calendar_initial':initial.isoformat(),'calendar_now':timezone.localtime().strftime('%Y-%m-%dT%H:%M:%S'),
            'selected_layers': request.GET.getlist('layer') if request.GET.get('layers_set') == '1' else [value for value, label in ScheduleEvent.EVENT_TYPE_CHOICES],'calendar_timezone':timezone.localtime().strftime('%Z · UTC%z'),
            'event_types':ScheduleEvent.EVENT_TYPE_CHOICES,'can_create_event':request.user.is_director() or bool(request.user.department_id)}


def lessons_context(request):
    associations=visible_associations(request.user).select_related('specialist','department').order_by('name')
    selected=None
    if request.GET.get('association'):
        try: selected=associations.filter(pk=numeric(request.GET['association'])).first()
        except ValidationError: pass
    elif associations.count()==1: selected=associations.first()
    lessons=list(Lesson.objects.filter(association=selected,is_template=False).select_related('association').order_by('weekday','start_time')) if selected else []
    days=[]
    for weekday,label in Lesson.WEEKDAY_CHOICES:
        entries=[]
        for lesson in lessons:
            if lesson.weekday==weekday:
                lesson.ui_version=version(lesson); entries.append(lesson)
        days.append({'weekday':weekday,'label':label,'lessons':entries})
    return {'associations':associations,'selected_association':selected,'lessons':lessons,'lesson_days':days,
            'lessons_payload':[lesson_data(l) for l in lessons],
            'templates':ScheduleTemplate.objects.filter(association=selected),
            'can_edit_schedule':bool(selected and selected.specialist_id==request.user.pk and not request.user.is_director()),
            'schedule_version':week_version(selected) if selected else '',
            'total_minutes':sum(l.get_duration_minutes() for l in lessons),'lesson_count':len(lessons),
            'weekday_choices':Lesson.WEEKDAY_CHOICES,'can_export_all_kmf':request.user.is_director() or request.user.is_head()}

@login_required
def delete_event(request, event_id):
    from django.shortcuts import redirect
    from django.contrib import messages
    if request.method != 'POST': return JsonResponse({'error':'Метод не разрешён.'}, status=405)
    event=get_object_or_404(visible_events(request.user),pk=event_id)
    if not can_edit_event(request.user,event): raise Http404
    try:
        from accounts.google_calendar import delete_schedule_event_from_google_calendar
        delete_schedule_event_from_google_calendar(event)
    except Exception:
        logging.getLogger(__name__).warning('External calendar deletion failed',exc_info=False)
    event.delete();messages.success(request,'Событие удалено.');return redirect('schedule_main')
