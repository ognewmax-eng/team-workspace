"""
Storage backends для работы с внешними хранилищами файлов.
"""
from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils.deconstruct import deconstructible
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

try:
    import yadisk
    YADISK_AVAILABLE = True
except ImportError:
    YADISK_AVAILABLE = False
    logger.warning("Библиотека yadisk не установлена. Установите её: pip install yadisk")


@deconstructible
class YandexDiskStorage(Storage):
    """
    Storage backend для работы с Яндекс Диском через API.
    
    Требует настройки в settings.py:
    - YANDEX_DISK_TOKEN: OAuth токен для доступа к API
    - YANDEX_DISK_ROOT_PATH: корневой путь на Яндекс Диске (по умолчанию /DjangoMedia)
    - YANDEX_DISK_PUBLIC_URL_BASE: базовый URL для публичных ссылок (опционально)
    """
    
    def __init__(self):
        if not YADISK_AVAILABLE:
            raise ImportError(
                "Библиотека yadisk не установлена. "
                "Установите её командой: pip install yadisk"
            )
        
        self.token = getattr(settings, 'YANDEX_DISK_TOKEN', '')
        self.root_path = getattr(settings, 'YANDEX_DISK_ROOT_PATH', '/DjangoMedia')
        self.public_url_base = getattr(settings, 'YANDEX_DISK_PUBLIC_URL_BASE', '')
        self._client = None
        
        if not self.token:
            raise ValueError(
                "YANDEX_DISK_TOKEN должен быть установлен в settings.py. "
                "Получите токен через скрипт get_yandex_token.py"
            )
    
    def _get_client(self):
        """Получение клиента Яндекс Диска."""
        if self._client is None:
            self._client = yadisk.YaDisk(token=self.token)
            
            # Проверка подключения
            try:
                if not self._client.check_token():
                    raise ValueError("Неверный токен Яндекс Диска или токен истек")
            except Exception as e:
                logger.error(f"Ошибка проверки токена Яндекс Диска: {e}")
                raise ValueError(f"Ошибка подключения к Яндекс Диску: {e}")
        
        return self._client
    
    def _get_full_path(self, name):
        """Получение полного пути к файлу на Яндекс Диске."""
        # Убираем начальный слэш, если есть
        name = name.lstrip('/')
        # Объединяем с корневым путем
        full_path = os.path.join(self.root_path, name).replace('\\', '/')
        # Убираем двойные слэши
        full_path = full_path.replace('//', '/')
        return full_path
    
    def _open(self, name, mode='rb'):
        """Открытие файла для чтения."""
        client = self._get_client()
        temp_path = None
        
        try:
            remote_path = self._get_full_path(name)
            
            # Создаем временный файл
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            # Скачиваем файл с Яндекс Диска
            client.download(remote_path, temp_path)
            
            # Читаем содержимое
            with open(temp_path, 'rb') as f:
                content = f.read()
            
            # Удаляем временный файл
            os.unlink(temp_path)
            
            return ContentFile(content)
        except yadisk.exceptions.PathNotFoundError:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            raise FileNotFoundError(f"Файл {name} не найден на Яндекс Диске")
        except Exception as e:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            logger.error(f"Ошибка при открытии файла {name}: {e}")
            raise IOError(f"Не удалось открыть файл {name}: {str(e)}")
    
    def _save(self, name, content):
        """Сохранение файла на Яндекс Диск."""
        client = self._get_client()
        temp_path = None
        
        try:
            remote_path = self._get_full_path(name)
            
            # Создаем директории, если нужно
            dir_path = os.path.dirname(remote_path)
            if dir_path and dir_path != '/':
                try:
                    # Проверяем, существует ли директория
                    client.get_meta(dir_path)
                except yadisk.exceptions.PathNotFoundError:
                    # Создаем директорию рекурсивно
                    parts = dir_path.strip('/').split('/')
                    current_path = ''
                    for part in parts:
                        current_path = f"{current_path}/{part}" if current_path else f"/{part}"
                        try:
                            client.get_meta(current_path)
                        except yadisk.exceptions.PathNotFoundError:
                            client.mkdir(current_path)
            
            # Сохраняем во временный файл
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_path = temp_file.name
            
            # Записываем содержимое
            if hasattr(content, 'read'):
                # Если content - это файловый объект, читаем его
                content.seek(0)  # Перемещаемся в начало файла
                temp_file.write(content.read())
            else:
                # Если content - это байты
                temp_file.write(content)
            temp_file.close()
            
            # Загружаем файл на Яндекс Диск
            client.upload(temp_path, remote_path, overwrite=True)
            
            # Удаляем временный файл
            os.unlink(temp_path)
            
            return name
        except Exception as e:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            logger.error(f"Ошибка при сохранении файла {name}: {e}")
            raise IOError(f"Не удалось сохранить файл {name}: {str(e)}")
    
    def delete(self, name):
        """Удаление файла с Яндекс Диска."""
        client = self._get_client()
        try:
            remote_path = self._get_full_path(name)
            client.remove(remote_path, permanently=True)
        except yadisk.exceptions.PathNotFoundError:
            # Файл уже не существует, это нормально
            pass
        except Exception as e:
            logger.error(f"Ошибка при удалении файла {name}: {e}")
            raise IOError(f"Не удалось удалить файл {name}: {str(e)}")
    
    def exists(self, name):
        """Проверка существования файла."""
        client = self._get_client()
        try:
            remote_path = self._get_full_path(name)
            client.get_meta(remote_path)
            return True
        except yadisk.exceptions.PathNotFoundError:
            return False
        except Exception:
            return False
    
    def url(self, name):
        """Получение публичной ссылки на файл."""
        client = self._get_client()
        try:
            remote_path = self._get_full_path(name)
            
            # Получаем публичную ссылку
            public_link = client.get_download_link(remote_path)
            
            # Если установлен базовый URL для публичных ссылок, используем его
            if self.public_url_base:
                # Можно использовать прокси через свой сервер
                return f"{self.public_url_base}/{name}"
            
            return public_link
        except Exception as e:
            logger.error(f"Ошибка при получении URL для файла {name}: {e}")
            # Возвращаем URL через свой сервер как fallback
            from django.urls import reverse
            try:
                return reverse('yandex_disk_file', args=[name])
            except:
                return f"/media/{name}"
    
    def size(self, name):
        """Получение размера файла."""
        client = self._get_client()
        try:
            remote_path = self._get_full_path(name)
            meta = client.get_meta(remote_path)
            return meta.size
        except Exception:
            return 0
    
    def listdir(self, path):
        """Список файлов и директорий."""
        client = self._get_client()
        try:
            remote_path = self._get_full_path(path)
            items = client.listdir(remote_path)
            dirs = []
            files = []
            for item in items:
                if item.type == 'dir':
                    dirs.append(item.name)
                else:
                    files.append(item.name)
            return dirs, files
        except Exception:
            return [], []
