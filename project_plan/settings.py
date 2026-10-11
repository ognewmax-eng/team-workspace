"""Portable configuration. No organization credentials or production defaults."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
BASE_DIR=Path(__file__).resolve().parent.parent
CONFIG_FILE=Path(os.environ.get('WORKSPACE_CONFIG',BASE_DIR/'.env'))
load_dotenv(CONFIG_FILE,override=False)
def flag(name,default=False):return os.environ.get(name,str(default)).lower() in ('1','true','yes')
SECRET_KEY=os.environ.get('SECRET_KEY','')
if len(SECRET_KEY)<50:raise ImproperlyConfigured('Run python install.py to generate a private configuration.')
DEBUG=flag('DEBUG')
SITE_NAME=os.environ.get('ORGANIZATION_NAME','Рабочее пространство')
SITE_URL=os.environ.get('SITE_URL','http://localhost:8080').rstrip('/')
parsed=urlsplit(SITE_URL)
if parsed.scheme not in ['http','https'] or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
    raise ImproperlyConfigured('SITE_URL must be a plain http(s) origin.')
SITE_DOMAIN=parsed.netloc
ALLOWED_HOSTS=[x.strip() for x in os.environ.get('ALLOWED_HOSTS',parsed.hostname).split(',') if x.strip()]
CSRF_TRUSTED_ORIGINS=[SITE_URL]
DATA_DIR=Path(os.environ.get('DATA_DIR',BASE_DIR/'data')).resolve();DATA_DIR.mkdir(parents=True,exist_ok=True,mode=0o700)
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':DATA_DIR/'db.sqlite3','OPTIONS':{'timeout':30}}}
INSTALLED_APPS=['admin_interface','colorfield','django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','accounts','tasks','schedule','analytics','wiki','events','documents']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware','accounts.middleware.ActivityLogMiddleware']
ROOT_URLCONF='project_plan.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.debug','django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages','accounts.context_processors.user_theme_settings','accounts.branding.organization']}}]
WSGI_APPLICATION='project_plan.wsgi.application'
AUTH_USER_MODEL='accounts.User'
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.'+x} for x in ['UserAttributeSimilarityValidator','MinimumLengthValidator','CommonPasswordValidator','NumericPasswordValidator']]
LANGUAGE_CODE='ru-ru';TIME_ZONE=os.environ.get('TIME_ZONE','Europe/Moscow');USE_I18N=True;USE_TZ=True
STATIC_URL='/static/';STATIC_ROOT=DATA_DIR/'staticfiles';STATICFILES_DIRS=[BASE_DIR/'static']
MEDIA_URL='/private-files/';MEDIA_ROOT=DATA_DIR/'media'
STORAGES={'default':{'BACKEND':'accounts.local_storage.PrivateLocalStorage'},'staticfiles':{'BACKEND':'whitenoise.storage.CompressedStaticFilesStorage'}}
SYNOLOGY_CONFIG_FILE=os.environ.get('SYNOLOGY_CONFIG_FILE',str(DATA_DIR/'synology.json'))
if os.environ.get('FILE_STORAGE','local')=='synology':STORAGES['default']['BACKEND']='accounts.synology_storage.SynologyStorage'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
LOGIN_URL='/login/';LOGIN_REDIRECT_URL='/dashboard/';LOGOUT_REDIRECT_URL='/'
EMAIL_HOST=os.environ.get('EMAIL_HOST','');EMAIL_PORT=int(os.environ.get('EMAIL_PORT','587'))
EMAIL_HOST_USER=os.environ.get('EMAIL_HOST_USER','');EMAIL_HOST_PASSWORD=os.environ.get('EMAIL_HOST_PASSWORD','')
EMAIL_USE_SSL=flag('EMAIL_USE_SSL');EMAIL_USE_TLS=flag('EMAIL_USE_TLS',True)
if EMAIL_USE_SSL and EMAIL_USE_TLS:raise ImproperlyConfigured('Choose SSL or STARTTLS, not both.')
EMAIL_TIMEOUT=30;DEFAULT_FROM_EMAIL=os.environ.get('DEFAULT_FROM_EMAIL','notifications@example.org');SERVER_EMAIL=DEFAULT_FROM_EMAIL
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST else 'accounts.mail_backend.DisabledEmailBackend'
TELEGRAM_BOT_TOKEN=os.environ.get('TELEGRAM_BOT_TOKEN','');TELEGRAM_WEBHOOK_URL=SITE_URL+'/telegram/webhook/'
GOOGLE_CALENDAR_CLIENT_ID=os.environ.get('GOOGLE_CALENDAR_CLIENT_ID','');GOOGLE_CALENDAR_CLIENT_SECRET=os.environ.get('GOOGLE_CALENDAR_CLIENT_SECRET','')
YANDEX_DISK_TOKEN='';YANDEX_DISK_ROOT_PATH='/WorkspaceMedia';YANDEX_DISK_BACKUP_PATH='/WorkspaceBackups'
SECURE_SSL_REDIRECT=parsed.scheme=='https';SESSION_COOKIE_SECURE=SECURE_SSL_REDIRECT;CSRF_COOKIE_SECURE=SECURE_SSL_REDIRECT
if flag('TRUST_PROXY'):SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
SECURE_CONTENT_TYPE_NOSNIFF=True;X_FRAME_OPTIONS='SAMEORIGIN'
LOGGING={'version':1,'disable_existing_loggers':False,'handlers':{'console':{'class':'logging.StreamHandler'}},'root':{'handlers':['console'],'level':'INFO'}}
