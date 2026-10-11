/**
 * JavaScript для системы уведомлений
 * 
 * БЕЗОПАСНОСТЬ: Все пользовательские данные экранируются перед вставкой в HTML
 * для предотвращения XSS атак.
 */

// Функция экранирования HTML для предотвращения XSS
function escapeHtml(text) {
    if (text == null || text === undefined) {
        return '';
    }
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, function(m) { return map[m]; });
}

// Функция валидации и экранирования URL
function sanitizeUrl(url) {
    if (!url || url === '#') {
        return '#';
    }
    // Проверяем, что URL начинается с / или является относительным
    // Это предотвращает javascript: и data: протоколы
    if (url.startsWith('/') || url.startsWith('./') || url.startsWith('../')) {
        return escapeHtml(url);
    }
    // Если это не относительный URL, возвращаем #
    return '#';
}

// Функция загрузки уведомлений
function loadNotifications() {
    const notificationsList = document.getElementById('notifications-list');
    if (!notificationsList) {
        console.warn('Элемент notifications-list не найден');
        return;
    }

    // Показываем индикатор загрузки
    notificationsList.innerHTML = `
        <li>
            <div class="dropdown-item-text text-center py-3">
                <div class="spinner-border spinner-border-sm text-primary" role="status">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
            </div>
        </li>
    `;

    // Используем URL из window.NOTIFICATIONS_URLS или fallback
    const listUrl = (window.NOTIFICATIONS_URLS && window.NOTIFICATIONS_URLS.list) || '/notifications/list/';
    
    if (!listUrl) {
        console.error('URL для загрузки уведомлений не определен');
        notificationsList.innerHTML = `
            <li>
                <div class="dropdown-item-text text-center text-danger py-3">
                    <i class="bi bi-exclamation-triangle"></i>
                    <div class="small mt-2">Ошибка конфигурации</div>
                </div>
            </li>
        `;
        return;
    }
    
    fetch(listUrl, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
        },
        credentials: 'same-origin'
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            if (data.notifications && data.notifications.length > 0) {
                let html = '';
                data.notifications.forEach(notification => {
                    const icon = getNotificationIcon(notification.type);
                    const isReadClass = notification.is_read ? '' : 'bg-light border-start border-primary border-3';
                    const badge = notification.is_read ? '' : '<span class="badge bg-primary ms-2">Новое</span>';
                    // Экранируем все пользовательские данные для предотвращения XSS
                    const typeDisplay = escapeHtml(notification.type_display || notification.type);
                    const taskUrl = sanitizeUrl(notification.task_url);
                    const message = escapeHtml(notification.message);
                    const createdAt = escapeHtml(notification.created_at);
                    
                    html += `
                        <li>
                            <a class="dropdown-item ${isReadClass}" href="${taskUrl}" style="white-space: normal;">
                                <div class="d-flex align-items-start">
                                    <div class="me-2">${icon}</div>
                                    <div class="flex-grow-1">
                                        <div class="d-flex justify-content-between align-items-start mb-1">
                                            <small class="fw-bold">${typeDisplay} ${badge}</small>
                                            <small class="text-muted">${createdAt}</small>
                                        </div>
                                        <div class="small">${message}</div>
                                    </div>
                                </div>
                            </a>
                        </li>
                    `;
                });
                notificationsList.innerHTML = html;
            } else {
                notificationsList.innerHTML = `
                    <li>
                        <div class="dropdown-item-text text-center text-muted py-3">
                            <i class="bi bi-bell-slash fs-4 d-block mb-2"></i>
                            Нет новых уведомлений
                        </div>
                    </li>
                `;
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки уведомлений:', error);
            console.error('URL запроса:', listUrl);
            console.error('Детали ошибки:', {
                message: error.message,
                stack: error.stack,
                name: error.name
            });
            
            let errorMessage = 'Ошибка загрузки уведомлений';
            if (error.message) {
                errorMessage += `: ${escapeHtml(error.message)}`;
            }
            
            notificationsList.innerHTML = `
                <li>
                    <div class="dropdown-item-text text-center text-danger py-3">
                        <i class="bi bi-exclamation-triangle"></i>
                        <div class="small mt-2">${escapeHtml(errorMessage)}</div>
                        <div class="small text-muted mt-1">Попробуйте обновить страницу</div>
                    </div>
                </li>
            `;
        });
}

// Функция получения иконки для типа уведомления
function getNotificationIcon(type) {
    const iconMap = {
        'task_assigned': '<i class="bi bi-clipboard-check text-primary"></i>',
        'task_comment': '<i class="bi bi-chat-dots text-info"></i>',
        'task_status_changed': '<i class="bi bi-arrow-repeat text-success"></i>',
    };
    return iconMap[type] || '<i class="bi bi-bell text-secondary"></i>';
}

// Функция обновления счетчика уведомлений
function updateNotificationCount() {
    const badge = document.getElementById('notification-badge');
    if (!badge) return;

    // Используем URL из window.NOTIFICATIONS_URLS или fallback
    const countUrl = (window.NOTIFICATIONS_URLS && window.NOTIFICATIONS_URLS.count) || '/notifications/count/';
    
    fetch(countUrl, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
        },
        credentials: 'same-origin'
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.count > 0) {
                badge.textContent = data.count;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        })
        .catch(error => {
            console.error('Ошибка обновления счетчика:', error);
            // Скрываем бейдж при ошибке
            badge.style.display = 'none';
        });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Загружаем только счетчик при загрузке страницы
    updateNotificationCount();

    // Обновляем счетчик каждые 30 секунд
    setInterval(function() {
        updateNotificationCount();
    }, 30000);

    // Загружаем уведомления только при открытии выпадающего меню
    const notificationsDropdown = document.getElementById('notificationsDropdown');
    if (notificationsDropdown) {
        // Используем событие Bootstrap 5 для выпадающего меню
        notificationsDropdown.addEventListener('show.bs.dropdown', function() {
            // Загружаем уведомления перед открытием меню
            loadNotifications();
        });
        
        // Также обрабатываем событие shown на случай, если show не сработало
        notificationsDropdown.addEventListener('shown.bs.dropdown', function() {
            // Дополнительная проверка - если список пустой, загружаем
            const list = document.getElementById('notifications-list');
            if (list && list.innerHTML.includes('spinner-border')) {
                loadNotifications();
            }
        });
    }
});

// Экспорт функций для использования в других скриптах
window.Notifications = {
    loadNotifications,
    updateNotificationCount
};

