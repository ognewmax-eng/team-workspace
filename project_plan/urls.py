"""
URL configuration for project_plan project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .admin import configure_admin

configure_admin()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('tasks/', include('tasks.urls')),
    path('schedule/', include('schedule.urls')),
    path('analytics/', include('analytics.urls')),
    path('wiki/', include('wiki.urls')),
    path('events/', include('events.urls')),
    path('documents/', include('documents.urls')),
]

from accounts.synology_views import synology_file

urlpatterns += [
    path('private-files/<path:name>', synology_file, name='synology_file'),
]
