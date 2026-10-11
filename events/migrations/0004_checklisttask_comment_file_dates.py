# Generated migration for adding comment_sent_at and file_sent_at fields to ChecklistTask

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0003_alter_checklisttask_responsible_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='checklisttask',
            name='comment_sent_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Дата и время отправки комментария'
            ),
        ),
        migrations.AddField(
            model_name='checklisttask',
            name='file_sent_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Дата и время отправки файла'
            ),
        ),
    ]
