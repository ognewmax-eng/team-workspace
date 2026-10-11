/**
 * JavaScript для уведомлений о ожидающих одобрения регистрациях
 */

document.addEventListener('DOMContentLoaded', function() {
    // Обновление счетчика ожидающих одобрения
    function updatePendingBadge() {
        const badge = document.getElementById('pending-badge');
        if (badge) {
            // Можно добавить AJAX запрос для получения актуального количества
            // Пока просто показываем бейдж, если он есть
            const count = parseInt(badge.textContent) || 0;
            if (count > 0) {
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }
    }
    
    updatePendingBadge();
    
    // Обновление каждые 30 секунд (опционально)
    // setInterval(updatePendingBadge, 30000);
});



