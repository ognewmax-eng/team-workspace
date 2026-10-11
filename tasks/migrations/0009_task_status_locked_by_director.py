from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0008_taskassignee_through'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='status_locked_by_director',
            field=models.BooleanField(
                default=False,
                verbose_name='Статус зафиксирован руководителем',
                help_text='Если включено, статус задачи не изменяется автоматически по статусам исполнителей',
            ),
        ),
    ]

