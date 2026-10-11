import hashlib,json,sqlite3,tarfile,tempfile
from datetime import datetime,timezone
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.db import connection
class Command(BaseCommand):
    help='Local backup: consistent SQLite snapshot and optional private local files.'
    def add_arguments(self,p):
        p.add_argument('--directory',required=True);p.add_argument('--include-media',action='store_true')
    def handle(self,*args,**options):
        directory=Path(options['directory']).resolve()
        if directory==settings.BASE_DIR or directory==settings.MEDIA_ROOT.resolve() or settings.MEDIA_ROOT.resolve() in directory.parents:raise CommandError('Выберите отдельный каталог копий.')
        directory.mkdir(parents=True,exist_ok=True);directory.chmod(0o700)
        if options['include_media'] and settings.STORAGES['default']['BACKEND']!='accounts.local_storage.PrivateLocalStorage':raise CommandError('Для внешнего хранилища настройте его собственное резервное копирование.')
        target=directory/('workspace_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.tar.gz')
        with tempfile.TemporaryDirectory() as tmp:
            snapshot=Path(tmp)/'db.sqlite3';connection.ensure_connection()
            with sqlite3.connect(snapshot) as dest:connection.connection.backup(dest)
            with sqlite3.connect(snapshot) as db:
                if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise CommandError('Проверка снимка не пройдена.')
            with tarfile.open(target,'x:gz') as archive:
                archive.add(snapshot,arcname='db.sqlite3')
                if options['include_media'] and settings.MEDIA_ROOT.exists():archive.add(settings.MEDIA_ROOT,arcname='media')
        target.chmod(0o600)
        self.stdout.write(str(target)+'\nSHA-256: '+hashlib.sha256(target.read_bytes()).hexdigest())
