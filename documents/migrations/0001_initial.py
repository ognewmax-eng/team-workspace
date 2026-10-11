# Generated manually for documents app

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
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Краткое название документа', max_length=255, verbose_name='Название')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('file', models.FileField(help_text='Загрузите файл документа', upload_to='documents/%Y/%m/', verbose_name='Файл')),
                ('category', models.CharField(choices=[('order', 'Приказ'), ('regulation', 'Положение'), ('contract', 'Контракт'), ('directive', 'Распоряжение'), ('normative', 'Нормативный документ')], max_length=20, verbose_name='Категория')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='accounts.department', verbose_name='Отдел')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_documents', to=settings.AUTH_USER_MODEL, verbose_name='Загрузил')),
            ],
            options={
                'verbose_name': 'Документ',
                'verbose_name_plural': 'Документы',
                'ordering': ['-created_at'],
            },
        ),
    ]
