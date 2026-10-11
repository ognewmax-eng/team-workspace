# Generated manually for TaskAssignee through model

from django.conf import settings
from django.db import migrations, models


def migrate_to_task_assignee(apps, schema_editor):
    """Перенос назначений из M2M в TaskAssignee с копированием статуса задачи."""
    Task = apps.get_model('tasks', 'Task')
    TaskAssignee = apps.get_model('tasks', 'TaskAssignee')
    for task in Task.objects.prefetch_related('assigned_to').all():
        for user in task.assigned_to.all():
            completed_at = task.completed_at if task.status == 'completed' else None
            TaskAssignee.objects.get_or_create(
                task=task,
                user=user,
                defaults={
                    'status': task.status,
                    'completed_at': completed_at,
                },
            )


def reverse_migrate(apps, schema_editor):
    """Обратная миграция: заполняем M2M из TaskAssignee (новая таблица появится после AddField)."""
    Task = apps.get_model('tasks', 'Task')
    TaskAssignee = apps.get_model('tasks', 'TaskAssignee')
    for ta in TaskAssignee.objects.select_related('task', 'user').all():
        ta.task.assigned_to.add(ta.user)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tasks', '0007_task_is_archived'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskAssignee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('assigned', 'Назначено'),
                        ('in_progress', 'В работе'),
                        ('pending', 'На проверке'),
                        ('completed', 'Завершено'),
                    ],
                    default='assigned',
                    max_length=20,
                    verbose_name='Статус исполнителя',
                )),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата завершения')),
                ('task', models.ForeignKey(on_delete=models.CASCADE, related_name='assignments', to='tasks.task', verbose_name='Задача')),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='task_assignments', to=settings.AUTH_USER_MODEL, verbose_name='Исполнитель')),
            ],
            options={
                'verbose_name': 'Назначение на задачу',
                'verbose_name_plural': 'Назначения на задачи',
                'ordering': ['task', 'user'],
                'unique_together': {('task', 'user')},
            },
        ),
        migrations.RunPython(migrate_to_task_assignee, reverse_migrate),
        migrations.RemoveField(
            model_name='task',
            name='assigned_to',
        ),
        migrations.AddField(
            model_name='task',
            name='assigned_to',
            field=models.ManyToManyField(
                blank=True,
                help_text='Можно выбрать несколько исполнителей из разных отделов',
                related_name='assigned_tasks',
                through='tasks.TaskAssignee',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Исполнители',
            ),
        ),
    ]
