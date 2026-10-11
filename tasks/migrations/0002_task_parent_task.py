# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='parent_task',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='subtasks',
                to='tasks.task',
                verbose_name='Родительская задача',
                help_text='Выберите родительскую задачу, если это подзадача'
            ),
        ),
    ]
