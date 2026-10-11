"""Mailing records are append-only delivery history, separate from site notifications."""
from django.conf import settings
from django.db import models


class EmailCampaign(models.Model):
    STATUS = [('draft', 'Подготовлена'), ('queued', 'В очереди'), ('running', 'Отправляется'),
              ('finished', 'Обработана'), ('cancelled', 'Отменена')]
    subject = models.CharField('Тема', max_length=200)
    body = models.TextField('Текст', max_length=20000)
    audience = models.CharField('Получатели', max_length=250)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, related_name='email_campaigns', verbose_name='Автор')
    status = models.CharField('Состояние', max_length=12, choices=STATUS, default='draft', db_index=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    queued_at = models.DateTimeField('Поставлена в очередь', null=True, blank=True)
    finished_at = models.DateTimeField('Обработана', null=True, blank=True)
    test_sent_at = models.DateTimeField('Тест принят SMTP', null=True, blank=True)
    test_email = models.EmailField('Адрес теста', blank=True)
    last_error = models.CharField('Ошибка подключения', max_length=250, blank=True)
    skipped_count = models.PositiveIntegerField('Исключено при подготовке', default=0)

    class Meta:
        verbose_name = 'Email-рассылка'
        verbose_name_plural = 'Email-рассылки'
        ordering = ['-created_at']
        permissions = [('send_emailcampaign', 'Может отправлять email-рассылки')]

    def __str__(self):
        return self.subject


class EmailDelivery(models.Model):
    STATUS = [('pending', 'Ожидает'), ('sending', 'Передаётся'), ('sent', 'Принято SMTP'),
              ('failed', 'Отклонено'), ('skipped', 'Пропущено'), ('uncertain', 'Результат неизвестен')]
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name='deliveries', verbose_name='Рассылка')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='Пользователь')
    email = models.EmailField('Адрес')
    status = models.CharField('Результат', max_length=12, choices=STATUS, default='pending', db_index=True)
    started_at = models.DateTimeField('Начало попытки', null=True, blank=True)
    sent_at = models.DateTimeField('Принято SMTP', null=True, blank=True)
    error = models.CharField('Пояснение', max_length=250, blank=True)

    class Meta:
        verbose_name = 'Отправка письма'
        verbose_name_plural = 'Журнал отправок писем'
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['campaign', 'email'], name='unique_campaign_email')]

    def __str__(self):
        return self.email
