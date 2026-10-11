"""
Views для управления задачами и канбан-доской.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from .models import Task, TaskComment, TaskFile, TaskAssignee
from .forms import TaskForm, TaskCommentForm, TaskFileForm
from accounts.models import Department, Notification
from accounts.signals import create_notification
from accounts.google_calendar import sync_task_to_google_calendar, delete_task_from_google_calendar
from schedule.models import ScheduleEvent
from datetime import timedelta
from .workspace import visible_tasks, can_edit_task, task_version

User = get_user_model()


def sync_task_assignees(task, users):
    """
    Синхронизировать назначения задачи с списком пользователей.
    Создаёт TaskAssignee для новых, удаляет для снятых. Существующие назначения не трогает.
    """
    users = list(users) if users else []
    new_ids = {u.id for u in users}
    TaskAssignee.objects.filter(task=task).exclude(user_id__in=new_ids).delete()
    for user in users:
        TaskAssignee.objects.get_or_create(
            task=task,
            user=user,
            defaults={'status': 'assigned'},
        )


def sync_task_to_schedule(task):
    """
    Синхронизация задачи с расписанием.
    Создает или обновляет событие в расписании для задачи с дедлайном.
    """
    if not task.deadline or not task.department:
        # Если нет дедлайна или отдела, удаляем связанное событие, если оно есть
        try:
            if hasattr(task, 'schedule_events'):
                task.schedule_events.all().delete()
        except Exception:
            pass
        return None
    
    # Время начала — за час до дедлайна, включая просроченные задачи.
    start_time = task.deadline - timedelta(hours=1)
    
    end_time = task.deadline
    
    # Проверяем, есть ли уже связанное событие
    try:
        schedule_event = task.schedule_events.first()
    except Exception:
        schedule_event = None
    
    if schedule_event:
        # Обновляем существующее событие
        schedule_event.title = f"📋 {task.title}"
        schedule_event.description = task.description or f"Задача: {task.title}"
        schedule_event.start_time = start_time
        schedule_event.end_time = end_time
        schedule_event.event_type = 'task'
        schedule_event.department = task.department
        schedule_event.save()
        
        # Обновляем участников
        schedule_event.participants.clear()
        for assignee in task.assigned_to.all():
            schedule_event.participants.add(assignee)
        
        # Если нет исполнителей, добавляем создателя задачи как участника
        if not task.assigned_to.exists() and task.created_by:
            schedule_event.participants.add(task.created_by)
    else:
        # Создаем новое событие
        schedule_event = ScheduleEvent.objects.create(
            title=f"📋 {task.title}",
            description=task.description or f"Задача: {task.title}",
            event_type='task',
            department=task.department,
            created_by=task.created_by,
            start_time=start_time,
            end_time=end_time,
            related_task=task
        )
        
        # Добавляем всех исполнителей как участников
        for assignee in task.assigned_to.all():
            schedule_event.participants.add(assignee)
        
        # Если нет исполнителей, добавляем создателя задачи как участника
        if not task.assigned_to.exists() and task.created_by:
            schedule_event.participants.add(task.created_by)
    
    return schedule_event


def remove_task_from_schedule(task):
    """
    Удаление задачи из расписания.
    """
    if hasattr(task, 'schedule_events'):
        task.schedule_events.all().delete()


@login_required
def task_list_view(request):
    from .workspace import workspace_context
    return render(request, 'tasks/task_list.html', workspace_context(request))


@login_required
def task_archive_view(request):
    from .workspace import workspace_context
    return render(request, 'tasks/task_archive.html', workspace_context(request, archived=True))


@login_required
def task_archive_toggle_view(request, task_id):
    """
    Переключение задачи в архив / из архива. POST только. Только директор.
    """
    task = get_object_or_404(Task, id=task_id)

    if not request.user.is_director():
        messages.error(request, 'Архивировать задачи может только директор.')
        return redirect('task_list')

    if request.method != 'POST':
        return redirect('task_detail', task_id=task.id)

    task.is_archived = not task.is_archived
    task.save()
    action = 'в архив' if task.is_archived else 'из архива'
    messages.success(request, f'Задача "{task.title}" отправлена {action}.')

    if task.is_archived:
        return redirect('task_archive')
    return redirect('task_detail', task_id=task.id)


@login_required
def kanban_view(request):
    from .workspace import workspace_context
    return render(request, 'tasks/kanban.html', workspace_context(request, board=True))


@login_required
def task_detail_view(request, task_id):
    """
    Детальная страница задачи с комментариями и файлами.
    """
    task = get_object_or_404(
        visible_tasks(request.user).select_related('parent_task', 'department', 'created_by', 'event_work__event__workspace')
        .prefetch_related('assigned_to', 'assignments__user', 'departments'),
        id=task_id
    )

    is_assigned = request.user in task.assigned_to.all()

    # Назначение текущего пользователя (для блока «Мой статус»)
    my_assignment = None
    if is_assigned:
        my_assignment = next((a for a in task.assignments.all() if a.user_id == request.user.id), None)

    # Оптимизация: используем select_related для комментариев и файлов
    comments = task.comments.select_related('author').all()
    files = task.files.select_related('uploaded_by').all()
    subtasks = visible_tasks(request.user).filter(parent_task=task).select_related('department', 'created_by').prefetch_related('assigned_to')
    comment_form = TaskCommentForm()
    file_form = TaskFileForm()

    if request.method == 'POST':
        if task.is_archived:
            messages.error(request, 'Верните задачу из архива перед изменением.')
            return redirect('task_detail', task_id=task.id)
        if 'add_comment' in request.POST:
            comment_form = TaskCommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.task = task
                comment.author = request.user
                comment.save()
                messages.success(request, 'Комментарий добавлен.')
                return redirect('task_detail', task_id=task.id)

        elif 'upload_file' in request.POST:
            file_form = TaskFileForm(request.POST, request.FILES)
            if file_form.is_valid():
                file_obj = file_form.save(commit=False)
                file_obj.task = task
                file_obj.uploaded_by = request.user
                file_obj.save()
                messages.success(request, 'Файл загружен.')
                return redirect('task_detail', task_id=task.id)

        elif 'update_status' in request.POST:
            response = update_task_status_ajax(request, task.pk)
            import json
            result = json.loads(response.content)
            (messages.success if result.get('success') else messages.error)(request, result.get('message','Проверьте результат после обновления.'))
            return redirect('task_detail', task_id=task.pk)

    from events.collaboration import linked_task, is_closed, can_manage
    event_link = linked_task(task)
    task_closed = bool(event_link and is_closed(event_link.event))
    can_complete = not event_link or can_manage(request.user,event_link.event)
    can_change_status = my_assignment is not None or (request.user.is_director() and not is_assigned)

    context = {
        'task': task,
        'comments': comments,
        'files': files,
        'subtasks': subtasks,
        'comment_form': comment_form,
        'file_form': file_form,
        'my_assignment': my_assignment,
        'assignments': task.assignments.select_related('user').all(),
        'can_change_status': can_change_status and not task.is_archived and not task_closed,
        'can_complete_task':can_complete,'status_version':task_version(task),
        'can_edit_task': can_edit_task(request.user, task),
        'visible_parent_task': visible_tasks(request.user).filter(pk=task.parent_task_id).first() if task.parent_task_id else None,
    }
    return render(request, 'tasks/task_detail.html', context)


@login_required
def task_create_view(request):
    """
    Создание новой задачи.
    """
    parent_task_id = request.GET.get('parent')
    parent_task = None
    if parent_task_id:
        parent_task = Task.objects.prefetch_related('departments').filter(id=parent_task_id).first()
    
    if request.method == 'POST':
        # Валидируем форму (поле files не входит в форму, обрабатывается отдельно)
        form = TaskForm(request.POST, user=request.user)
        
        # Обрабатываем файлы отдельно
        uploaded_files = request.FILES.getlist('files') if 'files' in request.FILES else []
        
        if form.is_valid():
            departments_list = list(form.cleaned_data.get('departments') or [])
            if not departments_list:
                form.add_error('departments', 'Выберите хотя бы один отдел.')
                return render(request, 'tasks/task_form.html', {
                    'form': form,
                    'title': 'Создать подзадачу' if parent_task else 'Создать задачу',
                    'parent_task': parent_task,
                })
            task = form.save(commit=False)
            task.created_by = request.user
            task.department = departments_list[0]
            # Если parent_task был передан через GET и не выбран в форме, используем его
            if parent_task and not form.cleaned_data.get('parent_task'):
                task.parent_task = parent_task
            # Если parent_task выбран в форме, используем его
            elif form.cleaned_data.get('parent_task'):
                task.parent_task = form.cleaned_data.get('parent_task')
            task.save()
            form.save_m2m()  # сохраняем departments (M2M)

            # Назначения через TaskAssignee (through-модель)
            sync_task_assignees(task, form.cleaned_data.get('assigned_to') or [])

            # Обработка загруженных файлов
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    TaskFile.objects.create(
                        task=task,
                        file=uploaded_file,
                        uploaded_by=request.user,
                        description=''
                    )
                messages.success(request, f'Задача создана. Загружено файлов: {len(uploaded_files)}')
            
            # Создаем уведомления для назначенных исполнителей
            assigned_users = task.assigned_to.all()
            for assignee in assigned_users:
                # Не отправляем уведомление, если пользователь сам создал задачу и назначил её себе
                if assignee != request.user:
                    message = f'Вам назначена задача "{task.title}"'
                    message += f' от {request.user.get_full_name() or request.user.username}'
                    create_notification(
                        user=assignee,
                        notification_type='task_assigned',
                        message=message,
                        related_task=task
                    )
            
            # Синхронизация с расписанием
            if task.deadline and task.department:
                try:
                    sync_task_to_schedule(task)
                except Exception as e:
                    # Логируем ошибку, но не прерываем создание задачи
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Ошибка синхронизации задачи с расписанием: {str(e)}")
            
            # Синхронизация с Google Calendar
            if task.assigned_to.exists() and task.deadline:
                try:
                    sync_task_to_google_calendar(task)
                except Exception as e:
                    # Логируем ошибку, но не прерываем создание задачи
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Ошибка синхронизации задачи с Google Calendar: {str(e)}")
            
            if not uploaded_files:
                messages.success(request, 'Задача успешно создана.')
            return redirect('task_detail', task_id=task.id)
    else:
        form = TaskForm(user=request.user)
        # Если есть родительская задача, устанавливаем её по умолчанию
        if parent_task:
            form.fields['parent_task'].initial = parent_task.id
            # Отделы по умолчанию — из родительской задачи
            if getattr(parent_task, 'departments', None) and parent_task.departments.exists():
                form.fields['departments'].initial = list(parent_task.departments.values_list('id', flat=True))
            elif parent_task.department:
                form.fields['departments'].initial = [parent_task.department.id]

    return render(request, 'tasks/task_form.html', {
        'form': form, 
        'title': 'Создать подзадачу' if parent_task else 'Создать задачу',
        'parent_task': parent_task
    })


@login_required
def task_update_view(request, task_id):
    """
    Редактирование задачи.
    """
    task = get_object_or_404(
        Task.objects.select_related('parent_task', 'department', 'created_by', 'event_work__event__workspace').prefetch_related('departments'),
        id=task_id
    )
    from events.collaboration import linked_task
    event_link = linked_task(task)
    if event_link:
        from events.work_views import task_form_view
        return task_form_view(request, pk=event_link.event_id, task_id=task.pk)

    if not can_edit_task(request.user, task):
        from django.http import Http404
        raise Http404

    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, instance=task, user=request.user)
        # Отделы задачи до сохранения — для не-директора не разрешаем снимать «чужие» отделы
        original_department_ids = set(task.departments.values_list('id', flat=True))
        if form.is_valid():
            departments_list = list(form.cleaned_data.get('departments') or [])
            if not departments_list:
                form.add_error('departments', 'Выберите хотя бы один отдел.')
                return render(request, 'tasks/task_form.html', {'form': form, 'task': task, 'title': 'Редактировать задачу'})
            # Сохраняем старый список исполнителей до сохранения
            old_assigned_to = set(task.assigned_to.all())
            # save(commit=False), т.к. assigned_to идёт через TaskAssignee — M2M с through
            # не сохраняется через form.save_m2m(); синхронизируем назначения вручную
            task = form.save(commit=False)
            task.save()
            form.save_m2m()  # сохраняем departments (M2M)
            # Не-директор не может снимать отделы, не входящие в его доступ: восстанавливаем их
            if not request.user.is_director() and original_department_ids:
                user_allowed_dept_ids = {request.user.department_id} if request.user.department_id else set()
                preserved_ids = original_department_ids - user_allowed_dept_ids
                submitted_ids = {d.id for d in departments_list}
                for dept_id in preserved_ids:
                    if dept_id not in submitted_ids:
                        task.departments.add(dept_id)
            # Инвариант: task.department = первый из task.departments (для расписания и др.)
            first_dept = task.departments.order_by('id').first()
            if first_dept is not None:
                task.department = first_dept
                task.save(update_fields=['department'])

            # Синхронизируем назначения через TaskAssignee (through-модель)
            new_users = form.cleaned_data.get('assigned_to') or []
            sync_task_assignees(task, new_users)
            new_assigned_to = set(task.assigned_to.all())

            # Находим новых исполнителей (которых не было в старом списке)
            new_assignees = new_assigned_to - old_assigned_to
            
            # Создаем уведомления для новых исполнителей
            for assignee in new_assignees:
                # Не отправляем уведомление, если пользователь сам назначил задачу себе
                if assignee != request.user:
                    message = f'Вам назначена задача "{task.title}"'
                    message += f' от {request.user.get_full_name() or request.user.username}'
                    create_notification(
                        user=assignee,
                        notification_type='task_assigned',
                        message=message,
                        related_task=task
                    )
            
            # Синхронизация с расписанием
            if task.deadline and task.department:
                try:
                    sync_task_to_schedule(task)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Ошибка синхронизации задачи с расписанием: {str(e)}")
            else:
                # Если дедлайн или отдел удалены, удаляем из расписания
                try:
                    remove_task_from_schedule(task)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Ошибка удаления задачи из расписания: {str(e)}")
            
            # Синхронизация с Google Calendar
            if task.assigned_to.exists() and task.deadline:
                try:
                    sync_task_to_google_calendar(task)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Ошибка синхронизации задачи с Google Calendar: {str(e)}")
            elif old_assigned_to:
                # Если исполнители изменились, удаляем событие у старых исполнителей
                removed_assignees = old_assigned_to - new_assigned_to
                for old_assignee in removed_assignees:
                    try:
                        delete_task_from_google_calendar(task, old_assignee)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Ошибка удаления задачи из Google Calendar: {str(e)}")
            
            messages.success(request, 'Задача обновлена.')
            return redirect('task_detail', task_id=task.id)
    else:
        form = TaskForm(instance=task, user=request.user)

    return render(request, 'tasks/task_form.html', {'form': form, 'task': task, 'title': 'Редактировать задачу'})


@login_required
def task_delete_view(request, task_id):
    """
    Удаление задачи (только для директора).
    """
    task = get_object_or_404(Task, id=task_id)
    
    # Проверка прав - только директор может удалять задачи
    if not request.user.is_director():
        messages.error(request, 'У вас нет прав на удаление задач.')
        return redirect('task_list')
    
    if request.method == 'POST':
        task_title = task.title
        # Удаляем из Google Calendar перед удалением задачи
        if task.assigned_to.exists() and task.google_calendar_event_id:
            try:
                delete_task_from_google_calendar(task)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка удаления задачи из Google Calendar: {str(e)}")
        
        task.delete()
        messages.success(request, f'Задача "{task_title}" успешно удалена.')
        return redirect('task_list')
    
    # GET запрос - показываем страницу подтверждения
    context = {
        'task': task,
    }
    return render(request, 'tasks/task_confirm_delete.html', context)


@login_required
def update_task_status_ajax(request, task_id):
    """Persist the personal or director status and return the actual aggregate."""
    from django.db import transaction, OperationalError
    from django.utils.crypto import constant_time_compare
    import logging
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не разрешён'}, status=405)
    new_status = request.POST.get('status')
    if new_status not in dict(Task.STATUS_CHOICES):
        return JsonResponse({'success': False, 'message': 'Неизвестный статус'}, status=400)
    try:
        with transaction.atomic():
            task = get_object_or_404(Task.objects.select_for_update(), pk=task_id)
            if not visible_tasks(request.user).filter(pk=task.pk).exists():
                from django.http import Http404
                raise Http404
            if task.is_archived:
                return JsonResponse({'success': False, 'message': 'Задача в архиве. Обновите страницу.'}, status=409)
            from events.collaboration import linked_task, is_closed, can_manage, log
            event_link = linked_task(task)
            if event_link:
                if is_closed(event_link.event):
                    return JsonResponse({'success': False, 'message': 'Мероприятие закрыто. Ответственный может вернуть его в подготовку.'}, status=409)
                if new_status == 'completed' and not can_manage(request.user, event_link.event):
                    return JsonResponse({'success': False, 'message': 'Отправьте результат на проверку. Завершение подтверждает ответственный мероприятия.'}, status=403)
            assignment = task.assignments.filter(user=request.user).first()
            if assignment is None and not request.user.is_director():
                return JsonResponse({'success': False, 'message': 'Менять статус может исполнитель или директор.'}, status=403)
            expected = request.POST.get('version')
            if expected and not constant_time_compare(expected, task_version(task)):
                return JsonResponse({'success': False, 'message': 'Задача изменилась. Обновите страницу и повторите действие.'}, status=409)
            if assignment is not None:
                old_status = assignment.status
                assignment.status = new_status
                assignment.save()
                task.update_aggregate_status()
                message = 'Ваш статус: %s. Общий статус: %s.' % (assignment.get_status_display(), task.get_status_display())
                if task.status_locked_by_director:
                    message += ' Общий статус зафиксирован директором.'
                notice = 'Исполнитель %s изменил свой статус по задаче «%s» на «%s»' % (request.user.get_full_name() or request.user.username, task.title, assignment.get_status_display())
            else:
                old_status = task.status
                task.status = new_status
                task.status_locked_by_director = True
                task.save()
                message = 'Общий статус задачи обновлён.'
                notice = 'Статус задачи «%s» изменён на «%s»' % (task.title, task.get_status_display())
            if event_link and old_status != new_status:
                log(event_link.event, request.user, 'Статус задачи «%s»: %s.' % (task.title, task.get_status_display()))
            result = {'success': True, 'message': message, 'status': task.status,
                      'status_label': task.get_status_display(),
                      'personal_status': assignment.status if assignment else None,
                      'version': task_version(task),
                      'completed_count': task.assignments.filter(status='completed').count(),
                      'assignee_count': task.assignments.count()}
    except OperationalError:
        return JsonResponse({'success': False, 'message': 'База занята другим изменением. Обновите страницу и повторите.'}, status=409)
    if old_status != new_status:
        try:
            recipients = set(task.assigned_to.all())
            if task.created_by: recipients.add(task.created_by)
            if event_link and event_link.event.responsible: recipients.add(event_link.event.responsible)
            recipients.discard(request.user)
            for user in recipients:
                create_notification(user=user, notification_type='task_status_changed', message=notice, related_task=task)
        except Exception:
            logging.getLogger(__name__).warning('Task status saved; notification failed', exc_info=False)
        try:
            if task.deadline and task.department_id: sync_task_to_schedule(task)
        except Exception:
            logging.getLogger(__name__).warning('Task status saved; schedule sync failed', exc_info=False)
    return JsonResponse(result)

