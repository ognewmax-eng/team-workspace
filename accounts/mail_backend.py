from pathlib import Path
from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend
SENDER = settings.DEFAULT_FROM_EMAIL
FROM_EMAIL = settings.DEFAULT_FROM_EMAIL
def config_path(): return Path(settings.CONFIG_FILE)
def load_config():
    return dict(host=settings.EMAIL_HOST,port=settings.EMAIL_PORT,username=settings.EMAIL_HOST_USER,password=settings.EMAIL_HOST_PASSWORD,use_ssl=settings.EMAIL_USE_SSL,use_tls=settings.EMAIL_USE_TLS,timeout=30)
class PrivateSMTPBackend(EmailBackend):
    pass
from django.core.mail.backends.base import BaseEmailBackend
from django.core.exceptions import ImproperlyConfigured
class DisabledEmailBackend(BaseEmailBackend):
    def send_messages(self,email_messages):
        raise ImproperlyConfigured('SMTP is not configured.')
