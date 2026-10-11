"""
URL маршруты для приложения tasks.
"""
from django.urls import path
from . import views
from . import archive

urlpatterns = [
    path('', views.task_list_view, name='task_list'),
    path('archive/', views.task_archive_view, name='task_archive'),
    path('archive/bulk/', archive.bulk_archive, name='task_bulk_archive'),
    path('kanban/', views.kanban_view, name='kanban'),
    path('create/', views.task_create_view, name='task_create'),
    path('<int:task_id>/', views.task_detail_view, name='task_detail'),
    path('<int:task_id>/edit/', views.task_update_view, name='task_update'),
    path('<int:task_id>/delete/', views.task_delete_view, name='task_delete'),
    path('<int:task_id>/archive/', views.task_archive_toggle_view, name='task_archive_toggle'),
    path('<int:task_id>/update-status/', views.update_task_status_ajax, name='update_task_status'),
]
