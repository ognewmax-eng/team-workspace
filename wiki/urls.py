"""
URL маршруты для приложения wiki.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.wiki_list_view, name='wiki_list'),
    path('create/', views.wiki_create_view, name='wiki_create'),
    path('preview/', views.wiki_preview_view, name='wiki_preview'),
    path('<int:article_id>/', views.wiki_detail_view, name='wiki_detail'),
    path('<int:article_id>/edit/', views.wiki_update_view, name='wiki_update'),
    path('<int:article_id>/delete/', views.wiki_delete_view, name='wiki_delete'),
    path('<int:article_id>/restore/', views.wiki_restore_view, name='wiki_restore'),
    path('<int:article_id>/history/<int:revision_id>/', views.wiki_revision_view, name='wiki_revision'),
    path('<int:article_id>/add-file/', views.wiki_add_file_view, name='wiki_add_file'),
    path('file/<int:file_id>/delete/', views.wiki_delete_file_view, name='wiki_delete_file'),
]
