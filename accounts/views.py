"""
Views для аутентификации и управления профилем.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from django.http import JsonResponse
from .models import User, Department, Notification
from .forms import UserRegistrationForm, UserProfileEditForm, PasswordChangeForm
from .google_calendar import GoogleCalendarService
from tasks.models import Task
from schedule.models import ScheduleEvent


def login_view(request):
    """Страница входа в систему."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.warning(
                    request,
                    'Ваш аккаунт еще не активирован администратором. '
                    'Пожалуйста, дождитесь одобрения регистрации.'
                )
                return render(request, 'accounts/login.html')
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.get_full_name() or user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль.')

    return render(request, 'accounts/login.html')


@login_required
def dashboard_view(request):
    """Единое рабочее пространство для всех пользователей."""
    from .studio import studio_dashboard
    return studio_dashboard(request)


@login_required
def profile_view(request):
    from .profiles import profile_page
    return profile_page(request)


@login_required
def profile_edit_view(request):
    from .profiles import edit_profile
    return edit_profile(request)


@login_required
def password_change_view(request):
    """Изменение пароля пользователя."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Пароль успешно изменен.')
            return redirect('profile')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
    }
    return render(request, 'accounts/password_change.html', context)


@login_required
def theme_settings_view(request):
    """Совместимость со старыми закладками страницы оформления."""
    return redirect('profile')


@login_required
def theme_settings_ajax(request):
    """Старый API оформления больше не изменяет настройки пользователя."""
    return JsonResponse({
        'success': False,
        'message': 'На сайте используется единое оформление.'
    }, status=410)


def logout_view(request):
    """Выход из системы."""
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы.')
    return redirect('login')


def register_view(request):
    """Страница регистрации нового пользователя."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                'Регистрация успешна! Ваш аккаунт ожидает одобрения администратора. '
                'Вы получите уведомление, когда администратор активирует ваш аккаунт.'
            )
            return redirect('login')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def pending_registrations_view(request):
    """Список пользователей, ожидающих одобрения (только для администраторов)."""
    pending_users = User.objects.filter(is_active=False).order_by('-date_joined')
    
    context = {
        'pending_users': pending_users,
        'pending_count': pending_users.count(),
    }
    return render(request, 'accounts/pending_registrations.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def approve_user_view(request, user_id):
    """Одобрение регистрации пользователя."""
    user = get_object_or_404(User, id=user_id, is_active=False)
    
    if request.method == 'POST':
        user.is_active = True
        user.save()
        messages.success(request, f'Пользователь {user.get_full_name() or user.username} успешно активирован.')
        return redirect('pending_registrations')
    
    context = {
        'user': user,
    }
    return render(request, 'accounts/approve_user.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def reject_user_view(request, user_id):
    """Отклонение регистрации пользователя."""
    user = get_object_or_404(User, id=user_id, is_active=False)
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'Регистрация пользователя {username} отклонена.')
        return redirect('pending_registrations')
    
    context = {
        'user': user,
    }
    return render(request, 'accounts/reject_user.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def approve_user_ajax(request, user_id):
    """AJAX-эндпоинт для быстрого одобрения пользователя."""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id, is_active=False)
        user.is_active = True
        user.save()
        return JsonResponse({'success': True, 'message': 'Пользователь активирован'})
    return JsonResponse({'success': False, 'message': 'Метод не разрешен'}, status=405)


@login_required
def notifications_view(request):
    """Страница со всеми уведомлениями пользователя."""
    # Оптимизация: используем select_related для related_task и агрегацию для подсчета
    notifications = Notification.objects.filter(user=request.user).select_related(
        'related_task', 'related_task__department', 'related_task__created_by'
    ).order_by('-created_at')
    
    # Оптимизация: подсчитываем одним запросом
    counts = Notification.objects.filter(user=request.user).aggregate(
        unread=Count('id', filter=Q(is_read=False)),
        read=Count('id', filter=Q(is_read=True))
    )
    unread_count = counts['unread']
    read_count = counts['read']
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
        'read_count': read_count,
    }
    return render(request, 'accounts/notifications.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """Отметить уведомление как прочитанное."""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Уведомление отмечено как прочитанное.')
    return redirect('notifications')


@login_required
def mark_all_notifications_read(request):
    """Отметить все уведомления как прочитанные."""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Все уведомления отмечены как прочитанные.')
    return redirect('notifications')


@login_required
def delete_read_notifications(request):
    """Удалить все прочитанные уведомления."""
    if request.method == 'POST':
        deleted_count = Notification.objects.filter(user=request.user, is_read=True).delete()[0]
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Удалено {deleted_count} прочитанных уведомлений',
                'deleted_count': deleted_count
            })
        
        messages.success(request, f'Удалено {deleted_count} прочитанных уведомлений.')
        return redirect('notifications')
    
    # GET запрос - показываем страницу подтверждения
    read_notifications_count = Notification.objects.filter(user=request.user, is_read=True).count()
    context = {
        'read_notifications_count': read_notifications_count,
    }
    return render(request, 'accounts/delete_read_notifications.html', context)


@login_required
def notifications_count_ajax(request):
    """AJAX-эндпоинт для получения количества непрочитанных уведомлений."""
    count = request.user.get_unread_notifications_count()
    return JsonResponse({'count': count})


@login_required
def notifications_list_ajax(request):
    """AJAX-эндпоинт для получения списка последних уведомлений."""
    try:
        # Оптимизация: используем select_related для related_task
        notifications = Notification.objects.filter(user=request.user).select_related(
            'related_task', 'related_task__department', 'related_task__created_by'
        ).order_by('-created_at')[:10]
        
        notifications_data = []
        for notification in notifications:
            try:
                task_url = None
                if notification.related_task:
                    try:
                        task_url = notification.related_task.get_absolute_url()
                    except Exception:
                        task_url = f'/tasks/{notification.related_task.id}/'
                
                notifications_data.append({
                    'id': notification.id,
                    'type': notification.notification_type,  # Ключ типа
                    'type_display': notification.get_notification_type_display(),  # Отображаемое значение
                    'message': notification.message,
                    'is_read': notification.is_read,
                    'created_at': notification.created_at.strftime('%d.%m.%Y %H:%M'),
                    'task_url': task_url,
                })
            except Exception as e:
                # Пропускаем уведомление с ошибкой, но логируем
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Ошибка обработки уведомления {notification.id}: {e}')
                continue
        
        return JsonResponse({
            'notifications': notifications_data,
            'unread_count': request.user.get_unread_notifications_count()
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Ошибка в notifications_list_ajax: {e}')
        return JsonResponse({
            'notifications': [],
            'unread_count': 0,
            'error': str(e)
        }, status=500)


@login_required
def google_calendar_connect_view(request):
    """Подключение Google Calendar."""
    from django.conf import settings
    
    # Проверяем, установлены ли библиотеки Google API
    try:
        from accounts.google_calendar import GOOGLE_API_AVAILABLE
        if not GOOGLE_API_AVAILABLE:
            messages.error(
                request,
                'Библиотеки Google API не установлены. Установите: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib'
            )
            return redirect('profile')
    except ImportError:
        messages.error(
            request,
            'Библиотеки Google API не установлены. Установите: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib'
        )
        return redirect('profile')
    
    # Проверяем настройки
    client_id = getattr(settings, 'GOOGLE_CALENDAR_CLIENT_ID', None)
    client_secret = getattr(settings, 'GOOGLE_CALENDAR_CLIENT_SECRET', None)
    
    if not client_id or not client_secret:
        messages.error(
            request,
            'Google Calendar не настроен. Добавьте GOOGLE_CALENDAR_CLIENT_ID и GOOGLE_CALENDAR_CLIENT_SECRET в файл .env или settings.py. '
            'См. инструкцию: docs/GOOGLE_CALENDAR_SETUP.md'
        )
        return redirect('profile')
    
    service = GoogleCalendarService(request.user)
    auth_url = service.get_authorization_url(request)
    
    if auth_url:
        return redirect(auth_url)
    else:
        messages.error(
            request,
            'Не удалось получить URL для авторизации Google Calendar. Проверьте настройки GOOGLE_CALENDAR_CLIENT_ID и GOOGLE_CALENDAR_CLIENT_SECRET.'
        )
        return redirect('profile')


@login_required
def google_calendar_callback_view(request):
    """Обработка callback от Google OAuth."""
    code = request.GET.get('code')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f'Ошибка авторизации Google Calendar: {error}')
        return redirect('profile')
    
    if not code:
        messages.error(request, 'Код авторизации не получен.')
        return redirect('profile')
    
    service = GoogleCalendarService(request.user)
    success = service.handle_callback(request, code)
    
    if success:
        messages.success(request, 'Google Calendar успешно подключен! События будут автоматически синхронизироваться.')
    else:
        messages.error(request, 'Не удалось подключить Google Calendar. Попробуйте еще раз.')
    
    return redirect('profile')


@login_required
def google_calendar_disconnect_view(request):
    """Отключение Google Calendar."""
    if request.method == 'POST':
        service = GoogleCalendarService(request.user)
        service.disconnect()
        messages.success(request, 'Google Calendar отключен.')
        return redirect('profile')
    
    return redirect('profile')

