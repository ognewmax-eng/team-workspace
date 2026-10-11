from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('accounts', '0008_user_design_style')]
    operations = [migrations.CreateModel(
        name='UserWorkProfile',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('about', models.TextField(blank=True, max_length=2000, verbose_name='О себе')),
            ('responsibilities', models.TextField(blank=True, max_length=2000, verbose_name='Зоны ответственности')),
            ('skills', models.TextField(blank=True, max_length=1000, verbose_name='Навыки и компетенции')),
            ('projects', models.TextField(blank=True, max_length=1500, verbose_name='Текущие проекты и направления')),
            ('work_schedule', models.CharField(blank=True, max_length=250, verbose_name='Рабочий график')),
            ('workplace', models.CharField(blank=True, max_length=200, verbose_name='Площадка и кабинет')),
            ('contact_preferences', models.CharField(blank=True, max_length=350, verbose_name='Как со мной связаться')),
            ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='work_profile', to=settings.AUTH_USER_MODEL, verbose_name='Сотрудник')),
        ],
        options={'verbose_name': 'Рабочий профиль', 'verbose_name_plural': 'Рабочие профили'},
    )]
