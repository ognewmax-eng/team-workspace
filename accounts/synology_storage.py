"""Private Synology WebDAV storage for Django 4.2 / Python 3.8."""
import json
import posixpath
import tempfile
from pathlib import Path
from urllib.parse import quote, urlsplit
from uuid import uuid4

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.core.files import File
from django.core.files.storage import Storage
from django.core import signing
from django.urls import reverse
from django.utils.deconstruct import deconstructible


def clean_name(name):
    name = str(name)
    parts = name.split('/')
    if (not name or name.startswith('/') or '\\' in name
            or any(p in ('', '.', '..') or p.startswith('#') for p in parts)
            or any(ord(c) < 32 for c in name)):
        raise SuspiciousFileOperation('Invalid storage path')
    return name


def signature(name):
    return signing.Signer(salt='synology-private-file').signature(clean_name(name))


@deconstructible
class SynologyStorage(Storage):
    def __init__(self):
        config_path = getattr(settings, 'SYNOLOGY_CONFIG_FILE',
                              str(Path(settings.BASE_DIR).parents[1] / 'synology-job.json'))
        try:
            with open(config_path, encoding='utf-8') as f:
                config = json.load(f)
            self.base_url = config['url'].rstrip('/') + '/'
            self.auth = (config['username'], config['password'])
        except (OSError, KeyError, ValueError):
            raise ImproperlyConfigured('Create the private Synology config file') from None
        parsed = urlsplit(self.base_url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise ImproperlyConfigured('Synology URL must use HTTPS without credentials or query')
        if not all(self.auth):
            raise ImproperlyConfigured('Synology credentials are empty')

    def _url(self, name):
        return self.base_url + quote(clean_name(name), safe='/')

    def _request(self, method, name, **kwargs):
        try:
            return requests.request(method, self._url(name), auth=self.auth,
                                    timeout=(15, 120), allow_redirects=False,
                                    verify=True, **kwargs)
        except requests.RequestException:
            raise IOError('Synology connection failed') from None

    @staticmethod
    def _expect(response, codes):
        if response.status_code not in codes:
            raise IOError('Synology returned HTTP %s' % response.status_code)

    def _open(self, name, mode='rb'):
        if mode not in ('r', 'rb'):
            raise ValueError('Storage.open supports reading only')
        temp = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode='w+b')
        try:
            with self._request('GET', name, stream=True) as response:
                if response.status_code == 404:
                    raise FileNotFoundError(name)
                self._expect(response, (200,))
                for chunk in response.iter_content(64 * 1024):
                    temp.write(chunk)
            temp.seek(0)
            return File(temp, name=name)
        except Exception:
            temp.close()
            raise

    def _save(self, name, content):
        name = clean_name(name)
        parts = name.split('/')[:-1]
        for i in range(1, len(parts) + 1):
            with self._request('MKCOL', '/'.join(parts[:i])) as response:
                if response.status_code == 405:
                    # Existing collection; prove it exists rather than hiding method errors.
                    with self._request('PROPFIND', '/'.join(parts[:i]), headers={'Depth': '0'}) as probe:
                        self._expect(probe, (207,))
                else:
                    self._expect(response, (201,))
        with tempfile.TemporaryFile(mode='w+b') as temp:
            for chunk in content.chunks():
                temp.write(chunk)
            for attempt in range(5):
                temp.seek(0)
                with self._request('PUT', name, data=temp,
                                   headers={'If-None-Match': '*', 'Content-Type': 'application/octet-stream'}) as response:
                    if response.status_code == 412:
                        parent, basename = posixpath.split(name)
                        root, ext = posixpath.splitext(basename)
                        name = posixpath.join(parent, root + '_' + uuid4().hex[:7] + ext)
                        continue
                    self._expect(response, (201,))
                    return name
        raise IOError('Could not allocate a unique filename')

    def exists(self, name):
        with self._request('HEAD', name) as response:
            if response.status_code == 404:
                return False
            self._expect(response, (200, 204))
            return True

    def size(self, name):
        with self._request('HEAD', name) as response:
            if response.status_code == 404:
                raise FileNotFoundError(name)
            self._expect(response, (200, 204))
            return int(response.headers['Content-Length'])

    def delete(self, name):
        with self._request('DELETE', name) as response:
            self._expect(response, (200, 204, 404))

    def url(self, name):
        name = clean_name(name)
        return reverse('synology_file', kwargs={'name': name}) + '?sig=' + signature(name)
