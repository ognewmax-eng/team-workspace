# Generated manually for wiki app

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
            name='WikiArticle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Название статьи')),
                ('content', models.TextField(help_text='Поддерживается Markdown форматирование', verbose_name='Содержание статьи')),
                ('category', models.CharField(choices=[('instruction', 'Инструкция'), ('important', 'Важный момент'), ('procedure', 'Процедура'), ('reference', 'Справочная информация'), ('other', 'Другое')], default='instruction', max_length=20, verbose_name='Категория')),
                ('is_pinned', models.BooleanField(default=False, help_text='Закрепленные статьи отображаются вверху списка', verbose_name='Закрепить')),
                ('tags', models.CharField(blank=True, help_text='Теги через запятую для удобного поиска', max_length=500, verbose_name='Теги')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('views_count', models.PositiveIntegerField(default=0, verbose_name='Количество просмотров')),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wiki_articles', to=settings.AUTH_USER_MODEL, verbose_name='Автор')),
                ('department', models.ForeignKey(blank=True, help_text='Если не указан, статья видна всем отделам', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wiki_articles', to='accounts.department', verbose_name='Отдел')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_wiki_articles', to=settings.AUTH_USER_MODEL, verbose_name='Обновил')),
            ],
            options={
                'verbose_name': 'Статья вики',
                'verbose_name_plural': 'Статьи вики',
                'ordering': ['-is_pinned', '-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='WikiArticleFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='wiki_files/%Y/%m/%d/', verbose_name='Файл')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='Описание файла')),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='wiki.wikiarticle', verbose_name='Статья')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='uploaded_wiki_files', to=settings.AUTH_USER_MODEL, verbose_name='Загрузил')),
            ],
            options={
                'verbose_name': 'Файл статьи вики',
                'verbose_name_plural': 'Файлы статей вики',
                'ordering': ['-uploaded_at'],
            },
        ),
        migrations.AddIndex(
            model_name='wikiarticle',
            index=models.Index(fields=['is_pinned', '-updated_at'], name='wiki_wikiar_is_pinn_7a8b2d_idx'),
        ),
        migrations.AddIndex(
            model_name='wikiarticle',
            index=models.Index(fields=['category'], name='wiki_wikiar_categor_idx'),
        ),
        migrations.AddIndex(
            model_name='wikiarticle',
            index=models.Index(fields=['department'], name='wiki_wikiar_departm_idx'),
        ),
    ]
