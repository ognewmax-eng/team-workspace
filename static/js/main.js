/**
 * Основной JavaScript файл для улучшения UX
 */

// Утилита для плавной анимации появления элементов
function fadeInElements(selector, delay = 100) {
    const elements = document.querySelectorAll(selector);
    elements.forEach((element, index) => {
        element.style.opacity = '0';
        element.style.transform = 'translateY(20px)';
        setTimeout(() => {
            element.style.transition = 'all 0.5s ease-out';
            element.style.opacity = '1';
            element.style.transform = 'translateY(0)';
        }, index * delay);
    });
}

// Улучшение таблиц - добавление эффекта при наведении
function enhanceTables() {
    const tables = document.querySelectorAll('.table tbody tr');
    tables.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.transition = 'all 0.2s ease';
        });
    });
}

// Улучшение кнопок - добавление ripple эффекта
function addRippleEffect() {
    const buttons = document.querySelectorAll('.btn:not(.no-ripple)');
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple');
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
}

// Автоматическое форматирование дат
function formatDates() {
    const dateElements = document.querySelectorAll('[data-date]');
    dateElements.forEach(element => {
        const date = new Date(element.getAttribute('data-date'));
        element.textContent = date.toLocaleDateString('ru-RU', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    });
}

// Улучшение форм - валидация в реальном времени
function enhanceForms() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                if (this.checkValidity()) {
                    this.classList.add('is-valid');
                    this.classList.remove('is-invalid');
                } else {
                    this.classList.add('is-invalid');
                    this.classList.remove('is-valid');
                }
            });
        });
    });
}

// Подсветка активных элементов навигации
function highlightActiveNav() {
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
            link.style.background = 'rgba(255, 255, 255, 0.2)';
        }
    });
}

// Показ индикатора загрузки
function showLoadingIndicator(element) {
    if (element) {
        const originalContent = element.innerHTML;
        element.disabled = true;
        element.dataset.originalContent = originalContent;
        element.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Загрузка...';
    }
}

// Скрытие индикатора загрузки
function hideLoadingIndicator(element) {
    if (element && element.dataset.originalContent) {
        element.disabled = false;
        element.innerHTML = element.dataset.originalContent;
        delete element.dataset.originalContent;
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Анимация появления карточек
    if (!document.body.classList.contains('design-studio') && !document.body.classList.contains('studio-auth')) {
        fadeInElements('.card', 100);
    }
    
    // Сохраняем подтверждение удаления из общего шаблона.
    document.querySelectorAll('form[method="post"] button[type="submit"]').forEach(button => {
        if (button.textContent.includes('Удалить') || button.textContent.includes('Delete')) {
            button.addEventListener('click', function(event) {
                if (!confirm('Вы уверены, что хотите выполнить это действие?')) event.preventDefault();
            });
        }
    });

    // Улучшение таблиц
    enhanceTables();
    
    // Ripple эффект для кнопок
    addRippleEffect();
    
    // Форматирование дат
    formatDates();
    
    // Улучшение форм
    enhanceForms();
    
    // Подсветка активной навигации
    highlightActiveNav();
    
    // Автоматическое скрытие уведомлений
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });
    
    // Показ индикатора загрузки при отправке форм
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                showLoadingIndicator(submitBtn);
            }
        });
    });
    
    // Плавная прокрутка
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#' && href.length > 1) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });
    
    // Улучшение tooltips и popovers Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

// Экспорт функций для использования в других скриптах
window.UIUtils = {
    fadeInElements,
    enhanceTables,
    addRippleEffect,
    formatDates,
    enhanceForms,
    highlightActiveNav,
    showLoadingIndicator,
    hideLoadingIndicator
};



