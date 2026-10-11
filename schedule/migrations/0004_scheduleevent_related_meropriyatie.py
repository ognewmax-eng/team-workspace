# Generated migration for related_meropriyatie on ScheduleEvent

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0006_meropriyatie_meropriyatiefile'),
        ('schedule', '0003_scheduleevent_related_task'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheduleevent',
            name='related_meropriyatie',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='schedule_events',
                to='events.meropriyatie',
                verbose_name='Связанное мероприятие'
            ),
        ),
    ]
