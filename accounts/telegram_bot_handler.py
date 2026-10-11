"""
Обработчик команд для Telegram бота.
"""
import logging
from typing import Optional

# Безопасный импорт telegram библиотеки
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
    from telegram.ext import (
        Application,
        CommandHandler,
        CallbackQueryHandler,
        MessageHandler,
        ConversationHandler,
        filters
    )
    from asgiref.sync import sync_to_async
    TELEGRAM_BOT_AVAILABLE = True
except ImportError:
    TELEGRAM_BOT_AVAILABLE = False
    logging.warning("Модуль 'python-telegram-bot' не установлен. Интерактивный Telegram бот будет недоступен. Установите: pip install python-telegram-bot")

from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Department
from tasks.models import Task, TaskComment, TaskAssignee
from schedule.models import ScheduleEvent

User = get_user_model()
logger = logging.getLogger(__name__)

# Состояния для FSM (создание задачи)
TASK_TITLE, TASK_DESCRIPTION, TASK_DEPARTMENT, TASK_ASSIGNEE, TASK_PRIORITY, TASK_DEADLINE = range(6)

# Состояния для комментария
COMMENT_TEXT = 1

# Вспомогательные функции для async работы с Django ORM
if TELEGRAM_BOT_AVAILABLE:
    from asgiref.sync import sync_to_async
    
    # Обертки для часто используемых операций
    def _get_user_sync(chat_id):
        return User.objects.get(telegram_chat_id=chat_id)
    
    def _save_user_sync(user):
        user.save()
    
    def _get_departments_sync():
        return list(Department.objects.all())
    
    def _get_department_sync(dept_id):
        return Department.objects.get(id=dept_id)
    
    def _get_users_sync(dept):
        return list(User.objects.filter(department=dept, is_active=True))
    
    def _get_user_by_id_sync(user_id):
        return User.objects.get(id=user_id)
    
    def _create_task_sync(**kwargs):
        """Создание задачи с назначениями через TaskAssignee (through-модель)."""
        assigned_to = kwargs.pop('assigned_to', None)
        task = Task.objects.create(**kwargs)
        if assigned_to:
            users = assigned_to if isinstance(assigned_to, list) else [assigned_to]
            for user in users:
                TaskAssignee.objects.get_or_create(
                    task=task,
                    user=user,
                    defaults={'status': 'assigned'},
                )
        task = Task.objects.select_related('created_by', 'department').prefetch_related('assigned_to').get(id=task.id)
        return task
    
    def _get_task_sync(task_id):
        return Task.objects.select_related('created_by', 'department').prefetch_related('assigned_to').get(id=task_id)
    
    def _get_my_tasks_sync(user):
        """Получение задач пользователя с предзагрузкой связанных объектов (исключая завершенные)."""
        tasks = Task.objects.filter(assigned_to=user).exclude(status='completed').select_related('created_by', 'department').prefetch_related('assigned_to').order_by('-created_at')[:10]
        return list(tasks)
    
    def _get_department_tasks_sync(department):
        """Получение задач отдела с предзагрузкой связанных объектов (исключая завершенные)."""
        tasks = Task.objects.filter(department=department).exclude(status='completed').select_related('created_by', 'department').prefetch_related('assigned_to').order_by('-created_at')[:10]
        return list(tasks)
    
    def _get_task_assignees_sync(task):
        """Получение списка исполнителей задачи (синхронная обертка)."""
        return list(task.assigned_to.all())
    
    def _get_task_assignees_str_sync(task):
        """Получение строки с именами исполнителей (синхронная обертка)."""
        assignees = list(task.assigned_to.all())
        if assignees:
            return ', '.join([a.get_full_name() or a.username for a in assignees])
        return 'Не назначен'
    
    def _save_task_sync(task):
        task.save()

    def _get_task_with_assignments_sync(task_id):
        """Задача с предзагрузкой назначений (для отображения персонального статуса)."""
        return Task.objects.select_related('created_by', 'department').prefetch_related(
            'assigned_to', 'assignments__user'
        ).get(id=task_id)

    def _get_my_assignment_sync(task, user):
        """Назначение текущего пользователя на задачу (TaskAssignee) или None."""
        return TaskAssignee.objects.filter(task=task, user=user).first()

    def _update_task_status_via_bot_sync(task_id, user_id, new_status):
        """
        Обновить статус по задаче для пользователя бота.
        Если пользователь — исполнитель: обновляется его TaskAssignee.status и пересчитывается
        общий статус задачи. Если пользователь — директор (и не исполнитель): обновляется
        task.status и включается фиксация.
        Возвращает (success, task, kind) где kind in ('assignee', 'director') или (False, None, None).
        """
        if new_status not in dict(TaskAssignee.ASSIGNEE_STATUS_CHOICES):
            return (False, None, None)
        try:
            task = Task.objects.prefetch_related('assignments__user').get(id=task_id)
            user = User.objects.get(id=user_id)
        except (Task.DoesNotExist, User.DoesNotExist):
            return (False, None, None)
        assignment = TaskAssignee.objects.filter(task=task, user=user).first()
        if assignment is not None:
            assignment.status = new_status
            assignment.save()
            task.update_aggregate_status()
            task.refresh_from_db()
            return (True, task, 'assignee')
        if getattr(user, 'is_director', lambda: False)():
            task.status = new_status
            task.status_locked_by_director = True
            task.save()
            return (True, task, 'director')
        return (False, None, None)

    def _create_comment_sync(**kwargs):
        return TaskComment.objects.create(**kwargs)
    
    def _create_schedule_event_sync(task):
        """Создание события в расписании для задачи (синхронная обертка)."""
        try:
            # Если нет дедлайна или отдела, не создаем событие
            if not task.deadline or not task.department:
                return None
            
            # Время начала - за час до дедлайна (или текущее время, если дедлайн близко)
            from datetime import timedelta
            start_time = task.deadline - timedelta(hours=1)
            if start_time < timezone.now():
                start_time = timezone.now()
            
            end_time = task.deadline
            
            # Создаем событие в расписании
            event = ScheduleEvent.objects.create(
                title=f"📋 {task.title}",
                description=task.description or f"Задача: {task.title}",
                event_type='task',
                department=task.department,
                created_by=task.created_by,
                start_time=start_time,
                end_time=end_time
            )
            
            # Добавляем всех исполнителей как участников
            for assignee in task.assigned_to.all():
                event.participants.add(assignee)
            
            return event
        except Exception as e:
            logger.error(f"Ошибка создания события в расписании для задачи {task.id}: {str(e)}", exc_info=True)
            return None
    
    # Асинхронные обертки
    async_get_user = sync_to_async(_get_user_sync, thread_sensitive=True)
    async_save_user = sync_to_async(_save_user_sync, thread_sensitive=True)
    async_get_departments = sync_to_async(_get_departments_sync, thread_sensitive=True)
    async_get_department = sync_to_async(_get_department_sync, thread_sensitive=True)
    async_get_users = sync_to_async(_get_users_sync, thread_sensitive=True)
    async_get_user_by_id = sync_to_async(_get_user_by_id_sync, thread_sensitive=True)
    async_create_task = sync_to_async(_create_task_sync, thread_sensitive=True)
    async_get_task = sync_to_async(_get_task_sync, thread_sensitive=True)
    async_get_my_tasks = sync_to_async(_get_my_tasks_sync, thread_sensitive=True)
    async_get_department_tasks = sync_to_async(_get_department_tasks_sync, thread_sensitive=True)
    async_get_task_assignees = sync_to_async(_get_task_assignees_sync, thread_sensitive=True)
    async_get_task_assignees_str = sync_to_async(_get_task_assignees_str_sync, thread_sensitive=True)
    async_save_task = sync_to_async(_save_task_sync, thread_sensitive=True)
    async_get_task_with_assignments = sync_to_async(_get_task_with_assignments_sync, thread_sensitive=True)
    async_get_my_assignment = sync_to_async(_get_my_assignment_sync, thread_sensitive=True)
    async_update_task_status_via_bot = sync_to_async(_update_task_status_via_bot_sync, thread_sensitive=True)
    async_create_comment = sync_to_async(_create_comment_sync, thread_sensitive=True)
    async_create_schedule_event = sync_to_async(_create_schedule_event_sync, thread_sensitive=True)


class TelegramBotHandler:
    """Обработчик команд Telegram бота."""
    
    def __init__(self, bot_token: str):
        if not TELEGRAM_BOT_AVAILABLE:
            raise ImportError("python-telegram-bot не установлен. Установите: pip install python-telegram-bot")
        
        self.bot_token = bot_token
        self.application = Application.builder().token(bot_token).build()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Настройка обработчиков команд."""
        # Обработчик ошибок
        async def error_handler(update: object, context):
            """Обработка ошибок."""
            logger.error(f"Ошибка при обработке обновления: {context.error}", exc_info=context.error)
            if update and hasattr(update, 'effective_chat'):
                try:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="❌ Произошла ошибка при обработке вашего запроса. Попробуйте позже."
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение об ошибке: {str(e)}")
        
        self.application.add_error_handler(error_handler)
        
        # Базовые команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("tasks", self.list_tasks))
        self.application.add_handler(CommandHandler("my_tasks", self.my_tasks))
        
        # Обработчик неизвестных команд (добавляется после всех известных команд)
        # Используем MessageHandler с фильтром COMMAND для перехвата всех команд
        # ВАЖНО: Этот обработчик должен быть добавлен ПОСЛЕ всех CommandHandler'ов,
        # но ПЕРЕД общим MessageHandler, чтобы перехватывать неизвестные команды
        self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown_command))
        
        # ВАЖНО: ConversationHandler должен быть добавлен ПЕРЕД общим MessageHandler
        # чтобы иметь приоритет при обработке сообщений
        
        # Создание задачи (только для директора/начальника)
        # ВАЖНО: Добавляем MessageHandler для кнопки "➕ Создать задачу" как entry_point
        # чтобы ConversationHandler правильно активировался при нажатии кнопки
        
        # Создаем обертку для логирования entry_point
        async def create_task_start_wrapper(update: Update, context):
            """Обертка для логирования входа в create_task_start."""
            text = update.message.text if update.message else 'N/A'
            logger.info(f"🔵 Entry point 'create_task' активирован для сообщения: '{text}'")
            return await self.create_task_start(update, context)
        
        # Обработчик для кнопок клавиатуры, который прерывает FSM
        async def keyboard_button_fallback(update: Update, context):
            """Обработчик кнопок клавиатуры, который прерывает FSM и выполняет действие."""
            if not update.message:
                return ConversationHandler.END
            
            text = update.message.text
            known_buttons = ["📋 Мои задачи", "📊 Задачи отдела", "ℹ️ Справка"]
            
            if text in known_buttons:
                logger.info(f"Кнопка клавиатуры '{text}' прерывает FSM")
                context.user_data.clear()
                
                user = await self._get_user(update.effective_user.id)
                if not user:
                    return ConversationHandler.END
                
                # Выполняем соответствующее действие
                if text == "📋 Мои задачи":
                    await self.my_tasks(update, context)
                elif text == "📊 Задачи отдела":
                    await self.list_tasks(update, context)
                elif text == "ℹ️ Справка":
                    await self.help_command(update, context)
                
                return ConversationHandler.END
            
            return ConversationHandler.END
        
        create_task_handler = ConversationHandler(
            entry_points=[
                CommandHandler("create_task", create_task_start_wrapper),
                # Используем filters.Regex для проверки точного совпадения текста кнопки
                MessageHandler(filters.TEXT & filters.Regex("^➕ Создать задачу$"), create_task_start_wrapper)
            ],
            states={
                # Используем filters.TEXT без ~filters.COMMAND, так как в состояниях ConversationHandler команды обычно не обрабатываются
                TASK_TITLE: [MessageHandler(filters.TEXT, self.task_title)],
                TASK_DESCRIPTION: [MessageHandler(filters.TEXT, self.task_description)],
                TASK_DEPARTMENT: [CallbackQueryHandler(self.task_department)],
                TASK_ASSIGNEE: [CallbackQueryHandler(self.task_assignee)],
                TASK_PRIORITY: [CallbackQueryHandler(self.task_priority)],
                TASK_DEADLINE: [MessageHandler(filters.TEXT, self.task_deadline)],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                # Обработка кнопок клавиатуры для прерывания FSM
                MessageHandler(
                    filters.TEXT & filters.Regex("^(📋 Мои задачи|📊 Задачи отдела|ℹ️ Справка)$"),
                    keyboard_button_fallback
                )
            ],
            per_message=False,  # per_message=False для более предсказуемого поведения
        )
        self.application.add_handler(create_task_handler)
        
        # Комментарии (для всех)
        # Обработчик для кнопок клавиатуры, который прерывает FSM комментариев
        async def comment_keyboard_button_fallback(update: Update, context):
            """Обработчик кнопок клавиатуры, который прерывает FSM комментариев и выполняет действие."""
            if not update.message:
                return ConversationHandler.END
            
            text = update.message.text
            known_buttons = ["📋 Мои задачи", "📊 Задачи отдела", "ℹ️ Справка", "➕ Создать задачу"]
            
            if text in known_buttons:
                logger.info(f"Кнопка клавиатуры '{text}' прерывает FSM комментариев")
                context.user_data.clear()
                
                user = await self._get_user(update.effective_user.id)
                if not user:
                    return ConversationHandler.END
                
                # Выполняем соответствующее действие
                if text == "📋 Мои задачи":
                    await self.my_tasks(update, context)
                elif text == "📊 Задачи отдела":
                    await self.list_tasks(update, context)
                elif text == "ℹ️ Справка":
                    await self.help_command(update, context)
                elif text == "➕ Создать задачу":
                    await self.create_task_start(update, context)
                
                return ConversationHandler.END
            
            return ConversationHandler.END
        
        comment_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.comment_start, pattern="^comment_")],
            states={
                COMMENT_TEXT: [MessageHandler(filters.TEXT, self.comment_text)],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                # Обработка кнопок клавиатуры для прерывания FSM комментариев
                MessageHandler(
                    filters.TEXT & filters.Regex("^(📋 Мои задачи|📊 Задачи отдела|ℹ️ Справка|➕ Создать задачу)$"),
                    comment_keyboard_button_fallback
                )
            ],
            per_message=False,  # per_message=False для более предсказуемого поведения, как у create_task_handler
        )
        self.application.add_handler(comment_handler)
        
        # Обработка callback кнопок
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Обработка текстовых сообщений (кнопки клавиатуры)
        # ВАЖНО: ConversationHandler должен обработать сообщения первым через entry_points
        # Этот обработчик обрабатывает только сообщения, которые не обработаны ConversationHandler
        # Обработка текстовых сообщений (кнопки клавиатуры)
        # ConversationHandler должен обработать сообщения первым через entry_points
        # Этот обработчик обрабатывает только сообщения, которые не обработаны ConversationHandler
        # Используем простой filters.TEXT - проверку кнопки "➕ Создать задачу" делаем внутри handle_text_message
        self.application.add_handler(MessageHandler(filters.TEXT, self.handle_text_message))
    
    def _get_reply_keyboard(self, user):
        """Получение клавиатуры с кнопками команд в зависимости от роли пользователя."""
        keyboard = [
            [KeyboardButton("📋 Мои задачи"), KeyboardButton("📊 Задачи отдела")],
        ]
        
        # Для директора и начальника добавляем кнопку создания задачи
        if user and (user.is_director() or user.is_head()):
            keyboard.append([KeyboardButton("➕ Создать задачу")])
        
        keyboard.append([KeyboardButton("ℹ️ Справка")])
        
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    async def start_command(self, update: Update, context):
        """Обработка команды /start."""
        user_id = update.effective_user.id
        logger.info(f"🔵 Команда /start от пользователя {user_id}")
        
        user = await self._get_user(user_id)
        
        if not user:
            logger.warning(f"❌ Пользователь {user_id} не найден в системе")
            chat_id = update.effective_chat.id
            await update.message.reply_text(
                "❌ Вы не зарегистрированы в системе.\n\n"
                f"🆔 ID чата: {chat_id}\n\n"
                "Обратитесь к администратору для регистрации.\n"
                "Сообщите администратору ваш ID чата для добавления в систему."
            )
            return
        
        # Сохраняем chat_id если его еще нет
        if not user.telegram_chat_id:
            user.telegram_chat_id = update.effective_user.id
            await async_save_user(user)
        
        # Получаем department синхронно через обертку
        department = await sync_to_async(lambda: user.department)()
        department_name = department.name if department else 'Не назначен'
        
        # Получаем ID чата
        chat_id = update.effective_chat.id
        
        welcome_text = (
            f"👋 Добро пожаловать, {user.get_full_name() or user.username}!\n\n"
            f"Ваша роль: {user.get_role_display()}\n"
            f"Отдел: {department_name}\n"
            f"🆔 ID чата: {chat_id}\n\n"
            "Используйте кнопки ниже или команды для работы с ботом."
        )
        
        # Отправляем приветствие с клавиатурой
        reply_markup = self._get_reply_keyboard(user)
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        logger.info(f"✅ Приветствие отправлено пользователю {user_id} ({user.username})")
    
    async def unknown_command(self, update: Update, context):
        """Обработка неизвестных команд."""
        # Проверяем, что это действительно команда (начинается с "/")
        if not update.message or not update.message.text or not update.message.text.startswith('/'):
            return
        
        # Извлекаем имя команды
        command = update.message.text.split()[0] if update.message.text else ''
        
        # Список известных команд
        known_commands = ['/start', '/help', '/tasks', '/my_tasks', '/create_task', '/cancel']
        
        # Если команда не в списке известных, отправляем сообщение об ошибке
        if command not in known_commands:
            user = await self._get_user(update.effective_user.id)
            if user:
                reply_markup = self._get_reply_keyboard(user)
                await update.message.reply_text(
                    "❌ Извините, такой команды нет в списке.\n\n"
                    "Используйте кнопки клавиатуры или команды для работы с ботом.\n"
                    "Нажмите /help для справки.",
                    reply_markup=reply_markup
                )
            else:
                chat_id = update.effective_chat.id
                await update.message.reply_text(
                    "❌ Вы не зарегистрированы в системе.\n\n"
                    f"🆔 ID чата: {chat_id}\n\n"
                    "Обратитесь к администратору для регистрации.\n"
                    "Сообщите администратору ваш ID чата для добавления в систему."
                )
    
    async def help_command(self, update: Update, context):
        """Обработка команды /help."""
        user_id = update.effective_user.id
        logger.info(f"🔵 Команда /help от пользователя {user_id}")
        
        user = await self._get_user(user_id)
        
        if not user:
            logger.warning(f"❌ Пользователь {user_id} не найден в системе")
            return
        
        help_text = "📋 <b>Доступные команды:</b>\n\n"
        help_text += "/start - Начать работу с ботом\n"
        help_text += "/help - Показать эту справку\n"
        help_text += "/my_tasks - Мои задачи\n"
        help_text += "/tasks - Все задачи моего отдела\n"
        
        if user.is_director() or user.is_head():
            help_text += "/create_task - Создать новую задачу\n"
        
        help_text += "\n💡 <b>Быстрые действия:</b>\n"
        help_text += "Используйте кнопки клавиатуры или кнопки под сообщениями для быстрых действий."
        
        reply_markup = self._get_reply_keyboard(user)
        await update.message.reply_text(help_text, parse_mode='HTML', reply_markup=reply_markup)
    
    async def my_tasks(self, update: Update, context):
        """Список задач пользователя."""
        user_id = update.effective_user.id
        logger.info(f"🔵 Команда /my_tasks от пользователя {user_id}")
        
        user = await self._get_user(user_id)
        
        if not user:
            logger.warning(f"❌ Пользователь {user_id} не найден в системе")
            return
        
        tasks = await async_get_my_tasks(user)
        reply_markup = self._get_reply_keyboard(user)
        
        if not tasks:
            await update.message.reply_text("📭 У вас нет назначенных задач.", reply_markup=reply_markup)
            return
        
        for task in tasks:
            status_emoji = {
                'pending': '⏳',
                'assigned': '👤',
                'in_progress': '🔄',
                'completed': '✅'
            }
            emoji = status_emoji.get(task.status, '📌')
            
            text = f"{emoji} <b>{task.title}</b>\n"
            text += f"📊 Статус: {task.get_status_display()}\n"
            if task.deadline:
                text += f"📅 Дедлайн: {task.deadline.strftime('%d.%m.%Y %H:%M')}\n"
            if task.description:
                text += f"📄 {task.description[:100]}{'...' if len(task.description) > 100 else ''}\n"
            
            # Кнопки для быстрых действий
            keyboard = [
                [
                    InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_{task.id}"),
                    InlineKeyboardButton("📊 Статус", callback_data=f"status_{task.id}")
                ],
                [InlineKeyboardButton("📄 Подробнее", callback_data=f"task_{task.id}")]
            ]
            inline_markup = InlineKeyboardMarkup(keyboard)
            reply_markup = self._get_reply_keyboard(user)
            
            # Используем комбинацию inline кнопок и reply клавиатуры
            await update.message.reply_text(text, parse_mode='HTML', reply_markup=inline_markup)
            # Отправляем отдельное сообщение с reply клавиатурой
            await update.message.reply_text("Используйте кнопки выше для действий с задачей.", reply_markup=reply_markup)
    
    async def list_tasks(self, update: Update, context):
        """Список задач отдела."""
        user_id = update.effective_user.id
        logger.info(f"🔵 Команда /tasks от пользователя {user_id}")
        
        user = await self._get_user(user_id)
        
        if not user:
            return
        
        reply_markup = self._get_reply_keyboard(user)
        
        # Получаем department асинхронно
        department = await sync_to_async(lambda: user.department)()
        if not department:
            await update.message.reply_text("❌ Вы не привязаны к отделу.", reply_markup=reply_markup)
            return
        
        tasks = await async_get_department_tasks(department)
        
        if not tasks:
            await update.message.reply_text("📭 В вашем отделе нет задач.", reply_markup=reply_markup)
            return
        
        text = f"📋 <b>Задачи отдела {department.name}:</b>\n\n"
        for task in tasks:
            status_emoji = {
                'pending': '⏳',
                'assigned': '👤',
                'in_progress': '🔄',
                'completed': '✅'
            }
            emoji = status_emoji.get(task.status, '📌')
            
            # Получаем список исполнителей
            assigned_to_name = await async_get_task_assignees_str(task)
            
            text += f"{emoji} <b>{task.title}</b>\n"
            text += f"   Исполнители: {assigned_to_name}\n"
            text += f"   Статус: {task.get_status_display()}\n\n"
        
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)
    
    # ========== Создание задачи (FSM) ==========
    
    async def create_task_start(self, update: Update, context):
        """Начало создания задачи."""
        user_id = update.effective_user.id
        logger.info(f"🔵 Начало создания задачи от пользователя {user_id}")
        
        user = await self._get_user(user_id)
        
        if not user:
            logger.warning(f"❌ Пользователь {user_id} не найден в системе")
            return ConversationHandler.END
        
        if not (user.is_director() or user.is_head()):
            logger.warning(f"❌ Пользователь {user_id} не имеет прав для создания задач")
            await update.message.reply_text(
                "❌ У вас нет прав для создания задач.\n"
                "Только директор и начальник отдела могут создавать задачи."
            )
            return ConversationHandler.END
        
        logger.info(f"✅ Начинаем создание задачи для пользователя {user_id} ({user.username})")
        await update.message.reply_text(
            "📝 <b>Создание новой задачи</b>\n\n"
            "Введите название задачи:\n"
            "(Используйте /cancel для отмены)",
            parse_mode='HTML'
        )
        
        logger.info(f"✅ Сообщение с запросом названия задачи отправлено пользователю {user_id}")
        return TASK_TITLE
    
    async def task_title(self, update: Update, context):
        """Получение названия задачи."""
        context.user_data['task_title'] = update.message.text
        
        await update.message.reply_text(
            "📄 Введите описание задачи:\n"
            "(Используйте /cancel для отмены)"
        )
        
        return TASK_DESCRIPTION
    
    async def task_description(self, update: Update, context):
        """Получение описания задачи."""
        context.user_data['task_description'] = update.message.text
        
        # Выбор отдела
        departments = await async_get_departments()
        if not departments:
            await update.message.reply_text("❌ В системе нет отделов. Обратитесь к администратору.")
            return ConversationHandler.END
        
        keyboard = []
        for dept in departments:
            keyboard.append([InlineKeyboardButton(
                dept.name,
                callback_data=f"dept_{dept.id}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🏢 Выберите отдел:",
            reply_markup=reply_markup
        )
        
        return TASK_DEPARTMENT
    
    async def task_department(self, update: Update, context):
        """Выбор отдела."""
        query = update.callback_query
        await query.answer()
        
        dept_id = int(query.data.split('_')[1])
        try:
            department = await async_get_department(dept_id)
        except Department.DoesNotExist:
            await query.edit_message_text("❌ Отдел не найден.")
            return ConversationHandler.END
        
        context.user_data['task_department'] = dept_id
        
        # Выбор исполнителя
        users = await async_get_users(department)
        keyboard = []
        for user_obj in users:
            keyboard.append([InlineKeyboardButton(
                user_obj.get_full_name() or user_obj.username,
                callback_data=f"user_{user_obj.id}"
            )])
        keyboard.append([InlineKeyboardButton("Пропустить", callback_data="user_skip")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "👤 Выберите исполнителя:",
            reply_markup=reply_markup
        )
        
        return TASK_ASSIGNEE
    
    async def task_assignee(self, update: Update, context):
        """Выбор исполнителя."""
        query = update.callback_query
        await query.answer()
        
        if query.data == "user_skip":
            context.user_data['task_assignee'] = None
        else:
            user_id = int(query.data.split('_')[1])
            context.user_data['task_assignee'] = user_id
        
        # Выбор приоритета
        priorities = [
            ('low', '🟢 Низкий'),
            ('medium', '🟡 Средний'),
            ('high', '🟠 Высокий'),
            ('urgent', '🔴 Срочный')
        ]
        
        keyboard = []
        for priority, label in priorities:
            keyboard.append([InlineKeyboardButton(
                label,
                callback_data=f"priority_{priority}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚡ Выберите приоритет:",
            reply_markup=reply_markup
        )
        
        return TASK_PRIORITY
    
    async def task_priority(self, update: Update, context):
        """Выбор приоритета."""
        query = update.callback_query
        await query.answer()
        
        priority = query.data.split('_')[1]
        context.user_data['task_priority'] = priority
        
        await query.edit_message_text(
            "📅 Введите дедлайн в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 25.12.2024 18:00\n"
            "Или отправьте 'пропустить' для создания без дедлайна:\n"
            "(Используйте /cancel для отмены)"
        )
        
        return TASK_DEADLINE
    
    async def task_deadline(self, update: Update, context):
        """Получение дедлайна и создание задачи."""
        user = await self._get_user(update.effective_user.id)
        
        deadline_text = update.message.text.lower().strip()
        
        if deadline_text in ['пропустить', 'skip', 'нет', 'no']:
            deadline = None
        else:
            try:
                from datetime import datetime
                deadline = datetime.strptime(deadline_text, '%d.%m.%Y %H:%M')
                deadline = timezone.make_aware(deadline)
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат даты. Попробуйте снова:\n"
                    "Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
                    "Или отправьте 'пропустить'"
                )
                return TASK_DEADLINE
        
        # Создание задачи
        try:
            department = await async_get_department(context.user_data['task_department'])
            assignees = []
            if context.user_data.get('task_assignee'):
                assignee = await async_get_user_by_id(context.user_data['task_assignee'])
                assignees = [assignee]
            
            task = await async_create_task(
                title=context.user_data['task_title'],
                description=context.user_data['task_description'],
                department=department,
                assigned_to=assignees,
                created_by=user,
                priority=context.user_data['task_priority'],
                deadline=deadline
            )
            
            # Создание события в расписании (если есть дедлайн)
            if deadline:
                try:
                    schedule_event = await async_create_schedule_event(task)
                    if schedule_event:
                        logger.info(f"✅ Событие в расписании создано для задачи {task.id}")
                    else:
                        logger.warning(f"⚠️ Не удалось создать событие в расписании для задачи {task.id}")
                except Exception as e:
                    # Логируем ошибку, но не прерываем создание задачи
                    logger.error(f"Ошибка создания события в расписании для задачи {task.id}: {str(e)}", exc_info=True)
            
            deadline_str = deadline.strftime('%d.%m.%Y %H:%M') if deadline else 'Не установлен'
            assignee_str = await async_get_task_assignees_str(task)
            
            await update.message.reply_text(
                f"✅ <b>Задача создана!</b>\n\n"
                f"📋 {task.title}\n"
                f"🏢 Отдел: {department.name}\n"
                f"👤 Исполнители: {assignee_str}\n"
                f"⚡ Приоритет: {task.get_priority_display()}\n"
                f"📅 Дедлайн: {deadline_str}",
                parse_mode='HTML'
            )
            
            # Очистка данных
            context.user_data.clear()
            
        except Exception as e:
            logger.error(f"Ошибка создания задачи: {str(e)}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка при создании задачи: {str(e)}"
            )
        
        return ConversationHandler.END
    
    # ========== Комментарии ==========
    
    async def comment_start(self, update: Update, context):
        """Начало добавления комментария."""
        query = update.callback_query
        await query.answer()
        
        task_id = int(query.data.split('_')[1])
        try:
            task = await async_get_task(task_id)
        except Task.DoesNotExist:
            await query.edit_message_text("❌ Задача не найдена.")
            return ConversationHandler.END
        
        context.user_data['comment_task_id'] = task_id
        
        await query.edit_message_text(
            f"💬 <b>Добавление комментария к задаче:</b>\n"
            f"📋 {task.title}\n\n"
            f"Введите текст комментария:\n"
            f"(Используйте /cancel для отмены)",
            parse_mode='HTML'
        )
        
        return COMMENT_TEXT
    
    async def comment_text(self, update: Update, context):
        """Получение текста комментария и сохранение."""
        user = await self._get_user(update.effective_user.id)
        if not user:
            await update.message.reply_text("❌ Пользователь не найден.")
            return ConversationHandler.END
        
        task_id = context.user_data.get('comment_task_id')
        if not task_id:
            await update.message.reply_text("❌ Ошибка: задача не найдена.")
            return ConversationHandler.END
        
        try:
            task = await async_get_task(task_id)
        except Task.DoesNotExist:
            await update.message.reply_text("❌ Задача не найдена.")
            return ConversationHandler.END
        
        comment = await async_create_comment(
            task=task,
            author=user,
            text=update.message.text
        )
        
        await update.message.reply_text(
            f"✅ <b>Комментарий добавлен!</b>\n\n"
            f"📋 Задача: {task.title}\n"
            f"💬 Комментарий: {comment.text}",
            parse_mode='HTML'
        )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    # ========== Изменение статуса ==========
    
    async def button_callback(self, update: Update, context):
        """Обработка callback кнопок."""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("status_"):
            task_id = int(query.data.split('_')[1])
            user = await self._get_user(update.effective_user.id)
            try:
                task = await async_get_task_with_assignments(task_id)
            except Task.DoesNotExist:
                await query.edit_message_text("❌ Задача не найдена.")
                return
            my_assignment = await async_get_my_assignment(task, user) if user else None
            status_line = (
                f"Ваш статус: {my_assignment.get_status_display()}\n"
                f"Общий статус задачи: {task.get_status_display()}\n\n"
                if my_assignment
                else f"Текущий статус задачи: {task.get_status_display()}\n\n"
            )
            keyboard = [
                [
                    InlineKeyboardButton("👤 Назначено", callback_data=f"set_status_{task_id}_assigned"),
                    InlineKeyboardButton("🔄 В работе", callback_data=f"set_status_{task_id}_in_progress")
                ],
                [
                    InlineKeyboardButton("⏳ На проверке", callback_data=f"set_status_{task_id}_pending"),
                    InlineKeyboardButton("✅ Завершено", callback_data=f"set_status_{task_id}_completed")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"📊 <b>Изменение статуса</b>\n"
                f"📋 {task.title}\n\n"
                f"{status_line}"
                f"Выберите новый статус:",
                parse_mode='HTML',
                reply_markup=reply_markup
            )

        elif query.data.startswith("set_status_"):
            parts = query.data.split('_')
            task_id = int(parts[2])
            new_status = '_'.join(parts[3:])
            user = await self._get_user(update.effective_user.id)
            if not user:
                await query.edit_message_text("❌ Вы не зарегистрированы в системе.")
                return
            success, task, kind = await async_update_task_status_via_bot(task_id, user.id, new_status)
            if not success:
                await query.edit_message_text(
                    "❌ Вы не назначены на эту задачу. Изменить общий статус может только директор.",
                    parse_mode='HTML'
                )
                return
            if kind == 'assignee':
                msg = (
                    f"✅ <b>Ваш статус обновлён!</b>\n\n"
                    f"📋 Задача: {task.title}\n"
                    f"📊 Стало: {dict(TaskAssignee.ASSIGNEE_STATUS_CHOICES).get(new_status, new_status)}\n"
                    f"📊 Общий статус задачи: {task.get_status_display()}"
                )
            else:
                msg = (
                    f"✅ <b>Статус задачи изменён (зафиксирован)</b>\n\n"
                    f"📋 Задача: {task.title}\n"
                    f"📊 Статус: {task.get_status_display()}"
                )
            await query.edit_message_text(msg, parse_mode='HTML')
        
        elif query.data.startswith("task_"):
            task_id = int(query.data.split('_')[1])
            try:
                task = await async_get_task(task_id)
            except Task.DoesNotExist:
                await query.edit_message_text("❌ Задача не найдена.")
                return
            
            # Получаем список исполнителей
            assigned_to_name = await async_get_task_assignees_str(task)
            created_by_name = task.created_by.get_full_name() if task.created_by else 'Неизвестно'
            
            text = (
                f"📋 <b>{task.title}</b>\n\n"
                f"📄 Описание: {task.description or 'Нет описания'}\n"
                f"📊 Статус: {task.get_status_display()}\n"
                f"⚡ Приоритет: {task.get_priority_display()}\n"
                f"🏢 Отдел: {task.department.name}\n"
                f"👤 Исполнитель: {assigned_to_name}\n"
            )
            
            if task.deadline:
                text += f"📅 Дедлайн: {task.deadline.strftime('%d.%m.%Y %H:%M')}\n"
            
            if task.created_by:
                text += f"👨‍💼 Создал: {created_by_name}\n"
            
            keyboard = [
                [
                    InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_{task.id}"),
                    InlineKeyboardButton("📊 Статус", callback_data=f"status_{task.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
    
    async def cancel(self, update: Update, context):
        """Отмена операции."""
        context.user_data.clear()
        user = await self._get_user(update.effective_user.id)
        reply_markup = self._get_reply_keyboard(user) if user else None
        await update.message.reply_text("❌ Операция отменена.", reply_markup=reply_markup)
        return ConversationHandler.END
    
    async def handle_text_message(self, update: Update, context):
        """Обработка текстовых сообщений (кнопки клавиатуры)."""
        # Логируем все входящие текстовые сообщения для отладки
        logger.debug(f"handle_text_message вызван для сообщения: '{update.message.text}' от пользователя {update.effective_user.id}")
        
        user = await self._get_user(update.effective_user.id)
        
        if not user:
            chat_id = update.effective_chat.id
            await update.message.reply_text(
                "❌ Вы не зарегистрированы в системе.\n\n"
                f"🆔 ID чата: {chat_id}\n\n"
                "Обратитесь к администратору для регистрации.\n"
                "Сообщите администратору ваш ID чата для добавления в систему."
            )
            return
        
        text = update.message.text
        
        # Проверяем, является ли это известной кнопкой клавиатуры
        known_buttons = ["📋 Мои задачи", "📊 Задачи отдела", "ℹ️ Справка", "➕ Создать задачу"]
        
        # Если это известная кнопка, обрабатываем её даже если FSM активен
        # (это позволяет прервать процесс создания задачи)
        if text in known_buttons:
            # Если FSM активен, очищаем его перед обработкой кнопки
            conversation_keys = ['task_title', 'task_description', 'task_department', 
                               'task_assignee', 'task_priority', 'task_deadline', 'comment_task_id']
            
            if any(key in context.user_data for key in conversation_keys):
                logger.info(f"Прерывание FSM для обработки кнопки: {text}")
                context.user_data.clear()
            
            # Обрабатываем кнопку
            if text == "📋 Мои задачи":
                await self.my_tasks(update, context)
            elif text == "📊 Задачи отдела":
                await self.list_tasks(update, context)
            elif text == "ℹ️ Справка":
                await self.help_command(update, context)
            elif text == "➕ Создать задачу":
                # Кнопка "➕ Создать задачу" должна обрабатываться ConversationHandler через entry_point
                # Если мы здесь, значит что-то пошло не так, но попробуем обработать
                await self.create_task_start(update, context)
            return
        
        # Если это не известная кнопка, проверяем FSM
        # ВАЖНО: ConversationHandler в python-telegram-bot обрабатывает сообщения ПЕРВЫМ,
        # если пользователь находится в активном состоянии FSM.
        # Если ConversationHandler активен, он перехватит сообщение ДО этого обработчика.
        # Поэтому если мы здесь, значит ConversationHandler НЕ активен или не обработал сообщение.
        
        # Специальная обработка для комментариев: если есть comment_task_id, но ConversationHandler не обработал,
        # попробуем обработать сообщение как комментарий напрямую
        if 'comment_task_id' in context.user_data:
            logger.info(f"Обнаружен comment_task_id, но ConversationHandler не обработал сообщение. Обрабатываем как комментарий: {update.message.text}")
            try:
                await self.comment_text(update, context)
                return
            except Exception as e:
                logger.error(f"Ошибка при обработке комментария: {str(e)}", exc_info=True)
                # Если не удалось обработать, очищаем FSM и продолжаем
                context.user_data.clear()
        
        # Дополнительная проверка: если есть ключи, которые устанавливаются в процессе создания задачи,
        # значит мы в процессе FSM, но ConversationHandler почему-то не обработал сообщение.
        # В этом случае просто возвращаемся, чтобы не мешать.
        conversation_keys = ['task_title', 'task_description', 'task_department', 
                           'task_assignee', 'task_priority', 'task_deadline']
        
        if any(key in context.user_data for key in conversation_keys):
            # Если есть ключи FSM, но ConversationHandler не обработал сообщение,
            # возможно произошла ошибка. Логируем и не обрабатываем.
            logger.warning(f"Обнаружены ключи FSM в user_data, но ConversationHandler не обработал сообщение: {update.message.text}")
            return
        
        # Проверяем, является ли это неизвестной командой (начинается с "/")
        # Примечание: большинство неизвестных команд должны обрабатываться unknown_command,
        # но на случай, если команда попала сюда, обрабатываем её здесь тоже
        if text.startswith('/'):
            # Это команда, но она не была обработана другими обработчиками
            # Значит, это неизвестная команда
            reply_markup = self._get_reply_keyboard(user)
            await update.message.reply_text(
                "❌ Извините, такой команды нет в списке.\n\n"
                "Используйте кнопки клавиатуры или команды для работы с ботом.\n"
                "Нажмите /help для справки.",
                reply_markup=reply_markup
            )
            return
        
        # Если это не команда и не кнопка, показываем подсказку
        reply_markup = self._get_reply_keyboard(user)
        await update.message.reply_text(
            "Используйте кнопки клавиатуры или команды для работы с ботом.\n"
            "Нажмите /help для справки.",
            reply_markup=reply_markup
        )
    
    async def _get_user(self, telegram_chat_id: int) -> Optional[User]:
        """Получение пользователя по telegram_chat_id."""
        try:
            return await async_get_user(telegram_chat_id)
        except User.DoesNotExist:
            return None
    
    def run_polling(self):
        """Запуск бота в режиме polling."""
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    def run_webhook(self, webhook_url: str, port: int = 8000):
        """Настройка webhook."""
        self.application.run_webhook(
            webhook_url=webhook_url,
            port=port
        )
