import os,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','project_plan.settings')
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
while True:
    if settings.EMAIL_HOST:
        try:call_command('process_mailings')
        except Exception:print('Mailing worker failed; check server logs without exposing credentials.',flush=True)
    time.sleep(60)
