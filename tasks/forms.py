"""
Формы для создания и редактирования задач.
"""
from django import forms
from django.db.models import Q
from .models import Task, TaskComment, TaskFile, TaskTemplate
from accounts.models import Department, User


class MultipleFileInput(forms.ClearableFileInput):
    """Кастомный виджет для множественной загрузки файлов."""
    allow_multiple_selected = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs['multiple'] = True

    def value_from_datadict(self, data, files, name):
        """Возвращает список файлов вместо одного файла."""
        try:
            getter = files.getlist
        except AttributeError:
            getter = lambda key: [files.get(key)] if files.get(key) else []
        return getter(name)


class TaskForm(forms.ModelForm):
    """Форма для создания и редактирования задачи."""
    
    class Meta:
        model = Task
        fields = ['title', 'description', 'status', 'priority', 'departments',
                  'assigned_to', 'deadline', 'parent_task']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название задачи'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание задачи'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'departments': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input department-checkbox',
            }),
            'assigned_to': forms.SelectMultiple(attrs={
                'class': 'form-control',
                'size': '5',
                'multiple': True
            }),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'parent_task': forms.Select(attrs={
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        instance = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)
        
        # Поле files не включаем в форму, так как оно обрабатывается отдельно в view
        # Оно будет отображаться в шаблоне напрямую
        
        # Настройка поля parent_task
        if instance:
            # При редактировании исключаем саму задачу и её подзадачи из списка возможных родителей
            exclude_ids = [instance.id]
            # Добавляем все подзадачи текущей задачи
            exclude_ids.extend(instance.subtasks.values_list('id', flat=True))
            # Исключаем задачи, которые являются родителями текущей задачи (чтобы избежать циклов)
            current = instance
            while current.parent_task:
                exclude_ids.append(current.parent_task.id)
                current = current.parent_task
            
            # Ограничиваем выбор в зависимости от роли: директор — все; начальник — по отделам; специалист — только задачи, где он исполнитель
            if user:
                if user.is_director():
                    self.fields['parent_task'].queryset = Task.objects.exclude(id__in=exclude_ids)
                elif user.is_head() and user.department:
                    self.fields['parent_task'].queryset = Task.objects.filter(
                        Q(department=user.department) | Q(departments=user.department)
                    ).exclude(id__in=exclude_ids).distinct()
                elif user.is_specialist():
                    self.fields['parent_task'].queryset = Task.objects.filter(assigned_to=user).exclude(id__in=exclude_ids).distinct()
                else:
                    self.fields['parent_task'].queryset = Task.objects.none()
            else:
                self.fields['parent_task'].queryset = Task.objects.exclude(id__in=exclude_ids)
            
            self.fields['parent_task'].required = False
            self.fields['parent_task'].empty_label = "Нет (основная задача)"
        else:
            # При создании новой задачи: директор — все; начальник — по отделам; специалист — только задачи, где он исполнитель
            if user:
                if user.is_director():
                    self.fields['parent_task'].queryset = Task.objects.all()
                elif user.is_head() and user.department:
                    self.fields['parent_task'].queryset = Task.objects.filter(
                        Q(department=user.department) | Q(departments=user.department)
                    ).distinct()
                elif user.is_specialist():
                    self.fields['parent_task'].queryset = Task.objects.filter(assigned_to=user).distinct()
                else:
                    self.fields['parent_task'].queryset = Task.objects.none()
            else:
                self.fields['parent_task'].queryset = Task.objects.all()
            
            self.fields['parent_task'].required = False
            self.fields['parent_task'].empty_label = "Нет (основная задача)"
        
        # Ограничение выбора отделов в зависимости от роли.
        # При редактировании добавляем в queryset отделы, уже привязанные к задаче,
        # чтобы они отображались и не терялись при сохранении (для начальника и др.).
        if user:
            if user.is_director():
                self.fields['departments'].queryset = Department.objects.all()
                self.fields['departments'].required = True
            else:
                allowed_ids = set()
                if user.department:
                    allowed_ids.add(user.department.id)
                if instance and instance.pk:
                    if getattr(instance, 'departments', None):
                        allowed_ids |= set(instance.departments.values_list('id', flat=True))
                    # Задача с одним отделом (только FK, без M2M): включаем этот отдел в выбор,
                    # чтобы initial не оказался вне queryset и сохранение без изменений проходило
                    if getattr(instance, 'department_id', None):
                        allowed_ids.add(instance.department_id)
                self.fields['departments'].queryset = (
                    Department.objects.filter(id__in=allowed_ids) if allowed_ids else Department.objects.none()
                )
                # Обязательно только если есть хотя бы один отдел для выбора (иначе валидация невыполнима)
                self.fields['departments'].required = bool(allowed_ids)

        # При редактировании: если у задачи только department (без M2M), подставляем его в initial
        if instance and instance.pk and getattr(instance, 'department_id', None):
            if not getattr(instance, 'departments', None) or not instance.departments.exists():
                self.initial.setdefault('departments', [instance.department_id])

        if user:
            # Исполнители: при редактировании — только из отделов задачи; при создании — из всех доступных отделов (фильтр по выбранным отделам в шаблоне через JS)
            allowed_department_ids = list(self.fields['departments'].queryset.values_list('id', flat=True))
            if instance and instance.pk and hasattr(instance, 'departments'):
                dept_ids = list(instance.departments.values_list('id', flat=True))
                if dept_ids:
                    allowed_department_ids = [i for i in dept_ids if i in allowed_department_ids]
            if allowed_department_ids:
                self.fields['assigned_to'].queryset = User.objects.filter(
                    department_id__in=allowed_department_ids,
                    is_active=True
                ).select_related('department')
            else:
                self.fields['assigned_to'].queryset = User.objects.none()

            self.fields['assigned_to'].required = False
            self.fields['assigned_to'].help_text = 'Сначала выберите отдел(ы) — список исполнителей показывается только из выбранных отделов.'
            self.fields['departments'].help_text = 'Выберите один или несколько отделов (Ctrl+Click для множественного выбора).'

    def clean(self):
        data = super().clean()
        departments = data.get('departments') or []
        assigned_to = data.get('assigned_to')
        if departments and assigned_to:
            allowed_ids = {u.id for u in User.objects.filter(department__in=departments, is_active=True)}
            invalid = [u for u in assigned_to if u.id not in allowed_ids]
            if invalid:
                self.add_error(
                    'assigned_to',
                    'Исполнители должны быть из выбранных отделов: %s.' % ', '.join(u.get_full_name() or u.username for u in invalid)
                )
        return data


class TaskCommentForm(forms.ModelForm):
    """Форма для добавления комментария к задаче."""
    
    class Meta:
        model = TaskComment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Добавить комментарий...'
            })
        }


class TaskFileForm(forms.ModelForm):
    """Форма для загрузки файла к задаче."""
    
    class Meta:
        model = TaskFile
        fields = ['file', 'description']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '*/*'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Описание файла (необязательно)'
            })
        }

