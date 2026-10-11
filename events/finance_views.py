from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_POST
from .models import EventBudget,EventBudgetLine,EventBudgetApproval
from .collaboration import can_work,can_manage,can_admin,log
from .work_views import get_event,lock_event,current
from .finance_forms import BudgetForm,BudgetLineForm
from .planning import budget_totals,finance_version,period_label


def finance_event(request,pk,manage=False):
    event=get_event(request,pk)
    if not (can_manage(request.user,event) if manage else can_work(request.user,event)):raise Http404
    return event


@login_required
def finance_view(request,pk):
    event=finance_event(request,pk)
    budget=EventBudget.objects.filter(event=event).first()
    form=BudgetForm(request.POST or None,instance=budget)
    if request.method=='POST':
        if not can_manage(request.user,event):raise Http404
        if form.is_valid():
            try:
                with transaction.atomic():
                    locked=lock_event(event)
                    if not can_manage(request.user,locked):raise Http404
                    current(request.POST.get('version'),finance_version(locked))
                    item=form.save(commit=False);item.event=locked;item.status='draft';item.save()
                    log(locked,request.user,'Обновлены лимит и источник финансирования. Смета возвращена в черновик.')
                messages.success(request,'Лимит сохранён.');return redirect('event_finance',pk=pk)
            except ValidationError as exc:form.add_error(None,exc)
    return render(request,'events/finance.html',{'meropriyatie':event,'event_period':period_label(event),'budget':budget,
        'form':form,'totals':budget_totals(budget),'lines':budget.lines.all() if budget else [],'version':finance_version(event),
        'can_manage':can_manage(request.user,event),'can_approve':can_admin(request.user,event),
        'approvals':budget.approvals.select_related('approver').order_by('-pk')[:10] if budget else []})


@login_required
def line_view(request,pk,line_id=None):
    event=finance_event(request,pk,manage=True)
    line=get_object_or_404(EventBudgetLine,budget__event=event,pk=line_id) if line_id else None
    form=BudgetLineForm(request.POST or None,instance=line)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                locked=lock_event(event)
                if not can_manage(request.user,locked):raise Http404
                current(request.POST.get('version'),finance_version(locked))
                budget,_=EventBudget.objects.get_or_create(event=locked)
                item=form.save(commit=False);item.budget=budget;item.save()
                budget.status='draft';budget.save()
                log(locked,request.user,'Позиция сметы %s: «%s». Согласование сброшено.'%('обновлена' if line else 'добавлена',item.title))
            messages.success(request,'Позиция сохранена.');return redirect('event_finance',pk=pk)
        except ValidationError as exc:form.add_error(None,exc)
    return render(request,'events/finance_line.html',{'meropriyatie':event,'form':form,'version':request.POST.get('version','') if request.method=='POST' else finance_version(event),'title':'Изменить позицию' if line else 'Добавить позицию сметы'})


@login_required
@require_POST
def review_view(request,pk):
    event=finance_event(request,pk,manage=True)
    try:
        with transaction.atomic():
            locked=lock_event(event)
            if not can_manage(request.user,locked):raise Http404
            current(request.POST.get('version'),finance_version(locked))
            budget=get_object_or_404(EventBudget,event=locked)
            action=request.POST.get('action')
            if action=='submit':
                if budget.status!='draft':raise ValidationError('Смета уже отправлена или согласована.')
                if budget.allocated is None:raise ValidationError('Сначала укажите лимит. Для мероприятия без расходов укажите 0.')
                budget.status='review';message='Смета отправлена на согласование.'
            elif action in ['approve','return']:
                if not can_admin(request.user,locked):raise Http404
                if budget.status!='review':raise ValidationError('Сначала отправьте смету на согласование.')
                if action=='approve':
                    totals=budget_totals(budget)
                    if totals['over_budget']:raise ValidationError('Смета или закупки превышают лимит. Скорректируйте расходы или согласуйте новый лимит.')
                    from django.core.serializers.json import DjangoJSONEncoder
                    import json
                    payload={'allocated':str(budget.allocated),'funding_source':budget.funding_source,
                        'totals':totals,'lines':list(budget.lines.order_by('pk').values('title','category','quantity','unit','unit_price','purchased_quantity','actual_amount','paid_amount','status','supplier','document_number','due_date','note'))}
                    EventBudgetApproval.objects.create(budget=budget,approver=request.user,snapshot=json.loads(json.dumps(payload,cls=DjangoJSONEncoder)))
                    budget.status='approved';message='Смета согласована. Сохранён снимок согласованной версии.'
                else:
                    reason=request.POST.get('reason','').strip()
                    if not reason or len(reason)>400:raise ValidationError('Укажите причину возврата (до 400 символов).')
                    budget.status='draft';message='Смета возвращена: '+reason
            else:raise ValidationError('Некорректное действие.')
            budget.save();log(locked,request.user,message)
        messages.success(request,message)
    except ValidationError as exc:messages.error(request,'; '.join(exc.messages))
    return redirect('event_finance',pk=pk)


@login_required
def finance_export(request,pk):
    event=finance_event(request,pk)
    from .excel import export_budget
    return export_budget(event)
