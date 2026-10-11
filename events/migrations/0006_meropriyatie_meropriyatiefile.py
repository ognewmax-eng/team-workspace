# Generated migration for Meropriyatie and MeropriyatieFile

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('events', '0005_checklisttaskcomment'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Meropriyatie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300, verbose_name='Название мероприятия')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('event_type', models.CharField(choices=[('mz', 'МЗ'), ('vneplan', 'Внеплановое')], default='mz', max_length=20, verbose_name='Тип мероприятия')),
                ('event_date', models.DateTimeField(verbose_name='Дата проведения')),
                ('in_rosmol', models.BooleanField(default=False, verbose_name='Занесено в АИС «Росмолодёжь»')),
                ('rosmol_link', models.URLField(blank=True, max_length=500, verbose_name='Ссылка на мероприятие в АИС «Росмолодёжь»')),
                ('in_moroshka', models.BooleanField(default=False, verbose_name='Занесено в «Морошку»')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_meropriyatiya', to=settings.AUTH_USER_MODEL, verbose_name='Создал')),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meropriyatiya', to='accounts.department', verbose_name='Отдел')),
                ('responsible', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='responsible_meropriyatiya', to=settings.AUTH_USER_MODEL, verbose_name='Ответственный')),
            ],
            options={
                'verbose_name': 'Мероприятие',
                'verbose_name_plural': 'Мероприятия',
                'ordering': ['-event_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MeropriyatieFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='meropriyatiya/%Y/%m/%d/', verbose_name='Файл')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='Описание')),
                ('meropriyatie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='events.meropriyatie', verbose_name='Мероприятие')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meropriyatie_uploads', to=settings.AUTH_USER_MODEL, verbose_name='Загрузил')),
            ],
            options={
                'verbose_name': 'Файл мероприятия',
                'verbose_name_plural': 'Файлы мероприятий',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
