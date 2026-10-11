from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from .synology_storage import clean_name,signature
class PrivateLocalStorage(FileSystemStorage):
    def url(self,name):
        name=clean_name(name)
        return reverse('synology_file',kwargs={'name':name})+'?sig='+signature(name)
