"""Prepare a fixed audience, then send one private message per recipient."""
from collections import Counter
from datetime import timedelta
import smtplib
import ssl
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count
from django.template.loader import render_to_string
from django.utils import timezone
from .mail_backend import FROM_EMAIL
from .mailing_models import EmailCampaign, EmailDelivery

from django.conf import settings
SITE_URL = settings.SITE_URL + '/'


def valid_email(value):
    value = (value or '').strip().lower()
    try:
        validate_email(value)
    except ValidationError:
        return None
    return value


def stats(campaign):
    counts = Counter({row['status']: row['n'] for row in campaign.deliveries.values('status').annotate(n=Count('pk'))})
    counts['total'] = sum(counts.values())
    return counts


def prepare(data, creator):
    users = get_user_model().objects.filter(is_active=True).order_by('pk')
    scope = data['scope']
    audience = 'Все активные пользователи'
    if scope == 'department':
        users = users.filter(department=data['department'])
        audience = 'Отдел: ' + data['department'].name
    elif scope == 'selected':
        users = users.filter(pk__in=data['users'].values_list('pk', flat=True))
        audience = 'Выбранные пользователи'
    elif scope != 'all':
        raise ValueError('Неизвестный список получателей.')
    seen, targets, skipped = set(), [], 0
    for user in users:
        email = valid_email(user.email)
        if not email or email in seen:
            skipped += 1
            continue
        seen.add(email)
        targets.append((user.pk, email))
    if not targets:
        raise ValueError('В выбранной группе нет корректных email-адресов.')
    with transaction.atomic():
        campaign = EmailCampaign.objects.create(subject=data['subject'], body=data['body'], audience=audience,
                                                 created_by=creator, skipped_count=skipped)
        EmailDelivery.objects.bulk_create([EmailDelivery(campaign=campaign, user_id=uid, email=email)
                                          for uid, email in targets])
    return campaign


def message(campaign, email, connection, test=False):
    subject = ('[ТЕСТ] ' if test else '') + campaign.subject
    body = campaign.body + '\n\nРабочее пространство: ' + SITE_URL
    msg = EmailMultiAlternatives(subject, body, FROM_EMAIL, [email], connection=connection)
    msg.attach_alternative(render_to_string('emails/campaign.html', {'campaign': campaign, 'site_url': SITE_URL,
                                                                  'test': test, 'organization_name':settings.SITE_NAME}), 'text/html')
    return msg


def safe_error(error):
    # SMTP server text may contain credentials or other private data. Never log it.
    if isinstance(error, ImproperlyConfigured):
        return 'Проверьте настройки SMTP в закрытом файле окружения.'
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return 'SMTP: не удалось авторизоваться. Проверьте пароль почтового ящика.'
    if isinstance(error, ssl.SSLError):
        return 'SSL: не удалось установить защищённое соединение.'
    if isinstance(error, smtplib.SMTPResponseException):
        return 'SMTP отклонил операцию (код %s).' % error.smtp_code
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return 'SMTP отклонил адрес получателя.'
    return 'Соединение с почтовым сервером прервано. Результат отправки неизвестен.'


MAIL_ERRORS = (smtplib.SMTPException, OSError, ValueError, ImproperlyConfigured)


def send_test(campaign, email):
    if campaign.status != 'draft':
        raise ValueError('Тест доступен только до постановки рассылки в очередь.')
    connection = get_connection(fail_silently=False)
    try:
        if message(campaign, email, connection, test=True).send() != 1:
            raise ValueError('Почтовый сервер не подтвердил принятие тестового письма.')
    finally:
        connection.close()
    EmailCampaign.objects.filter(pk=campaign.pk, status='draft').update(test_sent_at=timezone.now(), test_email=email)


def enqueue(campaign_id):
    updated = EmailCampaign.objects.filter(pk=campaign_id, status='draft', test_sent_at__isnull=False).update(
        status='queued', queued_at=timezone.now(), last_error='')
    return bool(updated)


def cancel(campaign_id):
    with transaction.atomic():
        updated = EmailCampaign.objects.filter(pk=campaign_id, status__in=['draft', 'queued', 'running']).update(
            status='cancelled', finished_at=timezone.now())
        if updated:
            EmailDelivery.objects.filter(campaign_id=campaign_id, status='pending').update(
                status='skipped', error='Рассылка отменена.')
    return bool(updated)


def finish_campaigns():
    for campaign in EmailCampaign.objects.filter(status__in=['queued', 'running']):
        if not campaign.deliveries.filter(status__in=['pending', 'sending']).exists():
            EmailCampaign.objects.filter(pk=campaign.pk, status__in=['queued', 'running']).update(
                status='finished', finished_at=timezone.now())


def process_pending(limit=20):
    """Caller must hold the OS worker lock. Network I/O is outside DB transactions."""
    # A previous worker exited after claiming these messages. Never resend blindly.
    EmailDelivery.objects.filter(status='sending').update(status='uncertain', error='Предыдущая отправка прервана; повтор автоматически не выполняется.')
    finish_campaigns()
    since = timezone.now() - timedelta(hours=24)
    attempted = EmailDelivery.objects.filter(started_at__gte=since).count()
    limit = min(max(int(limit), 1), 50, max(0, 1000 - attempted))
    pending = EmailDelivery.objects.filter(status='pending', campaign__status__in=['queued', 'running']).order_by('campaign_id', 'pk')
    if not limit or not pending.exists():
        return {'processed': 0, 'sent': 0, 'uncertain': 0, 'failed': 0, 'skipped': 0, 'budget_exhausted': not bool(limit)}
    connection = None
    report = Counter()
    try:
        try:
            connection = get_connection(fail_silently=False)
            connection.open()
        except MAIL_ERRORS as error:
            EmailCampaign.objects.filter(status__in=['queued', 'running']).update(last_error=safe_error(error))
            raise ValueError(safe_error(error)) from None
        for delivery_id in list(pending.values_list('pk', flat=True)[:limit]):
            with transaction.atomic():
                delivery = EmailDelivery.objects.select_related('campaign', 'user').get(pk=delivery_id)
                if delivery.status != 'pending' or delivery.campaign.status not in ['queued', 'running']:
                    continue
                if not delivery.user or not delivery.user.is_active or valid_email(delivery.user.email) != delivery.email:
                    EmailDelivery.objects.filter(pk=delivery.pk, status='pending').update(
                        status='skipped', error='Пользователь отключён, удалён или изменил email после подготовки.')
                    report['skipped'] += 1
                    continue
                claimed = EmailDelivery.objects.filter(pk=delivery.pk, status='pending').update(
                    status='sending', started_at=timezone.now())
                if not claimed:
                    continue
                EmailCampaign.objects.filter(pk=delivery.campaign_id, status__in=['queued', 'running']).update(status='running', last_error='')
            # Deliveries go to a single To address; there is no public recipient list.
            try:
                if message(delivery.campaign, delivery.email, connection).send() != 1:
                    state, error = 'failed', 'Почтовый сервер не подтвердил принятие письма.'
                else:
                    state, error = 'sent', ''
            except MAIL_ERRORS as exc:
                definitive = isinstance(exc, (smtplib.SMTPRecipientsRefused, smtplib.SMTPResponseException, ValueError))
                state, error = ('failed' if definitive else 'uncertain'), safe_error(exc)
                # Reconnect before the next message after any interrupted session.
                try:
                    connection.close()
                except (smtplib.SMTPException, OSError):
                    pass
            EmailDelivery.objects.filter(pk=delivery.pk, status='sending').update(
                status=state, error=error, sent_at=timezone.now() if state == 'sent' else None)
            report[state] += 1
            report['processed'] += 1
    finally:
        if connection:
            try:
                connection.close()
            except (smtplib.SMTPException, OSError):
                pass
        finish_campaigns()
    return dict(report)
