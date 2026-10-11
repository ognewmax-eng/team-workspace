"""
URL маршруты для приложения schedule.
"""
from django.urls import path
from . import views, planner

urlpatterns = [
    path('lessons/<int:lesson_id>/duplicate/', planner.duplicate_lesson, name='lesson_duplicate'),
    path('lessons/template/<int:template_id>/preview/', planner.template_preview, name='template_preview'),
    path('<int:event_id>/delete/', planner.delete_event, name='schedule_event_delete'),
    path('', views.schedule_main_view, name='schedule_main'),
    path('calendar/', views.schedule_calendar_view, name='schedule_calendar'),
    path('list/', views.schedule_list_view, name='schedule_list'),
    path('events.json', views.schedule_events_json, name='schedule_events_json'),
    path('create/', views.schedule_event_create_view, name='schedule_event_create'),
    path('<int:event_id>/', views.schedule_event_detail_view, name='schedule_event_detail'),
    path('<int:event_id>/edit/', views.schedule_event_update_view, name='schedule_event_update'),
    # Расписание занятий
    path('lessons/', views.lessons_schedule_view, name='lessons_schedule'),
    path('lessons/create/', views.lesson_create_view, name='lesson_create'),
    path('lessons/<int:lesson_id>/update/', views.lesson_update_view, name='lesson_update'),
    path('lessons/<int:lesson_id>/delete/', views.lesson_delete_view, name='lesson_delete'),
    path('lessons/<int:lesson_id>/move/', views.lesson_move_view, name='lesson_move'),
    path('lessons/template/create/', views.create_template_from_schedule_view, name='create_template_from_schedule'),
    path('lessons/template/apply/', views.apply_template_view, name='apply_template'),
    path('lessons/template/<int:template_id>/delete/', views.delete_template_view, name='delete_template'),
    path('lessons/clear-week/', views.clear_week_view, name='clear_week'),
    # Экспорт расписания
    path('lessons/export/pdf/', views.export_lessons_schedule_pdf, name='export_lessons_schedule_pdf'),
    path('lessons/export/excel/', views.export_lessons_schedule_excel, name='export_lessons_schedule_excel'),
    path('lessons/export/pdf-all/', views.export_lessons_schedule_pdf_all, name='export_lessons_schedule_pdf_all'),
    path('lessons/export/excel-all/', views.export_lessons_schedule_excel_all, name='export_lessons_schedule_excel_all'),
]

