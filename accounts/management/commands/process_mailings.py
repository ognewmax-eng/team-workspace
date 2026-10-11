import fcntl
import os
from django.core.management.base import BaseCommand, CommandError
from accounts.mail_backend import config_path
from accounts.mailing_service import process_pending


class Command(BaseCommand):
    help = 'Обработать очередь email-рассылок. Не повторяет отправленные или неоднозначные попытки.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20)

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 50:
            raise CommandError('--limit должен быть от 1 до 50.')
        path = config_path().with_name('email-worker.lock')
        try:
            fd = os.open(str(path), os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        except OSError:
            raise CommandError('Не удалось открыть блокировку очереди почты.') from None
        with os.fdopen(fd, 'a') as lock:
            os.fchmod(lock.fileno(), 0o600)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.stdout.write('Очередь уже обрабатывается другим процессом.')
                return
            try:
                report = process_pending(options['limit'])
            except ValueError as error:
                raise CommandError(str(error)) from None
        if report.get('processed') or report.get('skipped') or report.get('budget_exhausted'):
            self.stdout.write('Обработано: %s; принято SMTP: %s; отклонено: %s; неизвестно: %s; пропущено: %s%s' % (
                report.get('processed', 0), report.get('sent', 0), report.get('failed', 0), report.get('uncertain', 0),
                report.get('skipped', 0), '; лимит 1000 попыток за 24 часа исчерпан' if report.get('budget_exhausted') else ''))
