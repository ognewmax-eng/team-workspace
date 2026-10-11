"""Verify referenced files, optionally comparing bytes and probing writes."""
import hashlib
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from accounts.synology_storage import SynologyStorage


def digest(storage, name):
    result = hashlib.sha256()
    with storage.open(name) as f:
        for chunk in f.chunks():
            result.update(chunk)
    return result.hexdigest()


class Command(BaseCommand):
    help = 'Verify Synology attachments without changing database or active storage'

    def add_arguments(self, parser):
        parser.add_argument('--write-test', action='store_true')
        parser.add_argument('--compare', action='store_true', help='Compare SHA256 with current storage before switching')

    def handle(self, *args, **options):
        from documents.models import Document
        from tasks.models import TaskFile
        from wiki.models import WikiArticleFile
        from events.models import MeropriyatieFile, ChecklistTask
        if ChecklistTask.objects.exclude(file_url='').exists():
            raise CommandError('Checklist links now exist: review before switching')
        storage = SynologyStorage()
        if options['compare'] and isinstance(default_storage, SynologyStorage):
            raise CommandError('Compare must run before switching from old storage')
        names = set()
        for model in (Document, TaskFile, WikiArticleFile, MeropriyatieFile):
            names.update(n for n in model.objects.values_list('file', flat=True) if n)
        errors = 0
        for name in sorted(names):
            try:
                if not storage.exists(name):
                    self.stderr.write('MISSING: ' + name)
                    errors += 1
                elif options['compare'] and digest(storage, name) != digest(default_storage, name):
                    self.stderr.write('DIFFERENT: ' + name)
                    errors += 1
                else:
                    self.stdout.write('OK: ' + name)
            except Exception as exc:
                errors += 1
                self.stderr.write('ERROR: %s (%s)' % (name, type(exc).__name__))
        if errors:
            raise CommandError('File errors: %s; do not switch storage yet' % errors)
        if options['write_test']:
            # Unique disposable file; only this file is deleted.
            name = 'test/synology_probe_' + uuid4().hex + '.txt'
            payload = 'Проверка Synology: upload/read/delete\n'.encode('utf-8')
            saved = None
            try:
                saved = storage.save(name, ContentFile(payload))
                with storage.open(saved) as f:
                    if f.read() != payload:
                        raise CommandError('Write/read mismatch')
            finally:
                if saved:
                    storage.delete(saved)
            self.stdout.write('Upload / read / delete: OK')
        self.stdout.write(self.style.SUCCESS('Referenced files verified: %s' % len(names)))
