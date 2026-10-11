"""
Формы для создания и редактирования статей вики.
"""
from django import forms
from .models import WikiArticle, WikiArticleFile
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


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        values = data if isinstance(data, (tuple, list)) else [data] if data else []
        if len(values) > 10:
            raise forms.ValidationError('За один раз можно добавить не более 10 файлов.')
        return [super(MultipleFileField, self).clean(item, initial) for item in values]


class WikiArticleForm(forms.ModelForm):
    """Форма для создания и редактирования статьи вики."""
    
    # Поле для загрузки файлов при создании/редактировании статьи
    files = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': '*/*'
        }),
        help_text='Можно выбрать несколько файлов (Ctrl+Click или Cmd+Click для множественного выбора)'
    )
    
    class Meta:
        model = WikiArticle
        fields = ['title', 'content', 'category', 'department', 'is_pinned', 'tags']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название статьи'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 15,
                'placeholder': 'Содержание статьи (поддерживается Markdown)'
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_pinned': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Теги через запятую (например: инструкция, работа, важное)'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Ограничение выбора отдела в зависимости от роли
        if user:
            if user.is_director():
                # Директор видит все отделы
                self.fields['department'].queryset = Department.objects.all()
            elif user.is_head():
                # Начальник видит только свой отдел
                if user.department:
                    self.fields['department'].queryset = Department.objects.filter(id=user.department.id)
                else:
                    self.fields['department'].queryset = Department.objects.none()
            else:
                # Специалист видит только свой отдел
                if user.department:
                    self.fields['department'].queryset = Department.objects.filter(id=user.department.id)
                else:
                    self.fields['department'].queryset = Department.objects.none()
            
            self.fields['department'].required = False
            self.fields['department'].empty_label = "Все отделы"
        else:
            self.fields['department'].queryset = Department.objects.none()
            self.fields['department'].required = False
            self.fields['department'].empty_label = "Все отделы"

    def clean_content(self):
        value = self.cleaned_data['content']
        if len(value) > 200000:
            raise forms.ValidationError('Текст статьи должен быть не длиннее 200 000 символов.')
        return value


class WikiArticleFileForm(forms.ModelForm):
    """Форма для загрузки файла к статье вики."""
    
    class Meta:
        model = WikiArticleFile
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
