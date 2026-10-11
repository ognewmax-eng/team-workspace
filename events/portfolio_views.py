from collections import Counter
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q,Count,F,Case,When,IntegerField
from django.db.models.functions import ExtractYear,ExtractMonth
from django.http import Http404
from django.shortcuts import render,redirect
from django.utils import timezone
from accounts.models import Department
from tasks.models import Task,TaskAssignee
from .models import Meropriyatie,EventWorkspace,EventTask
from .collaboration import visible_events,can_manage,is_closed,team,event_version,log
from .planning import MONTHS,decorate,finance_scope,budget_totals
from .importing import can_import
from .work_views import get_event,lock_event,current


def filtered(request):
    now=timezone.now();today=timezone.localdate()
    qs=visible_events(request.user).select_related('department','responsible','workspace','plan').annotate(
        p_year=Case(When(event_date__isnull=True,then=F('plan__year')),default=ExtractYear('event_date',tzinfo=timezone.get_current_timezone()),output_field=IntegerField()),
        p_start=Case(When(event_date__isnull=True,then=F('plan__month_start')),default=ExtractMonth('event_date',tzinfo=timezone.get_current_timezone()),output_field=IntegerField()),
        p_end=Case(When(event_date__isnull=True,then=F('plan__month_end')),default=ExtractMonth('event_date',tzinfo=timezone.get_current_timezone()),output_field=IntegerField()),
        task_total=Count('work_tasks',filter=Q(work_tasks__task__is_archived=False),distinct=True),
        task_done=Count('work_tasks',filter=Q(work_tasks__task__is_archived=False,work_tasks__task__status='completed'),distinct=True),
        task_overdue=Count('work_tasks',filter=Q(work_tasks__task__is_archived=False,work_tasks__task__deadline__lt=now)&~Q(work_tasks__task__status='completed'),distinct=True))
    fields={k:request.GET.get(k,'')[:200] for k in ['search','phase','type','period','department','month','quarter','year','view','needs']}
    year=request.GET.get('year',str(today.year))
    if year!='all':
        if not year.isascii() or not year.isdigit() or len(year)!=4 or not 2000<=int(year)<=2100:year=str(today.year)
        qs=qs.filter(p_year=int(year))
    fields['year']=year
    if fields['search']:qs=qs.filter(Q(title__icontains=fields['search'])|Q(description__icontains=fields['search'])|Q(plan__organizer__icontains=fields['search']))
    if fields['phase'] in dict(EventWorkspace.PHASE_CHOICES):
        qs=qs.filter(Q(workspace__phase='preparing')|Q(workspace__isnull=True)) if fields['phase']=='preparing' else qs.filter(workspace__phase=fields['phase'])
    if fields['type'] in dict(Meropriyatie.EVENT_TYPE_CHOICES):qs=qs.filter(event_type=fields['type'])
    value=fields['department']
    if value.isascii() and value.isdigit() and len(value)<13:qs=qs.filter(department_id=int(value))
    else:fields['department']=''
    if request.GET.get('mine')=='1':qs=qs.filter(Q(responsible=request.user)|Q(workspace__participants=request.user)|Q(work_tasks__task__assigned_to=request.user)).distinct()
    month=fields['month']
    if month.isascii() and month.isdigit() and 1<=int(month)<=12:qs=qs.filter(p_start__lte=int(month),p_end__gte=int(month))
    else:fields['month']=''
    quarter=fields['quarter']
    if quarter in ['1','2','3','4']:qs=qs.filter(p_start__lte=int(quarter)*3,p_end__gte=int(quarter)*3-2)
    else:fields['quarter']=''
    if fields['period']=='undated':qs=qs.filter(event_date__isnull=True)
    elif fields['period']=='upcoming':qs=qs.filter(Q(event_date__gte=now)|Q(event_date__isnull=True)&(Q(p_year__gt=today.year)|Q(p_year=today.year,p_end__gte=today.month)))
    elif fields['period']=='past':qs=qs.filter(Q(event_date__lt=now)|Q(event_date__isnull=True)&(Q(p_year__lt=today.year)|Q(p_year=today.year,p_end__lt=today.month)))
    if fields['needs']=='lead':qs=qs.filter(responsible__isnull=True)
    elif fields['needs']=='overdue':qs=qs.filter(task_overdue__gt=0)
    elif fields['needs']=='budget':qs=qs.filter(budget__in=finance_scope(request.user),budget__status='review')
    qs=qs.order_by(F('p_year').asc(nulls_last=True),F('p_start').asc(nulls_last=True),F('event_date').asc(nulls_last=True),'pk')
    return qs,fields


@login_required
def list_view(request):
    qs,fields=filtered(request)
    # Aggregation uses the filtered accessible set, before pagination.
    stats={'total':qs.count(),'undated':qs.filter(event_date__isnull=True).count(),'unassigned':qs.filter(responsible__isnull=True).count(),
        'completed':qs.filter(workspace__phase='completed').count(),'overdue_events':qs.filter(task_overdue__gt=0).count()}
    counts=Counter(qs.values_list('p_start',flat=True))
    maximum=max([1]+list(counts.values()))
    months=[{'number':i,'name':name,'count':counts[i],'width':round(counts[i]*100/maximum)} for i,name in enumerate(MONTHS,1)]
    quarters=[{'number':i,'count':sum(counts[m] for m in range(i*3-2,i*3+1))} for i in range(1,5)]
    sums={'allocated':Decimal('0'),'estimate':Decimal('0'),'actual':Decimal('0'),'paid':Decimal('0'),'missing':0,'count':0}
    for budget in finance_scope(request.user).filter(event__in=qs).prefetch_related('lines'):
        totals=budget_totals(budget);sums['count']+=1
        if totals['allocated'] is None:sums['missing']+=1
        else:sums['allocated']+=totals['allocated']
        for key in ['estimate','actual','paid']:sums[key]+=totals[key]
    page=Paginator(qs,18 if fields['view']!='table' else 40).get_page(request.GET.get('page'))
    for event in page:
        decorate(event,request.user)
        ws=getattr(event,'workspace',None);event.ui_phase=ws.phase if ws else 'preparing'
        event.ui_phase_label=dict(EventWorkspace.PHASE_CHOICES)[event.ui_phase]
        event.ui_progress=round(event.task_done*100/event.task_total) if event.task_total else 0
    params=request.GET.copy();params.pop('page',None)
    if 'year' not in params:params['year']=fields['year']
    dept_ids=visible_events(request.user).values_list('department_id',flat=True)
    years=set(visible_events(request.user).filter(event_date__isnull=False).values_list('event_date',flat=True))
    choices={timezone.localtime(d).year for d in years}
    choices.update(visible_events(request.user).filter(plan__isnull=False).values_list('plan__year',flat=True));choices.add(timezone.localdate().year)
    return render(request,'events/meropriyatie_list.html',dict(fields,meropriyatiya=page,stats=stats,month_bars=months,quarter_counts=quarters,financial=sums,
        departments=Department.objects.filter(pk__in=dept_ids),years=sorted(choices),months=list(enumerate(MONTHS,1)),
        phases=EventWorkspace.PHASE_CHOICES,event_types=Meropriyatie.EVENT_TYPE_CHOICES,kind=fields['type'],department_filter=fields['department'],
        page_query=params.urlencode(),can_create=bool(request.user.department_id or request.user.is_director()),can_import=can_import(request.user)))


@login_required
def export_view(request):
    qs,fields=filtered(request)
    if qs.count()>10000:raise Http404
    from .excel import export_events
    return export_events(qs)


PRESETS=[('brief','Согласовать цель, аудиторию и программу','preparation'),('budget','Подготовить смету и закупки','preparation'),
    ('venue','Подготовить площадку и оборудование','preparation'),('media','Подготовить анонс и регистрацию','preparation'),
    ('safety','Проверить безопасность и распределить роли','preparation'),('delivery','Провести мероприятие','delivery'),
    ('report','Собрать результаты, фото и отчёт','followup')]


class PresetForm(forms.Form):
    tasks=forms.MultipleChoiceField(choices=[(key,title) for key,title,stage in PRESETS],widget=forms.CheckboxSelectMultiple,label='Задачи')
    version=forms.CharField(widget=forms.HiddenInput)
    def __init__(self,*args,event=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['assignee']=forms.ModelChoiceField(queryset=team(event),label='Первоначальный исполнитель')
        self.fields['assignee'].help_text='После создания распределите задачи между членами команды.'


@login_required
def presets_view(request,pk):
    event=get_event(request,pk,manage=True)
    if is_closed(event):raise Http404
    form=PresetForm(request.POST or None,event=event,initial={'tasks':[p[0] for p in PRESETS],'version':event_version(event),'assignee':event.responsible_id})
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                locked=lock_event(event)
                if not can_manage(request.user,locked) or is_closed(locked):raise Http404
                current(form.cleaned_data['version'],event_version(locked))
                if not team(locked).filter(pk=form.cleaned_data['assignee'].pk).exists():raise ValidationError('Команда изменилась. Обновите страницу.')
                count=0
                for key,title,stage in PRESETS:
                    if key not in form.cleaned_data['tasks'] or EventTask.objects.filter(event=locked,stage=stage,task__title=title).exists():continue
                    task=Task.objects.create(title=title,department=locked.department,created_by=request.user)
                    task.departments.add(locked.department);TaskAssignee.objects.create(task=task,user=form.cleaned_data['assignee'])
                    EventTask.objects.create(event=locked,task=task,stage=stage);count+=1
                ws,_=EventWorkspace.objects.get_or_create(event=locked);ws.save()
                log(locked,request.user,'Добавлен шаблон подготовки: %s задач. Повторяющиеся задачи пропущены.'%count)
                from .work_views import notify
                if count:notify([form.cleaned_data['assignee']],request.user,'Вам назначены задачи подготовки мероприятия «%s».'%locked.title)
            messages.success(request,'Добавлено задач: %s. Распределите их между специалистами.'%count)
            return redirect('meropriyatie_detail',pk=pk)
        except ValidationError as exc:form.add_error(None,exc)
    return render(request,'events/work_form.html',{'form':form,'meropriyatie':event,'title':'Шаблон задач подготовки'})
