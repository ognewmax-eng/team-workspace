# Generated manually for ActivityLog model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_user_theme_settings'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('view', 'Просмотр'), ('create', 'Создание'), ('update', 'Обновление'), ('delete', 'Удаление'), ('login', 'Вход'), ('logout', 'Выход'), ('download', 'Скачивание'), ('upload', 'Загрузка'), ('other', 'Другое')], default='other', max_length=20, verbose_name='Действие')),
                ('content_type', models.CharField(blank=True, help_text='Например: Task, Event, WikiArticle', max_length=100, verbose_name='Тип объекта')),
                ('object_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID объекта')),
                ('object_repr', models.CharField(blank=True, help_text='Строковое представление объекта', max_length=200, verbose_name='Объект')),
                ('description', models.TextField(blank=True, verbose_name='Описание действия')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP адрес')),
                ('user_agent', models.TextField(blank=True, verbose_name='User Agent')),
                ('url', models.URLField(blank=True, max_length=500, verbose_name='URL')),
                ('method', models.CharField(blank=True, help_text='GET, POST, PUT, DELETE и т.д.', max_length=10, verbose_name='HTTP метод')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата и время')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_logs', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Действие пользователя',
                'verbose_name_plural': 'Действия пользователей',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['-created_at'], name='accounts_ac_created_idx'),
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['user', '-created_at'], name='accounts_ac_user_id_idx'),
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['action', '-created_at'], name='accounts_ac_action__idx'),
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['content_type', 'object_id'], name='accounts_ac_content_idx'),
        ),
    ]
