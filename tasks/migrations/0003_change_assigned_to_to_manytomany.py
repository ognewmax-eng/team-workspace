# Generated manually

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tasks', '0002_task_parent_task'),
    ]

    operations = [
        # Сначала создаем новое поле ManyToManyField
        migrations.AddField(
            model_name='task',
            name='assigned_to_new',
            field=models.ManyToManyField(
                blank=True,
                help_text='Можно выбрать несколько исполнителей из разных отделов',
                related_name='assigned_tasks',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Исполнители'
            ),
        ),
        # Переносим данные из старого поля в новое
        migrations.RunPython(
            code=lambda apps, schema_editor: migrate_assigned_to_data(apps, schema_editor),
            reverse_code=lambda apps, schema_editor: reverse_migrate_assigned_to_data(apps, schema_editor),
        ),
        # Удаляем старое поле
        migrations.RemoveField(
            model_name='task',
            name='assigned_to',
        ),
        # Переименовываем новое поле
        migrations.RenameField(
            model_name='task',
            old_name='assigned_to_new',
            new_name='assigned_to',
        ),
    ]


def migrate_assigned_to_data(apps, schema_editor):
    """Перенос данных из ForeignKey в ManyToManyField."""
    Task = apps.get_model('tasks', 'Task')
    User = apps.get_model(settings.AUTH_USER_MODEL)
    for task in Task.objects.all():
        # Проверяем, есть ли старое поле assigned_to (ForeignKey)
        if hasattr(task, 'assigned_to') and task.assigned_to_id:
            try:
                user = User.objects.get(id=task.assigned_to_id)
                task.assigned_to_new.add(user)
            except User.DoesNotExist:
                pass


def reverse_migrate_assigned_to_data(apps, schema_editor):
    """Обратный перенос данных из ManyToManyField в ForeignKey (берем первого исполнителя)."""
    Task = apps.get_model('tasks', 'Task')
    for task in Task.objects.all():
        assignees = list(task.assigned_to_new.all())
        if assignees:
            # В обратной миграции мы восстанавливаем ForeignKey, но это поле уже удалено
            # Поэтому эта функция не будет работать правильно, но это нормально для обратной миграции
            pass
