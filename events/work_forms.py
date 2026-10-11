from django import forms
from django.contrib.auth import get_user_model
from tasks.models import Task
from .models import EventTask, EventWorkspace
from .collaboration import team


class TeamForm(forms.Form):
    participants = forms.ModelMultipleChoiceField(queryset=get_user_model().objects.none(), required=False,
                  label='Команда мероприятия', widget=forms.CheckboxSelectMultiple)
    version = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['participants'].queryset = get_user_model().objects.filter(is_active=True).select_related('department').order_by('department__name','last_name','first_name','username')


class WorkTaskForm(forms.ModelForm):
    assigned_to = forms.ModelMultipleChoiceField(queryset=get_user_model().objects.none(), required=True,
                    widget=forms.CheckboxSelectMultiple, label='Исполнители из команды')
    stage = forms.ChoiceField(choices=EventTask.STAGE_CHOICES, label='Этап')
    version = forms.CharField(widget=forms.HiddenInput)
    deadline = forms.DateTimeField(required=False, label='Срок',
                   widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M',attrs={'type':'datetime-local'}),
                   input_formats=['%Y-%m-%dT%H:%M'])
    class Meta:
        model = Task
        fields = ['title','description','priority','deadline']
        widgets = {'description':forms.Textarea(attrs={'rows':4})}

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = team(event)
        self.fields['assigned_to'].help_text = 'Сначала добавьте специалистов в команду мероприятия.'


class WorkspaceForm(forms.Form):
    phase = forms.ChoiceField(choices=EventWorkspace.PHASE_CHOICES,label='Состояние мероприятия')
    location = forms.CharField(max_length=200,required=False,label='Место проведения')
    end_date = forms.DateTimeField(required=False,label='Дата и время окончания',
                  widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M',attrs={'type':'datetime-local'}),input_formats=['%Y-%m-%dT%H:%M'])
    version = forms.CharField(widget=forms.HiddenInput)
