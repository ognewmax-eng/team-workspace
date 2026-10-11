from django import forms
from django.contrib.auth import get_user_model
from .models import Department


class ComposeForm(forms.Form):
    subject = forms.CharField(label='Тема письма', max_length=200)
    body = forms.CharField(label='Текст письма', max_length=20000, widget=forms.Textarea(attrs={'rows': 10}),
                           help_text='Обычный текст. В конце письма будет ссылка на рабочее пространство.')
    scope = forms.ChoiceField(label='Кому отправить', choices=[('all', 'Всем активным пользователям'),
        ('department', 'Активным пользователям отдела'), ('selected', 'Выбранным пользователям')])
    department = forms.ModelChoiceField(label='Отдел', required=False, queryset=Department.objects.all(), help_text='Используется при выборе группы «Активным пользователям отдела».')
    users = forms.ModelMultipleChoiceField(label='Выбранные пользователи', required=False,
        queryset=get_user_model().objects.none(), widget=forms.SelectMultiple(attrs={'size': 7}),
        help_text='Используется для группы «Выбранным пользователям». Для выбора нескольких удерживайте Ctrl или Cmd.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['users'].queryset = get_user_model().objects.filter(is_active=True).order_by('last_name', 'first_name', 'username')

    def clean_subject(self):
        value = self.cleaned_data['subject']
        if '\n' in value or '\r' in value:
            raise forms.ValidationError('Тема должна быть одной строкой.')
        return value

    def clean(self):
        data = super().clean()
        if data.get('scope') == 'department' and not data.get('department'):
            self.add_error('department', 'Выберите отдел.')
        if data.get('scope') == 'selected' and not data.get('users'):
            self.add_error('users', 'Выберите хотя бы одного пользователя.')
        return data


class TestForm(forms.Form):
    email = forms.EmailField(label='Адрес для тестового письма')


class ConfirmForm(forms.Form):
    confirm = forms.BooleanField(label='Подтверждаю отправку этому списку получателей', required=True)
