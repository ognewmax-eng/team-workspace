from decimal import Decimal
from hashlib import sha256
import json
from django.db.models import Q
from django.utils import timezone
from .models import EventPlan, EventBudget, EventBudgetLine
from .collaboration import can_manage, can_work

MONTHS = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
ZERO = Decimal('0.00')


def period(event):
    if event.event_date:
        date=timezone.localtime(event.event_date)
        return date.year,date.month,date.month
    plan=getattr(event,'plan',None)
    return (plan.year,plan.month_start,plan.month_end) if plan else (None,None,None)


def period_label(event):
    if event.event_date:return timezone.localtime(event.event_date).strftime('%d.%m.%Y · %H:%M')
    year,start,end=period(event)
    if not year:return 'Срок уточняется'
    return '%s%s %s · дата уточняется'%(MONTHS[start-1], '–'+MONTHS[end-1].lower() if start!=end else '',year)


def save_plan(event,data):
    defaults={name:data.get(name) for name in ['organizer','audience','participants_target','participants_actual','results']}
    for name in ['organizer','audience','results']:defaults[name]=defaults[name] or ''
    defaults.update(year=data['plan_year'],month_start=data['month_start'],month_end=data['month_end'])
    EventPlan.objects.update_or_create(event=event,defaults=defaults)


def budget_totals(budget):
    all_lines=list(budget.lines.all()) if budget else []
    lines=[line for line in all_lines if line.status!='cancelled']
    estimate=sum((line.estimate for line in lines),ZERO)
    actual=sum((line.actual_amount for line in all_lines),ZERO)
    paid=sum((line.paid_amount for line in all_lines),ZERO)
    allocated=budget.allocated if budget else None
    overdue=sum(bool(line.due_date and line.due_date<timezone.localdate() and line.status!='received') for line in lines)
    return {'estimate':estimate,'actual':actual,'paid':paid,'unpaid':actual-paid,'allocated':allocated,
            'estimate_balance':allocated-estimate if allocated is not None else None,
            'remaining':allocated-actual if allocated is not None else None,
            'over_budget':allocated is not None and max(estimate,actual)>allocated,'overdue':overdue,
            'received':sum(line.status=='received' for line in lines),'count':len(lines)}


def finance_version(event):
    budget=EventBudget.objects.filter(event=event).first()
    payload=[event.pk,event.updated_at.isoformat(),budget.updated_at.isoformat() if budget else None,
             list(budget.lines.order_by('pk').values_list('pk','updated_at')) if budget else []]
    return sha256(json.dumps(payload,default=str).encode()).hexdigest()


def finance_scope(user):
    q=Q(event__responsible=user)|Q(event__workspace__participants=user)
    if user.is_director():return EventBudget.objects.all()
    if user.is_head() and user.department_id:q|=Q(event__department_id=user.department_id)
    return EventBudget.objects.filter(q).distinct()


def decorate(event,user):
    event.ui_period=period_label(event)
    event.ui_finance=can_work(user,event)
    event.ui_issues=[]
    if not event.event_date:event.ui_issues.append('Уточнить дату')
    if not event.responsible_id:event.ui_issues.append('Назначить ответственного')
    workspace=getattr(event,'workspace',None)
    if not workspace or not workspace.location:event.ui_issues.append('Указать место')
    if getattr(event,'task_overdue',0):event.ui_issues.append('Просрочены задачи: %s'%event.task_overdue)
    return event


def detail_context(event,user):
    decorate(event,user)
    plan=getattr(event,'plan',None)
    context={'event_plan':plan,'event_period':event.ui_period,'readiness':event.ui_issues}
    if can_work(user,event):
        budget=EventBudget.objects.filter(event=event).first()
        totals=budget_totals(budget)
        context.update(finance_access=True,event_budget=budget,finance_totals=totals)
        if totals['over_budget']:context['readiness'].append('Расходы превышают лимит бюджета')
        if budget and budget.lines.exclude(status='cancelled').exists() and budget.status!='approved':context['readiness'].append('Согласовать смету')
        if totals['overdue']:context['readiness'].append('Просрочены поставки: %s'%totals['overdue'])
    # Show only conflicts that this user may read; never disclose another department's event.
    workspace=getattr(event,'workspace',None)
    if event.event_date and workspace and workspace.location and workspace.end_date:
        from .collaboration import visible_events
        context['location_conflicts']=visible_events(user).filter(workspace__location__iexact=workspace.location,
            event_date__lt=workspace.end_date, workspace__end_date__gt=event.event_date).exclude(pk=event.pk).exclude(workspace__phase='cancelled')[:5]
    return context
