"""Event workspace pages. Every mutation checks event membership on the server."""
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count, F
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_POST
from accounts.models import Department
from tasks.models import Task, TaskAssignee, TaskComment
from tasks.workspace import task_version
from .models import Meropriyatie, MeropriyatieFile, EventWorkspace, EventTask, EventNote
from .forms import MeropriyatieForm
from .work_forms import TeamForm, WorkTaskForm, WorkspaceForm
from .collaboration import visible_events, can_manage, can_admin, can_work, is_closed, team, event_version, log

logger = logging.getLogger(__name__)


def get_event(request, pk, manage=False):
    event = get_object_or_404(visible_events(request.user).select_related('department','responsible','created_by'),pk=pk)
    if manage and not can_manage(request.user,event): raise Http404
    return event


def current(expected, actual):
    if not expected or not constant_time_compare(str(expected), actual):
        raise ValidationError('Данные изменились или страница устарела. Обновите страницу перед повтором.')


def lock_event(event):
    return Meropriyatie.objects.select_for_update().get(pk=event.pk)


def sync_event(event):
    from .views import _sync_meropriyatie_to_schedule
    try: _sync_meropriyatie_to_schedule(event)
    except Exception: logger.warning('Event saved; calendar synchronization failed',exc_info=False)


def notify(users, actor, message, task=None):
    # In-site notifications; existing project delivery preferences are preserved.
    from accounts.models import Notification
    for user in users:
        if user.pk != actor.pk and user.is_active:
            Notification.objects.create(user=user,notification_type='task_assigned' if task else 'task_status_changed',message=message,related_task=task)


def form_page(request,event,form,title):
    return render(request,'events/work_form.html',{'meropriyatie':event,'form':form,'title':title})


@login_required
def list_view(request):
    qs=visible_events(request.user).select_related('department','responsible','workspace').annotate(
        task_total=Count('work_tasks',filter=Q(work_tasks__task__is_archived=False),distinct=True),
        task_done=Count('work_tasks',filter=Q(work_tasks__task__is_archived=False,work_tasks__task__status='completed'),distinct=True),
        task_overdue=Count('work_tasks',filter=Q(work_tasks__task__is_archived=False,work_tasks__task__deadline__lt=timezone.now()) & ~Q(work_tasks__task__status='completed'),distinct=True))
    search=request.GET.get('search','').strip()[:200]
    phase=request.GET.get('phase','');kind=request.GET.get('type','');period=request.GET.get('period','')
    if search:qs=qs.filter(Q(title__icontains=search)|Q(description__icontains=search))
    if phase in dict(EventWorkspace.PHASE_CHOICES):
        qs=qs.filter(Q(workspace__phase=phase)|Q(workspace__isnull=True)) if phase=='preparing' else qs.filter(workspace__phase=phase)
    if kind in dict(Meropriyatie.EVENT_TYPE_CHOICES):qs=qs.filter(event_type=kind)
    if request.GET.get('mine')=='1':qs=qs.filter(Q(responsible=request.user)|Q(workspace__participants=request.user)|Q(work_tasks__task__assigned_to=request.user)).distinct()
    department=request.GET.get('department','')
    if department.isascii() and department.isdigit() and len(department)<13:qs=qs.filter(department_id=int(department))
    else:department=''
    if period=='upcoming':qs=qs.filter(event_date__gte=timezone.now())
    elif period=='past':qs=qs.filter(event_date__lt=timezone.now())
    page=Paginator(qs.order_by('event_date','pk') if period=='upcoming' else qs.order_by('-event_date','-pk'),18).get_page(request.GET.get('page'))
    for event in page:
        event.ui_phase=event.workspace.phase if hasattr(event,'workspace') else 'preparing'
        event.ui_phase_label=dict(EventWorkspace.PHASE_CHOICES)[event.ui_phase]
        event.ui_progress=round(event.task_done*100/event.task_total) if event.task_total else 0
    params=request.GET.copy();params.pop('page',None)
    dept_ids=visible_events(request.user).values_list('department_id',flat=True)
    return render(request,'events/meropriyatie_list.html',{'meropriyatiya':page,'departments':Department.objects.filter(pk__in=dept_ids),
        'phases':EventWorkspace.PHASE_CHOICES,'event_types':Meropriyatie.EVENT_TYPE_CHOICES,'search':search,'phase':phase,'kind':kind,'period':period,
        'department_filter':department,'page_query':params.urlencode(),'can_create':bool(request.user.department_id or request.user.is_director())})


@login_required
def detail_view(request,pk):
    event=get_event(request,pk)
    workspace=EventWorkspace.objects.filter(event=event).first()
    can_edit=can_manage(request.user,event); closed=is_closed(event)
    tasks=Task.objects.filter(event_work__event=event,is_archived=False).select_related('event_work').prefetch_related('assignments__user','assigned_to')
    total=tasks.count();done=tasks.filter(status='completed').count();pending=tasks.filter(status='pending').count()
    overdue=tasks.filter(deadline__lt=timezone.now()).exclude(status='completed').count()
    if request.GET.get('archived')=='1':
        tasks=Task.objects.filter(event_work__event=event,is_archived=True).select_related('event_work').prefetch_related('assignments__user','assigned_to')
    search=request.GET.get('search','').strip()[:200];stage=request.GET.get('stage','');status=request.GET.get('status','')
    if search:tasks=tasks.filter(Q(title__icontains=search)|Q(description__icontains=search))
    if stage in dict(EventTask.STAGE_CHOICES):tasks=tasks.filter(event_work__stage=stage)
    if status in dict(Task.STATUS_CHOICES):tasks=tasks.filter(status=status)
    if request.GET.get('mine')=='1':tasks=tasks.filter(assigned_to=request.user)
    page=Paginator(tasks.order_by(F('deadline').asc(nulls_last=True),'pk').distinct(),24).get_page(request.GET.get('page'))
    for task in page:
        task.ui_assignment=next((a for a in task.assignments.all() if a.user_id==request.user.pk),None)
        task.ui_can_change=not closed and not task.is_archived and (task.ui_assignment is not None or request.user.is_director())
        task.ui_version=task_version(task);task.ui_done=sum(a.status=='completed' for a in task.assignments.all());task.ui_total=len(task.assignments.all())
    members=list(team(event,active=False))
    # Never create a workspace as a side effect of viewing a legacy event.
    version=event_version(event)
    notes=Paginator(event.notes.select_related('author'),15).get_page(request.GET.get('notes_page'))
    phase=workspace.phase if workspace else 'preparing'
    status_choices=Task.STATUS_CHOICES if can_edit else [choice for choice in Task.STATUS_CHOICES if choice[0]!='completed']
    params=request.GET.copy();params.pop('page',None)
    files=list(event.files.select_related('uploaded_by'))
    for file in files: file.ui_name=file.file.name.rsplit('/',1)[-1]
    from .planning import detail_context
    return render(request,'events/meropriyatie_detail.html',dict(detail_context(event,request.user), **{'meropriyatie':event,'workspace':workspace,'can_manage':can_edit,'can_admin':can_admin(request.user,event),
        'can_work':can_work(request.user,event),'closed':closed,'phase':phase,'phase_label':dict(EventWorkspace.PHASE_CHOICES)[phase],
        'team':members,'tasks':page,'task_total':total,'task_done':done,'task_pending':pending,'task_overdue':overdue,'progress':round(done*100/total) if total else 0,
        'notes':notes,'activity':event.activity.select_related('actor')[:12],'version':version,'page_query':params.urlencode(),
        'all_status_choices':Task.STATUS_CHOICES,'search':search,'stage':stage,'status':status,'stages':EventTask.STAGE_CHOICES,'status_choices':status_choices,
        'workspace_form':WorkspaceForm(initial={'phase':phase,'location':workspace.location if workspace else '', 'end_date':workspace.end_date if workspace else None,'version':version}),
        'files':files}))


@login_required
def event_form_view(request,pk=None):
    event=get_event(request,pk,manage=True) if pk else None
    if event is None and not (request.user.is_director() or request.user.department_id):raise Http404
    initial={} if event else {'responsible':request.user.pk,'department':request.user.department_id}
    form=MeropriyatieForm(request.POST or None,instance=event,user=request.user,initial=initial)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                if event:
                    locked=lock_event(event)
                    if not can_manage(request.user,locked):raise Http404
                    current(request.POST.get('version'),event_version(locked))
                item=form.save(commit=False)
                if not event:item.created_by=request.user
                item.save()
                from .planning import save_plan
                save_plan(item,form.cleaned_data)
                ws,_=EventWorkspace.objects.get_or_create(event=item)
                if not item.event_date:
                    ws.end_date=None
                    if ws.phase=='ready':ws.phase='preparing'
                    ws.save()
                if event and locked.responsible_id and locked.responsible_id != item.responsible_id and TaskAssignee.objects.filter(task__event_work__event=item,user_id=locked.responsible_id).exists():
                    ws.participants.add(locked.responsible_id)
                log(item,request.user,'Карточка мероприятия обновлена.' if event else 'Мероприятие создано.')
            sync_event(item)
            messages.success(request,'Мероприятие сохранено.')
            return redirect('meropriyatie_detail',pk=item.pk)
        except ValidationError as exc:form.add_error(None,exc)
    return render(request,'events/meropriyatie_form.html',{'form':form,'meropriyatie':event,'version':request.POST.get('version','') if request.method=='POST' else event_version(event) if event else '',
        'title':'Редактировать мероприятие' if event else 'Создать мероприятие'})


@login_required
def team_view(request,pk):
    event=get_event(request,pk,manage=True)
    workspace=EventWorkspace.objects.filter(event=event).first()
    form=TeamForm(request.POST or None,initial={'participants':list(workspace.participants.values_list('pk',flat=True)) if workspace else [],'version':event_version(event)})
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                locked=lock_event(event)
                if not can_manage(request.user,locked):raise Http404
                current(form.cleaned_data['version'],event_version(locked))
                chosen=form.cleaned_data['participants'];ids={u.pk for u in chosen}
                if locked.responsible_id:ids.add(locked.responsible_id)
                used=set(TaskAssignee.objects.filter(task__event_work__event=locked).values_list('user_id',flat=True))
                if used-ids:raise ValidationError('Нельзя исключить исполнителя назначенных задач. Сначала переназначьте его задачи, в том числе архивные.')
                ws,_=EventWorkspace.objects.get_or_create(event=locked);before=set(ws.participants.values_list('pk',flat=True));ws.participants.set(chosen);ws.save()
                log(locked,request.user,'Обновлена команда мероприятия.')
                notify([u for u in chosen if u.pk not in before],request.user,'Вы добавлены в команду мероприятия «%s».'%locked.title)
            sync_event(locked);messages.success(request,'Команда обновлена.');return redirect('meropriyatie_detail',pk=event.pk)
        except ValidationError as exc:form.add_error(None,exc)
    return form_page(request,event,form,'Команда мероприятия')


@login_required
@require_POST
def workspace_update(request,pk):
    event=get_event(request,pk,manage=True);form=WorkspaceForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                locked=lock_event(event)
                if not can_manage(request.user,locked):raise Http404
                current(form.cleaned_data['version'],event_version(locked))
                end=form.cleaned_data['end_date']
                if end and (not locked.event_date or end<=locked.event_date):raise ValidationError('Сначала укажите точное начало. Окончание должно быть позже начала.')
                if form.cleaned_data['phase']=='ready' and (not locked.event_date or not locked.responsible_id or not form.cleaned_data['location']):
                    raise ValidationError('Для готовности укажите точную дату, ответственного и место проведения.')
                if form.cleaned_data['phase']=='completed' and Task.objects.filter(event_work__event=locked,is_archived=False).exclude(status='completed').exists():
                    raise ValidationError('Сначала завершите активные задачи мероприятия. При отмене используйте состояние «Отменено».')
                ws,_=EventWorkspace.objects.get_or_create(event=locked)
                for field in ['phase','location','end_date']:setattr(ws,field,form.cleaned_data[field])
                ws.save();log(locked,request.user,'Состояние: %s. Место и окончание обновлены.'%ws.get_phase_display())
            sync_event(locked);messages.success(request,'Параметры мероприятия сохранены.')
        except ValidationError as exc:messages.error(request,'; '.join(exc.messages))
    else:messages.error(request,'Проверьте параметры: '+ '; '.join('%s: %s'%(key,','.join(value)) for key,value in form.errors.items()))
    return redirect('meropriyatie_detail',pk=event.pk)


@login_required
def task_form_view(request,pk,task_id=None):
    event=get_event(request,pk,manage=True)
    if is_closed(event):messages.error(request,'Сначала верните мероприятие в подготовку.');return redirect('meropriyatie_detail',pk=pk)
    link=get_object_or_404(EventTask.objects.select_related('task'),event=event,task_id=task_id) if task_id else None
    task=link.task if link else None
    if task and task.is_archived:raise Http404
    initial={'stage':link.stage if link else 'preparation','assigned_to':list(task.assigned_to.values_list('pk',flat=True)) if task else [],'version':task_version(task) if task else event_version(event)}
    form=WorkTaskForm(request.POST or None,instance=task,event=event,initial=initial)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                locked=lock_event(event)
                if not can_manage(request.user,locked):raise Http404
                if is_closed(locked):raise ValidationError('Мероприятие уже закрыто. Обновите страницу.')
                if task:
                    stored=Task.objects.select_for_update().get(pk=task.pk)
                    current(form.cleaned_data['version'],task_version(stored))
                    if stored.is_archived:raise ValidationError('Задача в архиве.')
                else:current(form.cleaned_data['version'],event_version(locked))
                chosen=list(form.cleaned_data['assigned_to'])
                if set(u.pk for u in chosen)-set(team(locked).values_list('pk',flat=True)):raise ValidationError('Команда изменилась. Обновите страницу.')
                previous=set(task.assigned_to.values_list('pk',flat=True)) if task else set()
                item=form.save(commit=False)
                if not task:item.created_by=request.user
                item.department=locked.department;item.save()
                item.departments.set([locked.department])
                ids={u.pk for u in chosen}
                item.assignments.exclude(user_id__in=ids).delete()
                for u in chosen:TaskAssignee.objects.get_or_create(task=item,user=u)
                item.update_aggregate_status()
                if link:link.stage=form.cleaned_data['stage'];link.save()
                else:EventTask.objects.create(event=locked,task=item,stage=form.cleaned_data['stage'])
                ws,_=EventWorkspace.objects.get_or_create(event=locked);ws.save()
                log(locked,request.user,'Задача %s: «%s».'%('обновлена' if task else 'создана',item.title))
                notify([u for u in chosen if u.pk not in previous],request.user,'Вам назначена задача «%s» по мероприятию «%s».'%(item.title,locked.title),item)
            from tasks.views import sync_task_to_schedule
            try:sync_task_to_schedule(item)
            except Exception:logger.warning('Event task saved; schedule sync failed',exc_info=False)
            messages.success(request,'Задача сохранена. Она также доступна в разделе «Задачи».');return redirect('meropriyatie_detail',pk=event.pk)
        except ValidationError as exc:form.add_error(None,exc)
    return form_page(request,event,form,'Изменить задачу мероприятия' if task else 'Новая задача мероприятия')


@login_required
@require_POST
def review_task(request,pk,task_id):
    event=get_event(request,pk,manage=True)
    try:
        with transaction.atomic():
            locked=lock_event(event)
            if not can_manage(request.user,locked):raise Http404
            if is_closed(locked):raise ValidationError('Мероприятие закрыто.')
            task=get_object_or_404(Task.objects.select_for_update(),event_work__event=locked,pk=task_id,is_archived=False)
            current(request.POST.get('version'),task_version(task))
            if task.status_locked_by_director and not request.user.is_director():raise ValidationError('Статус зафиксирован директором. Проверку этой задачи должен выполнить директор.')
            if task.status!='pending' or task.assignments.exclude(status__in=['pending','completed']).exists() or not task.assignments.filter(status='pending').exists():
                raise ValidationError('Задача ещё не готова к проверке. Все исполнители должны отправить результат.')
            action=request.POST.get('action');text=request.POST.get('comment','').strip()
            if action not in ['approve','return']:raise ValidationError('Некорректное действие.')
            if action=='return' and not text:raise ValidationError('Укажите, что нужно доработать.')
            if len(text)>4000:raise ValidationError('Комментарий слишком длинный.')
            for assignment in task.assignments.filter(status='pending'):
                assignment.status='completed' if action=='approve' else 'in_progress';assignment.save()
            if task.status_locked_by_director:
                task.status_locked_by_director=False;task.save(update_fields=['status_locked_by_director'])
            task.update_aggregate_status()
            result='Результат принят.' if action=='approve' else 'Возвращено на доработку.'
            TaskComment.objects.create(task=task,author=request.user,text=result+(' '+text if text else ''))
            log(locked,request.user,'%s Задача «%s».'%(result,task.title))
        messages.success(request,result)
    except ValidationError as exc:messages.error(request,'; '.join(exc.messages))
    return redirect('meropriyatie_detail',pk=pk)


@login_required
@require_POST
def add_note(request,pk):
    event=get_event(request,pk)
    if not can_work(request.user,event):raise Http404
    text=request.POST.get('text','').strip()
    if not text or len(text)>4000:messages.error(request,'Комментарий должен содержать от 1 до 4000 символов.')
    else:EventNote.objects.create(event=event,author=request.user,text=text);messages.success(request,'Комментарий добавлен.')
    return redirect('meropriyatie_detail',pk=pk)


@login_required
@require_POST
def upload_files(request,pk):
    event=get_event(request,pk)
    if not can_work(request.user,event):raise Http404
    files=request.FILES.getlist('files');description=request.POST.get('description','').strip()
    if not files or len(files)>10 or len(description)>200:
        messages.error(request,'Выберите от 1 до 10 файлов; описание — до 200 символов.')
    else:
        try:
            for upload in files:MeropriyatieFile.objects.create(meropriyatie=event,file=upload,uploaded_by=request.user,description=description)
            log(event,request.user,'Добавлены материалы мероприятия.');messages.success(request,'Файлы добавлены.')
        except (OSError, IOError):
            logger.warning('Event attachment upload failed',exc_info=False);messages.error(request,'Не все файлы удалось сохранить. Проверьте список материалов перед повтором.')
    return redirect('meropriyatie_detail',pk=pk)


@login_required
def delete_view(request,pk):
    event=get_event(request,pk)
    if not can_admin(request.user,event):raise Http404
    if event.work_tasks.exists() or hasattr(event,'budget') or event.import_records.exists():
        messages.error(request,'У мероприятия есть задачи, финансовый учёт или история импорта. Завершите или отмените его вместо удаления.');return redirect('meropriyatie_detail',pk=pk)
    if request.method=='POST':
        with transaction.atomic():
            locked=lock_event(event)
            if locked.work_tasks.exists() or hasattr(locked,'budget') or locked.import_records.exists():messages.error(request,'Добавлены связанные данные. Удаление отменено; используйте состояние «Отменено».');return redirect('meropriyatie_detail',pk=pk)
            locked.schedule_events.all().delete();locked.delete()
        messages.success(request,'Мероприятие удалено.');return redirect('meropriyatie_list')
    return render(request,'events/meropriyatie_confirm_delete.html',{'meropriyatie':event})


@login_required
@require_POST
def archive_task(request,pk,task_id):
    event=get_event(request,pk,manage=True)
    try:
        with transaction.atomic():
            locked=lock_event(event)
            if not can_manage(request.user,locked):raise Http404
            if is_closed(locked):raise ValidationError('Сначала верните мероприятие в подготовку.')
            task=get_object_or_404(Task.objects.select_for_update(),event_work__event=locked,pk=task_id)
            current(request.POST.get('version'),task_version(task))
            action=request.POST.get('action')
            if action not in ['archive','restore']:raise ValidationError('Некорректное действие.')
            task.is_archived=action=='archive';task.save()
            log(locked,request.user,('Архивирована' if task.is_archived else 'Восстановлена')+' задача «%s».'%task.title)
        messages.success(request,'Задача архивирована.' if task.is_archived else 'Задача восстановлена.')
    except ValidationError as exc:messages.error(request,'; '.join(exc.messages))
    return redirect('meropriyatie_detail',pk=pk)
