"""
Формы для создания и редактирования событий расписания.
"""
from django import forms
from .models import ScheduleEvent, Association, Lesson, ScheduleTemplate
from accounts.models import Department, User


class ScheduleEventForm(forms.ModelForm):
    """Форма для создания и редактирования события расписания."""
    
    class Meta:
        model = ScheduleEvent
        fields = ['title', 'description', 'event_type', 'department', 
                  'start_time', 'end_time', 'location', 'participants']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название события'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание события'
            }),
            'event_type': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'start_time': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_time': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Место проведения'
            }),
            'participants': forms.CheckboxSelectMultiple(attrs={'class': 'planner-participant-choice'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Ограничение выбора отдела
        if user:
            if user.is_director():
                self.fields['department'].queryset = Department.objects.all()
            elif user.department:
                self.fields['department'].queryset = Department.objects.filter(id=user.department.id)
            else:
                self.fields['department'].queryset = Department.objects.none()
            
            # Ограничение выбора участников
            if user.is_director():
                self.fields['participants'].queryset = User.objects.filter(is_active=True)
            elif user.department:
                self.fields['participants'].queryset = User.objects.filter(
                    department=user.department,
                    is_active=True
                )
            else:
                self.fields['participants'].queryset = User.objects.none()

    def clean(self):
        """Валидация: время окончания должно быть после времени начала."""
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time:
            if end_time <= start_time:
                raise forms.ValidationError(
                    'Время окончания должно быть позже времени начала.'
                )
        
        return cleaned_data


class LessonForm(forms.ModelForm):
    """Форма для создания и редактирования занятия."""
    
    class Meta:
        model = Lesson
        fields = ['association', 'weekday', 'start_time', 'end_time', 'classroom', 'note']
        widgets = {
            'association': forms.Select(attrs={'class': 'form-control'}),
            'weekday': forms.Select(attrs={'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'end_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'classroom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Аудитория'
            }),
            'note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Примечание'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        association_id = kwargs.pop('association_id', None)
        super().__init__(*args, **kwargs)
        
        # Ограничение выбора объединений только теми, где пользователь специалист
        if user:
            self.fields['association'].queryset = Association.objects.filter(
                specialist=user,
                is_active=True
            )
            if association_id:
                self.fields['association'].initial = association_id

    def clean(self):
        """Валидация: время окончания должно быть после времени начала."""
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time:
            if end_time <= start_time:
                raise forms.ValidationError(
                    'Время окончания должно быть позже времени начала.'
                )
        
        return cleaned_data


class ScheduleTemplateForm(forms.ModelForm):
    """Форма для создания шаблона расписания."""
    
    class Meta:
        model = ScheduleTemplate
        fields = ['name', 'description', 'association']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название шаблона'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание шаблона'
            }),
            'association': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        association_id = kwargs.pop('association_id', None)
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['association'].queryset = Association.objects.filter(
                specialist=user,
                is_active=True
            )
            if association_id:
                self.fields['association'].initial = association_id

