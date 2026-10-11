from pathlib import Path
import json
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import Http404,FileResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_POST
from accounts.models import Department
from .models import EventImportBatch, Meropriyatie
from .importing import can_import,departments,read_upload,preview,commit,MAX_ROWS


class UploadForm(forms.Form):
    department=forms.ModelChoiceField(queryset=Department.objects.none(),label='Отдел для строк, где он не указан')
    file=forms.FileField(required=False,label='Файл .xlsx или HTML коллеги')
    default_type=forms.ChoiceField(required=False,choices=Meropriyatie.EVENT_TYPE_CHOICES,label='Тип по умолчанию')
    def __init__(self,*args,user=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['department'].queryset=departments(user)
        for field in self.fields.values():field.widget.attrs['class']='form-control'


@login_required
def import_view(request):
    if not can_import(request.user):raise Http404
    form=UploadForm(request.POST or None,request.FILES or None,user=request.user,initial={'department':request.user.department_id,'default_type':'mz'})
    if request.method=='POST' and form.is_valid():
        try:
            if form.cleaned_data['file']:
                rows=read_upload(form.cleaned_data['file']);label=form.cleaned_data['file'].name[:300]
            else:raise ValidationError('Выберите файл.')
            if not rows:raise ValidationError('В файле нет мероприятий.')
            if len(rows)>MAX_ROWS:raise ValidationError('Слишком много строк.')
            chosen_type=form.cleaned_data['default_type'] or 'mz'
            html_source=(form.cleaned_data['file'] and Path(form.cleaned_data['file'].name).suffix.lower() in ['.html','.htm'])
            for row in rows:
                if html_source or not row.get('event_type'):row['event_type']=chosen_type
            batch=EventImportBatch.objects.create(actor=request.user,department=form.cleaned_data['department'],rows=rows,source_label=label)
            return redirect('event_import_preview',batch_id=batch.pk)
        except ValidationError as exc:form.add_error(None,exc)
    return render(request,'events/import_upload.html',{'form':form})


@login_required
def preview_view(request,batch_id):
    if not can_import(request.user):raise Http404
    batch=get_object_or_404(EventImportBatch.objects.select_related('department'),pk=batch_id,actor=request.user)
    if not departments(request.user).filter(pk=batch.department_id).exists():raise Http404
    rows=preview(batch,request.user)
    return render(request,'events/import_preview.html',{'batch':batch,'rows':rows,'valid_count':sum(not r['errors'] and not r['duplicate'] for r in rows),
        'error_count':sum(bool(r['errors']) for r in rows),'duplicate_count':sum(r['duplicate'] for r in rows)})


@login_required
@require_POST
def commit_view(request,batch_id):
    if not can_import(request.user):raise Http404
    batch=get_object_or_404(EventImportBatch,pk=batch_id,actor=request.user)
    try:
        selected=request.POST.getlist('rows')
        if len(selected)>MAX_ROWS or any(not s.isascii() or not s.isdigit() or len(s)>4 for s in selected):raise ValidationError('Некорректный выбор строк.')
        result=commit(batch,request.user,{int(x) for x in selected})
        messages.success(request,'Импорт завершён. Добавлено: %s. Пропущено дублей: %s. Повторное нажатие не создаёт копии.'%(len(result['created']),result['skipped']))
        return redirect('event_import_preview',batch_id=batch_id)
    except ValidationError as exc:messages.error(request,'; '.join(exc.messages))
    except DatabaseError:messages.error(request,'Во время импорта данные изменились или база занята. Ничего не добавлено; проверьте предпросмотр и повторите.')
    return redirect('event_import_preview',batch_id=batch_id)


@login_required
def template_view(request):
    if not can_import(request.user):raise Http404
    from openpyxl import Workbook
    from accounts.models import User
    from .excel import sheet,response
    wb=Workbook();wb.remove(wb.active)
    from .importing import HEADERS
    sheet(wb,'Мероприятия',[label for key,label in HEADERS],[])
    sheet(wb,'Как заполнить',['Поле','Правило'],[['Название','Обязательно'],['Период','Точная дата или год и месяцы 1–12'],['Тип','mz или vneplan'],['Отдел','Название отдела либо выбранный отдел загрузки'],['Ответственный','Логин активного сотрудника'],['Бюджет','Рубли; пусто — не указан; 0 — без средств'],['Повторный импорт','Коды источника сохраняйте; существующие записи не перезаписываются']])
    staff=User.objects.filter(is_active=True).select_related('department')
    if not request.user.is_director():staff=staff.filter(department_id=request.user.department_id)
    sheet(wb,'Справочники',['Отдел','Логин','ФИО'],[
        [u.department.name if u.department else '',u.username,u.get_full_name()] for u in staff.order_by('department__name','last_name','first_name','username')])
    return response(wb,'events_import_template.xlsx')
