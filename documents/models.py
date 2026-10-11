"""
Модели для хранения документов (приказы, положения, контракты и т.д.).
Доступ: директор и начальник отдела.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import Department

User = get_user_model()


class Document(models.Model):
    """
    Документ с привязкой к отделу и категории.
    """
    CATEGORY_CHOICES = [
        ('order', 'Приказ'),
        ('regulation', 'Положение'),
        ('contract', 'Контракт'),
        ('directive', 'Распоряжение'),
        ('normative', 'Нормативный документ'),
    ]

    title = models.CharField(
        max_length=255,
        verbose_name='Название',
        help_text='Краткое название документа'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    file = models.FileField(
        upload_to='documents/%Y/%m/',
        verbose_name='Файл',
        help_text='Загрузите файл документа'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Отдел'
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        verbose_name='Категория'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents',
        verbose_name='Загрузил'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления'
    )

    class Meta:
        verbose_name = 'Документ'
        verbose_name_plural = 'Документы'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('document_detail', args=[self.pk])


class DocumentState(models.Model):
    """Separate table so the previous release can still read Document records."""
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='state')
    is_archived = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
