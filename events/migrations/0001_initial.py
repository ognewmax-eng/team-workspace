# Generated manually for events app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Название мероприятия')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('status', models.CharField(choices=[('draft', 'Черновик'), ('planning', 'В планировании'), ('in_progress', 'В процессе'), ('completed', 'Завершено'), ('cancelled', 'Отменено')], default='draft', max_length=20, verbose_name='Статус')),
                ('event_date', models.DateTimeField(blank=True, null=True, verbose_name='Дата проведения')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_planning_events', to=settings.AUTH_USER_MODEL, verbose_name='Создал')),
                ('department', models.ForeignKey(blank=True, help_text='Если не указан, мероприятие видно всем отделам', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='accounts.department', verbose_name='Отдел')),
            ],
            options={
                'verbose_name': 'Мероприятие',
                'verbose_name_plural': 'Мероприятия',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EventNode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Название узла')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('node_type', models.CharField(choices=[('root', 'Корневой узел'), ('task', 'Задача'), ('milestone', 'Веха'), ('resource', 'Ресурс'), ('note', 'Заметка'), ('other', 'Другое')], default='task', max_length=20, verbose_name='Тип узла')),
                ('position_x', models.FloatField(default=0, verbose_name='Позиция X')),
                ('position_y', models.FloatField(default=0, verbose_name='Позиция Y')),
                ('color', models.CharField(default='#3b82f6', max_length=7, verbose_name='Цвет узла')),
                ('size', models.IntegerField(default=20, verbose_name='Размер узла')),
                ('order', models.IntegerField(default=0, verbose_name='Порядок')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nodes', to='events.event', verbose_name='Мероприятие')),
                ('parent', models.ForeignKey(blank=True, help_text='Корневой узел не имеет родителя', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='events.eventnode', verbose_name='Родительский узел')),
            ],
            options={
                'verbose_name': 'Узел мероприятия',
                'verbose_name_plural': 'Узлы мероприятий',
                'ordering': ['order', 'created_at'],
            },
        ),
    ]
