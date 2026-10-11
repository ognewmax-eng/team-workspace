# Generated migration for ChecklistTaskComment model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('events', '0004_checklisttask_comment_file_dates'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChecklistTaskComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(verbose_name='Текст комментария')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата и время обновления')),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='checklist_task_comments', to=settings.AUTH_USER_MODEL, verbose_name='Автор')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='events.checklisttask', verbose_name='Задача')),
            ],
            options={
                'verbose_name': 'Комментарий к задаче',
                'verbose_name_plural': 'Комментарии к задачам',
                'ordering': ['created_at'],
            },
        ),
    ]
