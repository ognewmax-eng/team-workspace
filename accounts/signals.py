"""
Сигналы Django для автоматического создания уведомлений.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Notification
from .telegram_bot import send_telegram_notification

User = get_user_model()


def create_notification(user, notification_type, message, related_task=None):
    """
    Вспомогательная функция для создания уведомления.
    
    Args:
        user: Пользователь, которому отправляется уведомление
        notification_type: Тип уведомления
        message: Текст сообщения
        related_task: Связанная задача (опционально)
    """
    if user and user.is_authenticated:
        # Создаем уведомление в базе данных
        Notification.objects.create(
            user=user,
            notification_type=notification_type,
            message=message,
            related_task=related_task
        )
        
        # Отправляем уведомление в Telegram, если у пользователя указан chat_id
        if user.telegram_chat_id:
            try:
                send_telegram_notification(user, message, related_task)
            except Exception as e:
                # Логируем ошибку, но не прерываем создание уведомления
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка отправки Telegram уведомления: {str(e)}")


@receiver(post_save, sender='tasks.Task')
def task_assigned_notification(sender, instance, created, **kwargs):
    """
    Создание уведомления при назначении задачи пользователям.
    """
    # Проверяем, что задача создана с исполнителями
    if created and instance.assigned_to.exists():
        # Отправляем уведомление всем исполнителям
        for assignee in instance.assigned_to.all():
            # Не отправляем уведомление самому создателю, если он назначил задачу себе
            if assignee != instance.created_by:
                message = f'Вам назначена задача "{instance.title}"'
                if instance.created_by:
                    message += f' от {instance.created_by.get_full_name() or instance.created_by.username}'
                create_notification(
                    user=assignee,
                    notification_type='task_assigned',
                    message=message,
                    related_task=instance
                )
    # Для изменения исполнителей лучше обрабатывать в views, где мы знаем, кто изменил


@receiver(post_save, sender='tasks.TaskComment')
def task_comment_notification(sender, instance, created, **kwargs):
    """
    Создание уведомления при добавлении комментария к задаче.
    """
    if created:
        task = instance.task
        # Получаем список пользователей для уведомления
        users_to_notify = set()
        
        # Добавляем создателя задачи
        if task.created_by:
            users_to_notify.add(task.created_by)
        
        # Добавляем всех исполнителей задачи
        users_to_notify.update(task.assigned_to.all())
        
        # Убираем автора комментария из списка
        users_to_notify.discard(instance.author)
        
        # Создаем уведомления для всех, кроме автора комментария
        for user in users_to_notify:
            author_name = instance.author.get_full_name() or instance.author.username
            message = f'{author_name} оставил комментарий к задаче "{task.title}"'
            create_notification(
                user=user,
                notification_type='task_comment',
                message=message,
                related_task=task
            )


# Уведомления об изменении статуса обрабатываются в views/tasks/views.py
# так как там мы знаем, кто изменил статус (request.user)

