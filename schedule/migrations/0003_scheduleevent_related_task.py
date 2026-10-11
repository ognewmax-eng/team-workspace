# Generated migration for adding related_task field to ScheduleEvent

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0002_scheduleevent_google_calendar_event_id'),
        ('tasks', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheduleevent',
            name='related_task',
            field=models.ForeignKey(
                blank=True,
                help_text='Задача, для которой создано это событие расписания',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='schedule_events',
                to='tasks.task',
                verbose_name='Связанная задача'
            ),
        ),
    ]
