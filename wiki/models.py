"""
Модели для системы вики (инструкции и важные моменты для работы).
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from accounts.models import Department

User = get_user_model()


class WikiArticle(models.Model):
    """
    Статья вики с инструкциями и важными моментами для работы.
    """
    CATEGORY_CHOICES = [
        ('instruction', 'Инструкция'),
        ('important', 'Важный момент'),
        ('procedure', 'Процедура'),
        ('reference', 'Справочная информация'),
        ('other', 'Другое'),
    ]

    title = models.CharField(
        max_length=200,
        verbose_name='Название статьи'
    )
    content = models.TextField(
        verbose_name='Содержание статьи',
        help_text='Поддерживается Markdown форматирование'
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='instruction',
        verbose_name='Категория'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wiki_articles',
        verbose_name='Отдел',
        help_text='Если не указан, статья видна всем отделам'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='wiki_articles',
        verbose_name='Автор'
    )
    is_pinned = models.BooleanField(
        default=False,
        verbose_name='Закрепить',
        help_text='Закрепленные статьи отображаются вверху списка'
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Теги',
        help_text='Теги через запятую для удобного поиска'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_wiki_articles',
        verbose_name='Обновил'
    )
    views_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Количество просмотров'
    )

    class Meta:
        verbose_name = 'Статья вики'
        verbose_name_plural = 'Статьи вики'
        ordering = ['-is_pinned', '-updated_at']
        indexes = [
            models.Index(fields=['is_pinned', '-updated_at']),
            models.Index(fields=['category']),
            models.Index(fields=['department']),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        """Получить URL статьи."""
        return reverse('wiki_detail', args=[self.id])

    def get_tags_list(self):
        """Получить список тегов."""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []

    def increment_views(self):
        """Увеличить счетчик просмотров."""
        from django.db.models import F
        type(self).objects.filter(pk=self.pk).update(views_count=F('views_count') + 1)
        self.views_count += 1


class WikiArticleFile(models.Model):
    """
    Прикрепленные файлы к статьям вики.
    """
    article = models.ForeignKey(
        WikiArticle,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='Статья'
    )
    file = models.FileField(
        upload_to='wiki_files/%Y/%m/%d/',
        verbose_name='Файл'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='uploaded_wiki_files',
        verbose_name='Загрузил'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата загрузки'
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Описание файла'
    )

    class Meta:
        verbose_name = 'Файл статьи вики'
        verbose_name_plural = 'Файлы статей вики'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.file.name} (к статье "{self.article.title}")'


class WikiState(models.Model):
    article = models.OneToOneField(WikiArticle, on_delete=models.CASCADE, related_name='state')
    is_archived = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)


class WikiFileState(models.Model):
    attachment = models.OneToOneField(WikiArticleFile, on_delete=models.CASCADE, related_name='state')
    is_archived = models.BooleanField(default=False)


class WikiRevision(models.Model):
    """Text and metadata before an edit. Attachments are managed separately."""
    article = models.ForeignKey(WikiArticle, on_delete=models.CASCADE, related_name='revisions')
    saved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    saved_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=20)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    is_pinned = models.BooleanField(default=False)
    tags = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-saved_at', '-pk']
