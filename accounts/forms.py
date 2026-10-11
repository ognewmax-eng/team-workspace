"""
Формы для регистрации и управления пользователями.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Department, UserWorkProfile

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    """Форма регистрации нового пользователя."""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@email.com'
        }),
        label='Email'
    )
    first_name = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Имя'
        }),
        label='Имя'
    )
    last_name = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Фамилия'
        }),
        label='Фамилия'
    )
    phone = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 123-45-67'
        }),
        label='Телефон'
    )
    position = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Должность'
        }),
        label='Должность'
    )
    department = forms.ModelChoiceField(
        required=False,
        queryset=Department.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Отдел',
        empty_label='Выберите отдел (необязательно)'
    )
    role = forms.ChoiceField(
        required=True,
        choices=User.ROLE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Роль',
        initial='specialist'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2', 
                  'phone', 'position', 'department', 'role')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Стилизация полей
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Имя пользователя'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Пароль'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Подтверждение пароля'
        })
        # Помощь для полей
        self.fields['username'].help_text = 'Обязательное поле. Не более 150 символов. Только буквы, цифры и символы @/./+/-/_'
        self.fields['password1'].help_text = 'Пароль должен содержать минимум 8 символов'
        self.fields['password2'].help_text = 'Введите тот же пароль для подтверждения'

    def save(self, commit=True):
        """Сохранение пользователя с is_active=False для одобрения администратором."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data.get('phone', '')
        user.position = self.cleaned_data.get('position', '')
        user.department = self.cleaned_data.get('department')
        user.role = self.cleaned_data['role']
        user.is_active = False  # Требует одобрения администратора
        if commit:
            user.save()
        return user


class UserProfileEditForm(forms.ModelForm):
    """Форма для редактирования профиля пользователя."""
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'position', 'telegram_chat_id')
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Имя'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Фамилия'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'example@email.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+7 (999) 123-45-67'
            }),
            'position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Должность'
            }),
            'telegram_chat_id': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'ID чата в Telegram (опционально)'
            }),
        }
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'email': 'Email',
            'phone': 'Телефон',
            'position': 'Должность',
            'telegram_chat_id': 'Telegram Chat ID',
        }
        help_texts = {
            'telegram_chat_id': 'ID чата в Telegram для получения уведомлений. Получите его, отправив /start боту.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем email обязательным
        self.fields['email'].required = True


class UserWorkProfileForm(forms.ModelForm):
    class Meta:
        model = UserWorkProfile
        fields = ('about', 'responsibilities', 'skills', 'projects', 'work_schedule', 'workplace', 'contact_preferences')
        help_texts = {
            'about': 'Ваш опыт и то, что коллегам полезно знать о вас.',
            'responsibilities': 'По каким вопросам к вам обращаться и за что вы отвечаете.',
            'skills': 'Например: работа с подростками, монтаж, организация мероприятий.',
            'projects': 'Объединения, мероприятия и проекты, над которыми вы сейчас работаете.',
            'work_schedule': 'Дни и часы, когда вы обычно доступны.',
            'workplace': 'Например: Молодёжный клуб, кабинет 204.',
            'contact_preferences': 'Предпочтительный канал связи и время для рабочих вопросов.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
            if isinstance(field.widget, forms.Textarea): field.widget.attrs['rows'] = 4


class PasswordChangeForm(forms.Form):
    """Форма для изменения пароля."""
    old_password = forms.CharField(
        label='Текущий пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите текущий пароль'
        }),
        required=True
    )
    new_password1 = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите новый пароль'
        }),
        required=True,
        help_text='Пароль должен содержать минимум 8 символов'
    )
    new_password2 = forms.CharField(
        label='Подтверждение нового пароля',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Подтвердите новый пароль'
        }),
        required=True
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        """Проверка текущего пароля."""
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError('Неверный текущий пароль.')
        return old_password

    def clean_new_password2(self):
        """Проверка совпадения новых паролей."""
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError('Новые пароли не совпадают.')
        return password2

    def save(self, commit=True):
        """Сохранение нового пароля."""
        password = self.cleaned_data['new_password1']
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user
