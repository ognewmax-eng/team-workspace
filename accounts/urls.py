"""
URL маршруты для приложения accounts.
"""
from django.urls import path
from . import views
from . import profiles

# Безопасный импорт telegram_webhook
try:
    from .telegram_webhook import telegram_webhook
    TELEGRAM_WEBHOOK_AVAILABLE = True
except ImportError:
    # Если библиотека не установлена, создаем заглушку
    from django.http import HttpResponse
    def telegram_webhook(request):
        return HttpResponse('Telegram bot library not installed', status=503)
    TELEGRAM_WEBHOOK_AVAILABLE = False

urlpatterns = [
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('people/', profiles.colleagues, name='colleagues'),
    path('people/<int:user_id>/', profiles.colleague_profile, name='colleague_profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/change-password/', views.password_change_view, name='password_change'),
    path('profile/theme-settings/', views.theme_settings_view, name='theme_settings'),
    path('profile/theme-settings/ajax/', views.theme_settings_ajax, name='theme_settings_ajax'),
    path('pending-registrations/', views.pending_registrations_view, name='pending_registrations'),
    path('approve-user/<int:user_id>/', views.approve_user_view, name='approve_user'),
    path('reject-user/<int:user_id>/', views.reject_user_view, name='reject_user'),
    path('approve-user-ajax/<int:user_id>/', views.approve_user_ajax, name='approve_user_ajax'),
    # Уведомления
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/delete-read/', views.delete_read_notifications, name='delete_read_notifications'),
    path('notifications/count/', views.notifications_count_ajax, name='notifications_count_ajax'),
    path('notifications/list/', views.notifications_list_ajax, name='notifications_list_ajax'),
    # Google Calendar
    path('google-calendar/connect/', views.google_calendar_connect_view, name='google_calendar_connect'),
    path('google-calendar/callback/', views.google_calendar_callback_view, name='google_calendar_callback'),
    path('google-calendar/disconnect/', views.google_calendar_disconnect_view, name='google_calendar_disconnect'),
    # Telegram Bot Webhook
    path('telegram/webhook/', telegram_webhook, name='telegram_webhook'),
]
