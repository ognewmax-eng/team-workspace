"""
Формы для приложения events.
"""
from django import forms
from .models import Meropriyatie


class MeropriyatieForm(forms.ModelForm):
    """Форма создания/редактирования мероприятия."""
    event_date = forms.DateTimeField(
        required=False,
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%d.%m.%Y %H:%M', '%d.%m.%Y'],
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control', 'type': 'datetime-local'}),
        label='Точная дата и время (когда определены)',
        help_text='Без точной даты укажите год и месяцы планирования. В календаре будет только подтверждённая дата.'
    )
    plan_year = forms.IntegerField(required=False, min_value=2000, max_value=2100, label='Год плана')
    month_start = forms.IntegerField(required=False, min_value=1, max_value=12, label='Месяц начала (1–12)')
    month_end = forms.IntegerField(required=False, min_value=1, max_value=12, label='Месяц окончания (1–12)')
    organizer = forms.CharField(required=False, max_length=300, label='Организация / организатор')
    audience = forms.CharField(required=False, max_length=300, label='Целевая аудитория')
    participants_target = forms.IntegerField(required=False, min_value=0, max_value=10000000, label='План участников')
    participants_actual = forms.IntegerField(required=False, min_value=0, max_value=10000000, label='Факт участников')
    results = forms.CharField(required=False, max_length=20000, label='Результаты и выводы', widget=forms.Textarea(attrs={'rows':3}))

    class Meta:
        model = Meropriyatie
        fields = [
            'title', 'description', 'event_type', 'event_date',
            'department', 'responsible', 'in_rosmol', 'rosmol_link', 'in_moroshka',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название мероприятия'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'event_type': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'responsible': forms.Select(attrs={'class': 'form-select'}),
            'in_rosmol': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'rosmol_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'in_moroshka': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils import timezone
        plan = getattr(self.instance, 'plan', None) if self.instance.pk else None
        date = timezone.localtime(self.instance.event_date) if self.instance.pk and self.instance.event_date else None
        for name in ['organizer','audience','participants_target','participants_actual','results']:
            self.initial.setdefault(name, getattr(plan,name,None))
        self.initial.setdefault('plan_year',plan.year if plan else date.year if date else timezone.localdate().year)
        self.initial.setdefault('month_start',plan.month_start if plan else date.month if date else None)
        self.initial.setdefault('month_end',plan.month_end if plan else date.month if date else None)
        from accounts.models import Department, User
        from .collaboration import can_admin
        self.fields['responsible'].queryset = User.objects.filter(is_active=True).order_by('last_name','first_name','username')
        if user and user.is_director():
            self.fields['department'].queryset = Department.objects.all()
        else:
            dept = self.instance.department_id if self.instance.pk else user.department_id if user else None
            self.fields['department'].queryset = Department.objects.filter(pk=dept)
            self.fields['department'].disabled = True
        if user and not (user.is_director() or (self.instance.pk and can_admin(user,self.instance)) or (not self.instance.pk and user.is_head())):
            self.fields['responsible'].disabled = True
        self.fields['responsible'].required = False
        self.fields['responsible'].help_text = 'Организация из плана и ответственный сотрудник — разные поля. Ответственного можно назначить позже.'
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class','form-control')

    def clean(self):
        data = super().clean()
        if data.get('event_date'):
            from django.utils import timezone
            date = timezone.localtime(data['event_date'])
            data.update(plan_year=date.year, month_start=date.month, month_end=date.month)
        else:
            if not data.get('plan_year') or not data.get('month_start'):
                self.add_error(None,'Укажите точную дату либо год и месяц планирования.')
            if not data.get('month_end'):data['month_end']=data.get('month_start')
            if data.get('month_start') and data.get('month_end') and data['month_end']<data['month_start']:
                self.add_error('month_end','Окончание периода не может быть раньше начала. Период задаётся внутри одного года.')
        if data.get('rosmol_link') and not data.get('in_rosmol'):
            self.add_error('in_rosmol', 'Если указана ссылка, отметьте размещение в АИС «Росмолодёжь».')
        if self.instance.pk and data.get('event_date'):
            from .models import EventWorkspace
            workspace = EventWorkspace.objects.filter(event=self.instance).first()
            if workspace and workspace.end_date and workspace.end_date <= data['event_date']:
                self.add_error('event_date', 'Начало должно быть раньше указанного окончания. Сначала исправьте окончание в рабочей карточке.')
        return data
