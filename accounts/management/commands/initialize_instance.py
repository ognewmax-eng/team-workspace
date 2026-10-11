import getpass
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from accounts.models import Department
class Command(BaseCommand):
    help='Create the first director on an empty instance; never overwrite users.'
    def handle(self,*args,**options):
        User=get_user_model()
        if User.objects.exists():
            self.stdout.write('Пользователи уже существуют. Инициализация пропущена.');return
        login=input('Логин первого директора: ').strip()
        if not login:raise CommandError('Логин обязателен.')
        email=input('Email директора (необязательно): ').strip()
        department=input('Первый отдел [Администрация]: ').strip() or 'Администрация'
        password=getpass.getpass('Пароль: ')
        if password!=getpass.getpass('Повторите пароль: '):raise CommandError('Пароли не совпадают.')
        user=User(username=login,email=email,role='director',is_staff=True,is_superuser=True)
        try:user.full_clean(exclude=['password','department']);validate_password(password,user)
        except ValidationError as e:raise CommandError('; '.join(e.messages)) from None
        with transaction.atomic():
            if User.objects.exists():raise CommandError('Другой пользователь уже создан. Повторите проверку.')
            dept,_=Department.objects.get_or_create(name=department)
            user.department=dept;user.set_password(password);user.save()
        self.stdout.write('Директор создан. Войдите на сайт и добавьте свои отделы и сотрудников.')
