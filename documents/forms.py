"""
Формы для загрузки и редактирования документов.
"""
from django import forms
from .models import Document
from accounts.models import Department


class DocumentForm(forms.ModelForm):
    """Форма добавления/редактирования документа."""

    class Meta:
        model = Document
        fields = ['title', 'description', 'file', 'department', 'category']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название документа',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание документа (необязательно)',
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.odt,.ods,image/*',
            }),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            if self.user.is_director():
                self.fields['department'].queryset = Department.objects.all()
            elif self.user.is_head() and self.user.department:
                self.fields['department'].queryset = Department.objects.filter(id=self.user.department.id)
            else:
                self.fields['department'].queryset = Department.objects.none()
        if self.instance.pk:
            # Metadata changes never replace or clear the stored attachment.
            self.fields.pop('file')
