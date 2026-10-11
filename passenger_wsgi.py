"""Point Passenger at this file and select .venv/bin/python in the hosting panel."""
import os,sys
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','project_plan.settings')
from django.core.wsgi import get_wsgi_application
application=get_wsgi_application()
