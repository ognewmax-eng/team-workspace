"""
Views для управления чек-листами форумов.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from .models import ForumChecklist, ChecklistBlock, ChecklistTask, ChecklistTaskComment, Meropriyatie, MeropriyatieFile
from .forms import MeropriyatieForm
from accounts.models import Department
from datetime import timedelta

User = get_user_model()


@login_required
def forum_checklist_view(request, checklist_id=None):
    """
    Главная страница чек-листа форума с интерактивным интерфейсом.
    Доступ открыт для всех пользователей.
    """
    if checklist_id:
        checklist = get_object_or_404(ForumChecklist, id=checklist_id)
        # Доступ открыт для всех авторизованных пользователей
    else:
        # Создаем новый чек-лист или получаем последний
        checklist = ForumChecklist.objects.filter(created_by=request.user).first()
        if not checklist:
            # Если чек-лист не найден, перенаправляем на создание
            messages.info(request, 'Создайте новый чек-лист, выбрав шаблон и блоки.')
            return redirect('forum_checklist_create')
    
    # Получаем блоки с задачами и комментариями
    blocks = checklist.blocks.prefetch_related('tasks__comments__author').order_by('order')
    
    # Получаем участников
    participants = checklist.participants.all()
    
    # Получаем всех пользователей для выбора
    all_users = User.objects.filter(is_active=True).order_by('last_name', 'first_name', 'username')
    
    import json
    # Для JavaScript передаем список имен участников
    participants_list = [user.get_full_name() or user.username for user in participants]
    
    context = {
        'checklist': checklist,
        'blocks': blocks,
        'participants': participants,
        'all_users': all_users,
        'participants_json': json.dumps(participants_list),
    }
    return render(request, 'events/forum_checklist.html', context)


@login_required
def forum_checklist_list_view(request):
    """
    Список всех чек-листов форума.
    Показывает чек-листы, где пользователь является участником или создателем.
    """
    user = request.user
    
    # Получаем чек-листы, где пользователь является участником или создателем
    checklists = ForumChecklist.objects.filter(
        Q(participants=user) | Q(created_by=user)
    ).distinct().order_by('-created_at')
    
    # Директор и сотрудники видят все чек-листы
    if user.is_director() or user.is_staff:
        checklists = ForumChecklist.objects.all().order_by('-created_at')
    
    context = {
        'checklists': checklists,
    }
    return render(request, 'events/forum_checklist_list.html', context)


# Шаблоны блоков для чек-листов
CHECKLIST_TEMPLATES = {
    'full': {
        'name': 'Полный шаблон',
        'description': 'Все блоки для комплексного планирования форума',
        'blocks': [
            ('БЛОК 1: КОНЦЕПЦИЯ И СТРАТЕГИЯ', 1),
            ('БЛОК 2: ОРГКОМИТЕТ И КОМАНДА', 2),
            ('БЛОК 3: ФИНАНСИРОВАНИЕ', 3),
            ('БЛОК 4: УЧАСТНИКИ', 4),
            ('БЛОК 5: ПРОГРАММА', 5),
            ('БЛОК 6: ЛОГИСТИКА', 6),
            ('БЛОК 7: ЗАВЕРШЕНИЕ', 7),
        ]
    },
    'minimal': {
        'name': 'Минимальный шаблон',
        'description': 'Основные блоки для быстрого планирования',
        'blocks': [
            ('БЛОК 1: КОНЦЕПЦИЯ И СТРАТЕГИЯ', 1),
            ('БЛОК 2: ОРГКОМИТЕТ И КОМАНДА', 2),
            ('БЛОК 5: ПРОГРАММА', 3),
            ('БЛОК 6: ЛОГИСТИКА', 4),
        ]
    },
    'custom': {
        'name': 'Кастомный',
        'description': 'Выберите нужные блоки самостоятельно',
        'blocks': []
    }
}

# Все доступные блоки для выбора
ALL_AVAILABLE_BLOCKS = [
    ('БЛОК 1: КОНЦЕПЦИЯ И СТРАТЕГИЯ', 'concept'),
    ('БЛОК 2: ОРГКОМИТЕТ И КОМАНДА', 'team'),
    ('БЛОК 3: ФИНАНСИРОВАНИЕ', 'finance'),
    ('БЛОК 4: УЧАСТНИКИ', 'participants'),
    ('БЛОК 5: ПРОГРАММА', 'program'),
    ('БЛОК 6: ЛОГИСТИКА', 'logistics'),
    ('БЛОК 7: ЗАВЕРШЕНИЕ', 'completion'),
]


@login_required
def forum_checklist_create_view(request):
    """
    Создание нового чек-листа форума с выбором шаблона и блоков.
    """
    from accounts.models import User
    
    if request.method == 'POST':
        title = request.POST.get('title', 'Планирование форума')
        participant_ids = request.POST.getlist('participants')
        template_type = request.POST.get('template', 'full')
        selected_blocks = request.POST.getlist('blocks')
        
        checklist = ForumChecklist.objects.create(
            title=title,
            created_by=request.user
        )
        
        # Добавляем участников
        if participant_ids:
            participants = User.objects.filter(id__in=participant_ids)
            checklist.participants.set(participants)
        
        # Создаем блоки в зависимости от выбранного шаблона
        blocks_to_create = []
        
        if template_type == 'custom' and selected_blocks:
            # Кастомный шаблон - создаем только выбранные блоки
            block_mapping = {code: title for title, code in ALL_AVAILABLE_BLOCKS}
            order = 1
            for block_code in selected_blocks:
                if block_code in block_mapping:
                    blocks_to_create.append((block_mapping[block_code], order))
                    order += 1
        elif template_type in CHECKLIST_TEMPLATES:
            # Используем шаблон
            blocks_to_create = CHECKLIST_TEMPLATES[template_type]['blocks']
        else:
            # По умолчанию - полный шаблон
            blocks_to_create = CHECKLIST_TEMPLATES['full']['blocks']
        
        # Создаем блоки
        for block_title, order in blocks_to_create:
            ChecklistBlock.objects.create(
                checklist=checklist,
                title=block_title,
                order=order
            )
        
        messages.success(request, 'Чек-лист создан.')
        return redirect('forum_checklist', checklist_id=checklist.id)
    
    # Получаем список всех активных пользователей
    users = User.objects.filter(is_active=True).order_by('last_name', 'first_name', 'username')
    
    context = {
        'users': users,
        'templates': CHECKLIST_TEMPLATES,
        'available_blocks': ALL_AVAILABLE_BLOCKS,
    }
    return render(request, 'events/forum_checklist_create.html', context)


@login_required
def forum_checklist_ajax(request, checklist_id):
    """
    AJAX endpoints для управления чек-листом.
    Доступ открыт для всех пользователей, но редактирование ограничено.
    """
    try:
        checklist = get_object_or_404(ForumChecklist, id=checklist_id)
        
        # Проверка прав на редактирование (только для создания/удаления задач и изменения статусов блоков)
        # Для обновления своих задач доступ открыт всем
        can_edit = (request.user.is_staff or request.user == checklist.created_by or request.user.is_director())
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'update_task':
                task_id = request.POST.get('task_id')
                task = get_object_or_404(ChecklistTask, id=task_id, block__checklist=checklist)
                
                # Проверка прав: пользователь может обновлять задачу, если он ответственный или имеет права на редактирование
                is_responsible = task.responsible == request.user
                if not (can_edit or is_responsible):
                    return JsonResponse({'success': False, 'error': 'Нет прав на редактирование этой задачи'}, status=403)
                
                # Сохраняем старые значения для проверки изменений
                old_deadline = task.deadline
                old_responsible = task.responsible
                
                # Обновляем поля задачи
                if 'is_completed' in request.POST:
                    task.is_completed = request.POST.get('is_completed') == 'true'
                if 'status' in request.POST:
                    task.status = request.POST.get('status')
                # Изменение ответственного доступно только с правами редактирования
                if 'responsible' in request.POST:
                    if can_edit:
                        responsible_id = request.POST.get('responsible', '')
                        if responsible_id:
                            try:
                                responsible_user = User.objects.get(id=responsible_id)
                                task.responsible = responsible_user
                            except User.DoesNotExist:
                                task.responsible = None
                        else:
                            task.responsible = None
                # Удаляем старую логику сохранения комментария в поле task.comment
                # Теперь комментарии хранятся в отдельной модели ChecklistTaskComment
                if 'deadline' in request.POST:
                    if can_edit:  # Изменение дедлайна доступно только с правами редактирования
                        deadline_str = request.POST.get('deadline', '')
                        if deadline_str:
                            from datetime import datetime
                            try:
                                task.deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
                            except:
                                pass
                        else:
                            task.deadline = None
                
                task.save()
                
                # Синхронизация с расписанием только если изменился дедлайн или ответственный
                deadline_changed = old_deadline != task.deadline
                responsible_changed = old_responsible != task.responsible
                
                if (deadline_changed or responsible_changed) and task.deadline and task.responsible:
                    try:
                        from schedule.models import ScheduleEvent
                        from datetime import datetime, timedelta
                        
                        # Время начала - за час до дедлайна (или текущее время, если дедлайн близко)
                        deadline_datetime = timezone.make_aware(
                            datetime.combine(task.deadline, datetime.min.time())
                        )
                        start_time = deadline_datetime - timedelta(hours=1)
                        if start_time < timezone.now():
                            start_time = timezone.now()
                        
                        end_time = deadline_datetime
                        
                        # Проверяем, есть ли уже связанное событие
                        # Ищем по описанию, которое содержит ID задачи из чек-листа
                        task_identifier = f"Чек-лист: задача #{task.id}"
                        schedule_event = ScheduleEvent.objects.filter(
                            description__icontains=task_identifier,
                            event_type='task'
                        ).first()
                        
                        # Если не нашли по идентификатору, ищем по заголовку и дате (для обратной совместимости)
                        if not schedule_event:
                            schedule_event = ScheduleEvent.objects.filter(
                                title__icontains=task.title[:50],
                                event_type='task',
                                start_time__date=task.deadline
                            ).first()
                        
                        if schedule_event:
                            # Обновляем существующее событие
                            schedule_event.title = f"📋 {task.title}"
                            schedule_event.description = f"{task_identifier}\n{task.comment or f'Задача из чек-листа: {task.title}'}"
                            schedule_event.start_time = start_time
                            schedule_event.end_time = end_time
                            if task.responsible.department:
                                schedule_event.department = task.responsible.department
                            schedule_event.save()
                            schedule_event.participants.clear()
                            if task.responsible:
                                schedule_event.participants.add(task.responsible)
                        else:
                            # Создаем новое событие только если есть дедлайн и ответственный
                            department = task.responsible.department if task.responsible.department else None
                            if department:
                                schedule_event = ScheduleEvent.objects.create(
                                    title=f"📋 {task.title}",
                                    description=f"{task_identifier}\n{task.comment or f'Задача из чек-листа: {task.title}'}",
                                    event_type='task',
                                    department=department,
                                    created_by=task.responsible,
                                    start_time=start_time,
                                    end_time=end_time
                                )
                                if task.responsible:
                                    schedule_event.participants.add(task.responsible)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Ошибка синхронизации задачи из чек-листа с расписанием: {str(e)}")
                elif (deadline_changed and not task.deadline) or (responsible_changed and not task.responsible):
                    # Если дедлайн или ответственный удалены, удаляем событие из расписания
                    try:
                        from schedule.models import ScheduleEvent
                        # Ищем по идентификатору задачи
                        task_identifier = f"Чек-лист: задача #{task.id}"
                        ScheduleEvent.objects.filter(
                            description__icontains=task_identifier,
                            event_type='task'
                        ).delete()
                        # Также удаляем по заголовку и дате (для обратной совместимости)
                        if old_deadline:
                            ScheduleEvent.objects.filter(
                                title__icontains=task.title[:50],
                                event_type='task',
                                start_time__date=old_deadline
                            ).delete()
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Ошибка удаления задачи из расписания: {str(e)}")
                
                # Обновляем статус блока
                task.block.status = task.block.calculate_status()
                task.block.save()
                
                return JsonResponse({'success': True, 'task_id': task.id})
            
            elif action == 'create_task':
                # Создание задач доступно только с правами редактирования
                if not can_edit:
                    return JsonResponse({'success': False, 'error': 'Нет прав на создание задач'}, status=403)
                
                block_id = request.POST.get('block_id')
                block = get_object_or_404(ChecklistBlock, id=block_id, checklist=checklist)
                
                title = request.POST.get('title', 'Новая задача')
                task = ChecklistTask.objects.create(
                    block=block,
                    title=title,
                    order=block.tasks.count()
                )
                
                # Если при создании указаны дедлайн и ответственный, синхронизируем с расписанием
                if 'deadline' in request.POST and 'responsible' in request.POST:
                    deadline_str = request.POST.get('deadline', '')
                    responsible_id = request.POST.get('responsible', '')
                    
                    if deadline_str and responsible_id:
                        try:
                            from datetime import datetime, timedelta
                            task.deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
                            responsible_user = User.objects.get(id=responsible_id)
                            task.responsible = responsible_user
                            task.save()
                            
                            # Синхронизируем с расписанием
                            if task.deadline and task.responsible and task.responsible.department:
                                from schedule.models import ScheduleEvent
                                
                                deadline_datetime = timezone.make_aware(
                                    datetime.combine(task.deadline, datetime.min.time())
                                )
                                start_time = deadline_datetime - timedelta(hours=1)
                                if start_time < timezone.now():
                                    start_time = timezone.now()
                                
                                end_time = deadline_datetime
                                task_identifier = f"Чек-лист: задача #{task.id}"
                                
                                schedule_event = ScheduleEvent.objects.create(
                                    title=f"📋 {task.title}",
                                    description=f"{task_identifier}\nЗадача из чек-листа: {task.title}",
                                    event_type='task',
                                    department=task.responsible.department,
                                    created_by=task.responsible,
                                    start_time=start_time,
                                    end_time=end_time
                                )
                                if task.responsible:
                                    schedule_event.participants.add(task.responsible)
                        except Exception as e:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.error(f"Ошибка синхронизации новой задачи из чек-листа с расписанием: {str(e)}")
                
                return JsonResponse({
                    'success': True,
                    'task': {
                        'id': task.id,
                        'title': task.title,
                        'status': task.status,
                        'is_completed': task.is_completed,
                        'responsible': task.responsible.id if task.responsible else None,
                        'comment': task.comment,
                        'deadline': task.deadline.isoformat() if task.deadline else None,
                    }
                })
            
            elif action == 'delete_task':
                # Удаление задач доступно только с правами редактирования
                if not can_edit:
                    return JsonResponse({'success': False, 'error': 'Нет прав на удаление задач'}, status=403)
                
                task_id = request.POST.get('task_id')
                task = get_object_or_404(ChecklistTask, id=task_id, block__checklist=checklist)
                task.delete()
                return JsonResponse({'success': True})
            
            elif action == 'update_block_status':
                # Изменение статуса блока доступно участникам чек-листа
                is_participant = checklist.participants.filter(id=request.user.id).exists()
                if not (can_edit or is_participant):
                    return JsonResponse({'success': False, 'error': 'Нет прав на изменение статуса блока'}, status=403)
                
                block_id = request.POST.get('block_id')
                status = request.POST.get('status')
                block = get_object_or_404(ChecklistBlock, id=block_id, checklist=checklist)
                block.status = status
                block.save()
                return JsonResponse({'success': True})
            
            elif action == 'update_participants':
                # Изменение участников доступно только с правами редактирования
                if not can_edit:
                    return JsonResponse({'success': False, 'error': 'Нет прав на изменение участников'}, status=403)
                
                participant_ids = request.POST.getlist('participants')
                if participant_ids:
                    participants = User.objects.filter(id__in=participant_ids)
                    checklist.participants.set(participants)
                else:
                    checklist.participants.clear()
                
                # Возвращаем обновленный список участников
                participants_list = [{'id': u.id, 'name': u.get_full_name() or u.username} for u in checklist.participants.all()]
                return JsonResponse({'success': True, 'participants': participants_list})
            
            elif action == 'upload_file':
                task_id = request.POST.get('task_id')
                task = get_object_or_404(ChecklistTask, id=task_id, block__checklist=checklist)
                
                # Проверка прав: пользователь может загружать файлы к задаче, если он ответственный или имеет права на редактирование
                is_responsible = task.responsible == request.user
                if not (can_edit or is_responsible):
                    return JsonResponse({'success': False, 'error': 'Нет прав на загрузку файлов к этой задаче'}, status=403)
                
                if 'file' in request.FILES:
                    uploaded_file = request.FILES['file']
                    # Сохраняем файл в медиа
                    from django.core.files.storage import default_storage
                    import os
                    
                    # Генерируем уникальное имя файла
                    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                    file_name = f'forum_checklist_{checklist.id}/task_{task_id}_{timestamp}_{uploaded_file.name}'
                    
                    # Сохраняем файл
                    saved_path = default_storage.save(file_name, uploaded_file)
                    
                    # Обновляем задачу
                    task.file_name = uploaded_file.name
                    task.file_url = default_storage.url(saved_path)
                    # Безопасно устанавливаем дату отправки файла (если поле существует)
                    if hasattr(task, 'file_sent_at'):
                        task.file_sent_at = timezone.now()
                        file_sent_at_str = task.file_sent_at.strftime('%d.%m.%Y %H:%M')
                    else:
                        file_sent_at_str = None
                    task.save()
                    
                    return JsonResponse({
                        'success': True,
                        'file_name': task.file_name,
                        'file_url': task.file_url,
                        'file_sent_at': file_sent_at_str
                    })
                
                return JsonResponse({'success': False, 'error': 'Файл не загружен'})
            
            elif action == 'add_comment':
                # Добавление комментария доступно участникам чек-листа
                is_participant = checklist.participants.filter(id=request.user.id).exists()
                if not (can_edit or is_participant):
                    return JsonResponse({'success': False, 'error': 'Нет прав на добавление комментариев'}, status=403)
                
                task_id = request.POST.get('task_id')
                comment_text = request.POST.get('comment', '').strip()
                
                if not comment_text:
                    return JsonResponse({'success': False, 'error': 'Комментарий не может быть пустым'}, status=400)
                
                task = get_object_or_404(ChecklistTask, id=task_id, block__checklist=checklist)
                
                comment = ChecklistTaskComment.objects.create(
                    task=task,
                    author=request.user,
                    text=comment_text
                )
                
                return JsonResponse({
                    'success': True,
                    'comment': {
                        'id': comment.id,
                        'text': comment.text,
                        'author': comment.author.get_full_name() or comment.author.username,
                        'author_id': comment.author.id,
                        'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M')
                    }
                })
            
            elif action == 'get_comments':
                # Получение комментариев доступно всем участникам
                task_id = request.POST.get('task_id') or request.GET.get('task_id')
                if not task_id:
                    return JsonResponse({'success': False, 'error': 'Не указан ID задачи'}, status=400)
                
                task = get_object_or_404(ChecklistTask, id=task_id, block__checklist=checklist)
                
                comments = task.comments.select_related('author').order_by('created_at')
                comments_data = [{
                    'id': c.id,
                    'text': c.text,
                    'author': c.author.get_full_name() or c.author.username if c.author else 'Удаленный пользователь',
                    'author_id': c.author.id if c.author else None,
                    'created_at': c.created_at.strftime('%d.%m.%Y %H:%M')
                } for c in comments]
                
                return JsonResponse({
                    'success': True,
                    'comments': comments_data
                })
        
        elif request.method == 'GET':
            # Возвращаем данные чек-листа в JSON
            blocks_data = []
            for block in checklist.blocks.prefetch_related('tasks').order_by('order'):
                tasks_data = []
                for task in block.tasks.order_by('order'):
                    tasks_data.append({
                        'id': task.id,
                        'title': task.title,
                        'status': task.status,
                        'is_completed': task.is_completed,
                        'responsible': task.responsible.id if task.responsible else None,
                        'responsible_name': task.responsible.get_full_name() or task.responsible.username if task.responsible else '',
                        'comment': task.comment,
                        'file_name': task.file_name,
                        'deadline': task.deadline.isoformat() if task.deadline else None,
                        'order': task.order,
                    })
                blocks_data.append({
                    'id': block.id,
                    'title': block.title,
                    'status': block.status,
                    'order': block.order,
                    'tasks': tasks_data,
                })
            
            # Получаем участников
            participants_list = [{'id': u.id, 'name': u.get_full_name() or u.username} for u in checklist.participants.all()]
            
            return JsonResponse({
                'checklist': {
                    'id': checklist.id,
                    'title': checklist.title,
                    'participants': participants_list,
                },
                'blocks': blocks_data,
            })
        
        return JsonResponse({'success': False, 'error': 'Неизвестное действие'})
    
    except Exception as e:
        # Логируем ошибку для отладки
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка в forum_checklist_ajax: {str(e)}\n{traceback.format_exc()}")
        
        # Возвращаем понятное сообщение об ошибке
        return JsonResponse({
            'success': False, 
            'error': f'Произошла ошибка: {str(e)}'
        }, status=500)


# ==================== Мероприятия ====================

def _sync_meropriyatie_to_schedule(meropriyatie):
    """Keep the shared calendar consistent with the event's team and duration."""
    from schedule.models import ScheduleEvent
    from .models import EventWorkspace
    from .collaboration import team
    workspace = EventWorkspace.objects.filter(event=meropriyatie).first()
    if not meropriyatie.event_date or (workspace and workspace.phase == 'cancelled'):
        meropriyatie.schedule_events.all().delete()
        return None
    event = meropriyatie.schedule_events.first()
    if not event: event = ScheduleEvent(related_meropriyatie=meropriyatie, created_by=meropriyatie.created_by)
    event.title = ('🎉 ' + meropriyatie.title)[:200]
    event.description = meropriyatie.description or ''
    event.event_type = 'event'; event.department = meropriyatie.department
    event.start_time = meropriyatie.event_date
    event.end_time = workspace.end_date if workspace and workspace.end_date else meropriyatie.event_date + timedelta(hours=1)
    event.location = workspace.location if workspace else ''
    event.save(); event.participants.set(team(meropriyatie))
    return event


@login_required
def meropriyatie_list_view(request):
    from .work_views import list_view
    return list_view(request)


@login_required
def meropriyatie_create_view(request):
    from .work_views import event_form_view
    return event_form_view(request)


@login_required
def meropriyatie_detail_view(request, pk):
    from .work_views import detail_view
    return detail_view(request,pk)


@login_required
def meropriyatie_update_view(request, pk):
    from .work_views import event_form_view
    return event_form_view(request,pk)


@login_required
def meropriyatie_delete_view(request, pk):
    from .work_views import delete_view
    return delete_view(request,pk)
