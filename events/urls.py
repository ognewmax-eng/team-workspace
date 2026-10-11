"""
URL маршруты для приложения events.
"""
from django.urls import path
from . import views, work_views, portfolio_views, import_views, finance_views

urlpatterns = [
    # Чек-листы
    path('forum-checklist/', views.forum_checklist_list_view, name='forum_checklist_list'),
    path('forum-checklist/create/', views.forum_checklist_create_view, name='forum_checklist_create'),
    path('forum-checklist/<int:checklist_id>/', views.forum_checklist_view, name='forum_checklist'),
    path('forum-checklist/<int:checklist_id>/ajax/', views.forum_checklist_ajax, name='forum_checklist_ajax'),
    path('meropriyatiya/<int:pk>/team/', work_views.team_view, name='event_team'),
    path('meropriyatiya/<int:pk>/workspace/', work_views.workspace_update, name='event_workspace_update'),
    path('meropriyatiya/<int:pk>/tasks/create/', work_views.task_form_view, name='event_task_create'),
    path('meropriyatiya/<int:pk>/tasks/<int:task_id>/edit/', work_views.task_form_view, name='event_task_edit'),
    path('meropriyatiya/<int:pk>/tasks/<int:task_id>/review/', work_views.review_task, name='event_task_review'),
    path('meropriyatiya/<int:pk>/notes/', work_views.add_note, name='event_add_note'),
    path('meropriyatiya/<int:pk>/files/', work_views.upload_files, name='event_upload_files'),
    path('meropriyatiya/<int:pk>/tasks/<int:task_id>/archive/', work_views.archive_task, name='event_task_archive'),
    # Мероприятия
    path('meropriyatiya/', portfolio_views.list_view, name='meropriyatie_list'),
    path('meropriyatiya/export/', portfolio_views.export_view, name='event_export'),
    path('meropriyatiya/import/', import_views.import_view, name='event_import'),
    path('meropriyatiya/import/template/', import_views.template_view, name='event_import_template'),
    path('meropriyatiya/import/<int:batch_id>/', import_views.preview_view, name='event_import_preview'),
    path('meropriyatiya/import/<int:batch_id>/commit/', import_views.commit_view, name='event_import_commit'),
    path('meropriyatiya/<int:pk>/finance/', finance_views.finance_view, name='event_finance'),
    path('meropriyatiya/<int:pk>/finance/export/', finance_views.finance_export, name='event_finance_export'),
    path('meropriyatiya/<int:pk>/finance/review/', finance_views.review_view, name='event_finance_review'),
    path('meropriyatiya/<int:pk>/finance/lines/add/', finance_views.line_view, name='event_finance_line_add'),
    path('meropriyatiya/<int:pk>/finance/lines/<int:line_id>/', finance_views.line_view, name='event_finance_line_edit'),
    path('meropriyatiya/<int:pk>/presets/', portfolio_views.presets_view, name='event_task_presets'),
    path('meropriyatiya/create/', work_views.event_form_view, name='meropriyatie_create'),
    path('meropriyatiya/<int:pk>/', work_views.detail_view, name='meropriyatie_detail'),
    path('meropriyatiya/<int:pk>/edit/', work_views.event_form_view, name='meropriyatie_update'),
    path('meropriyatiya/<int:pk>/delete/', work_views.delete_view, name='meropriyatie_delete'),
]
