// Расписание занятий - JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const associationSelect = document.getElementById('association-select');
    const scheduleGrid = document.getElementById('schedule-grid');
    const newLessonDrag = document.getElementById('new-lesson-drag');
    const lessonModal = new bootstrap.Modal(document.getElementById('lessonModal'));
    const templatesModal = new bootstrap.Modal(document.getElementById('templatesModal'));
    const createTemplateModal = new bootstrap.Modal(document.getElementById('createTemplateModal'));
    
    let currentAssociationId = null;
    let currentAssociationColor = '#3b82f6';
    let lessons = [];
    let draggedLesson = null;
    let draggedFromPalette = false;

    // Загрузка занятий при выборе объединения
    associationSelect.addEventListener('change', function() {
        const selectedOption = this.options[this.selectedIndex];
        currentAssociationId = this.value;
        currentAssociationColor = selectedOption.getAttribute('data-color') || '#3b82f6';
        
        if (currentAssociationId) {
            loadLessons(currentAssociationId);
        } else {
            clearSchedule();
        }
    });

    // Генерация сетки расписания
    function generateScheduleGrid() {
        const scheduleGrid = document.getElementById('schedule-grid');
        const loadingIndicator = document.getElementById('schedule-grid-loading');
        
        if (!scheduleGrid) {
            console.error('Элемент schedule-grid не найден!');
            return;
        }
        
        // Показываем индикатор загрузки
        if (loadingIndicator) {
            loadingIndicator.style.display = 'block';
        }
        
        let html = '';
        
        // Заголовок времени (пустая ячейка в левом верхнем углу)
        html += '<div class="schedule-header"></div>';
        
        // Заголовки дней недели
        const weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
        weekdays.forEach(day => {
            html += `<div class="schedule-header">${day}</div>`;
        });
        
        // Генерируем временные слоты и ячейки
        for (let hour = 8; hour < 21; hour++) {
            // Слот на час (00 минут)
            html += `<div class="time-slot">${hour}:00</div>`;
            for (let day = 0; day < 7; day++) {
                html += `<div class="schedule-cell empty-cell" data-day="${day}" data-hour="${hour}" data-minute="0" id="cell-${hour}-${day}"></div>`;
            }
            
            // Слот на полчаса (30 минут)
            html += `<div class="time-slot">${hour}:30</div>`;
            for (let day = 0; day < 7; day++) {
                html += `<div class="schedule-cell empty-cell" data-day="${day}" data-hour="${hour}" data-minute="30" id="cell-${hour}-30-${day}"></div>`;
            }
        }
        
        scheduleGrid.innerHTML = html;
        
        // Скрываем индикатор загрузки
        if (loadingIndicator) {
            loadingIndicator.style.display = 'none';
        }
        
        // Добавляем обработчики для drag & drop на все ячейки
        setupCellDropHandlers();
        
        // Отладочный вывод
        const cellCount = document.querySelectorAll('.schedule-cell').length;
        const timeSlotCount = document.querySelectorAll('.time-slot').length;
        const headerCount = document.querySelectorAll('.schedule-header').length;
        console.log('Сетка расписания сгенерирована:');
        console.log('- Заголовков:', headerCount);
        console.log('- Временных слотов:', timeSlotCount);
        console.log('- Ячеек:', cellCount);
        
        if (cellCount === 0) {
            console.error('ОШИБКА: Ячейки не были созданы!');
            if (loadingIndicator) {
                loadingIndicator.innerHTML = '<div class="alert alert-danger">Ошибка генерации сетки. Перезагрузите страницу.</div>';
                loadingIndicator.style.display = 'block';
            }
        }
    }
    
    // Настройка обработчиков drag & drop для ячеек
    function setupCellDropHandlers() {
        const cells = document.querySelectorAll('.schedule-cell');
        cells.forEach(cell => {
            cell.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.classList.add('drag-over');
            });
            
            cell.addEventListener('dragleave', function(e) {
                e.preventDefault();
                e.stopPropagation();
                // Проверяем, что мы действительно покинули ячейку
                if (!this.contains(e.relatedTarget)) {
                    this.classList.remove('drag-over');
                }
            });
            
            // Также добавляем обработчик клика для создания занятия
            cell.addEventListener('click', function(e) {
                // Если клик по пустой ячейке (не по занятию)
                if (!e.target.closest('.lesson-block') && currentAssociationId) {
                    const weekday = parseInt(this.getAttribute('data-day'));
                    const hour = parseInt(this.getAttribute('data-hour'));
                    const minute = parseInt(this.getAttribute('data-minute'));
                    const startTime = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
                    openLessonModal(null, weekday, startTime);
                }
            });
            
            cell.addEventListener('drop', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.classList.remove('drag-over');
                handleCellDrop(this, e);
            });
        });
    }
    
    // Обработка drop на ячейку
    function handleCellDrop(cell, e) {
        const weekday = parseInt(cell.getAttribute('data-day'));
        const hour = parseInt(cell.getAttribute('data-hour'));
        const minute = parseInt(cell.getAttribute('data-minute'));
        const startTime = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
        
        if (draggedFromPalette) {
            // Создание нового занятия
            openLessonModal(null, weekday, startTime);
        } else if (draggedLesson) {
            // Перемещение существующего занятия
            moveLesson(draggedLesson.id, weekday, startTime);
        }
    }

    // Отрисовка занятий при загрузке страницы
    function renderInitialLessons() {
        // Получаем данные занятий из глобальной переменной
        const lessonsData = window.LESSONS_DATA || [];
        
        if (lessonsData && lessonsData.length > 0) {
            lessonsData.forEach(lesson => {
                positionLesson(lesson.id, lesson.weekday, lesson.start_time, lesson.end_time, lesson.color);
            });
        }
    }
    
    // Инициализация при загрузке страницы
    // Устанавливаем currentAssociationId из выбранного значения в селекте
    if (associationSelect && associationSelect.value) {
        const selectedOption = associationSelect.options[associationSelect.selectedIndex];
        currentAssociationId = associationSelect.value;
        currentAssociationColor = selectedOption.getAttribute('data-color') || '#3b82f6';
    }
    
    // Генерируем сетку сразу
    generateScheduleGrid();
    
        // Отрисовываем занятия после генерации сетки
    setTimeout(function() {
        renderInitialLessons();
    }, 300);

    // Загрузка занятий (используем данные из шаблона или перезагружаем страницу)
    function loadLessons(associationId) {
        if (!associationId) {
            clearSchedule();
            return;
        }
        
        // Перезагружаем страницу с выбранным объединением для получения актуальных данных
        window.location.href = `/schedule/lessons/?association=${associationId}`;
    }

    // Отрисовка занятий на сетке
    function renderLessons() {
        clearSchedule();
        
        // Получаем все блоки занятий из DOM (если они есть)
        const lessonBlocks = document.querySelectorAll('.lesson-block');
        lessonBlocks.forEach(block => {
            const lessonId = block.getAttribute('data-lesson-id');
            const weekday = parseInt(block.getAttribute('data-weekday'));
            const startTime = block.getAttribute('data-start-time');
            const endTime = block.getAttribute('data-end-time');
            
            positionLesson(lessonId, weekday, startTime, endTime, currentAssociationColor);
        });
    }

    // Позиционирование занятия на сетке
    function positionLesson(lessonId, weekday, startTime, endTime, color) {
        const [startHour, startMinute] = startTime.split(':').map(Number);
        const [endHour, endMinute] = endTime.split(':').map(Number);
        
        const startMinutes = startHour * 60 + startMinute;
        const endMinutes = endHour * 60 + endMinute;
        const duration = endMinutes - startMinutes;
        
        // Находим ячейку для начала занятия (ищем ближайшую ячейку по времени)
        // Округляем до ближайшего слота (0 или 30 минут)
        const roundedMinute = startMinute < 30 ? 0 : 30;
        const startCell = document.querySelector(
            `[data-day="${weekday}"][data-hour="${startHour}"][data-minute="${roundedMinute}"]`
        );
        
        if (!startCell) {
            console.warn(`Не найдена ячейка для занятия: день=${weekday}, время=${startTime}`);
            return;
        }
        
        // Убираем класс empty-cell, так как ячейка больше не пустая
        startCell.classList.remove('empty-cell');
        
        // Вычисляем точное смещение внутри ячейки (если время не кратно 30 минутам)
        const offsetMinutes = startMinute - roundedMinute;
        const offsetPixels = (offsetMinutes / 30) * 40; // 40px на 30 минут
        
        // Создаем блок занятия
        const lessonBlock = document.createElement('div');
        lessonBlock.className = 'lesson-block';
        lessonBlock.style.backgroundColor = color;
        lessonBlock.setAttribute('data-lesson-id', lessonId);
        lessonBlock.setAttribute('data-weekday', weekday);
        lessonBlock.setAttribute('data-start-time', startTime);
        lessonBlock.setAttribute('data-end-time', endTime);
        
        // Вычисляем высоту блока (количество слотов по 30 минут)
        const slots = Math.ceil(duration / 30);
        lessonBlock.style.height = `${slots * 40 - 4}px`; // -4 для отступов
        lessonBlock.style.top = `${2 + offsetPixels}px`;
        lessonBlock.textContent = `${startTime} - ${endTime}`;
        
        // Делаем блок перетаскиваемым
        lessonBlock.draggable = true;
        lessonBlock.addEventListener('dragstart', handleLessonDragStart);
        lessonBlock.addEventListener('click', handleLessonClick);
        lessonBlock.addEventListener('mouseenter', showLessonTooltip);
        
        startCell.appendChild(lessonBlock);
    }

    // Очистка сетки
    function clearSchedule() {
        document.querySelectorAll('.lesson-block').forEach(block => {
            const cell = block.parentElement;
            block.remove();
            // Восстанавливаем класс empty-cell для пустых ячеек
            if (cell && !cell.querySelector('.lesson-block')) {
                cell.classList.add('empty-cell');
            }
        });
    }

    // Drag & Drop для нового занятия из палитры
    if (newLessonDrag) {
        newLessonDrag.addEventListener('dragstart', function(e) {
            draggedFromPalette = true;
            e.dataTransfer.effectAllowed = 'copy';
        });
    }

    // Drag & Drop для существующих занятий
    function handleLessonDragStart(e) {
        draggedFromPalette = false;
        draggedLesson = {
            id: e.target.getAttribute('data-lesson-id'),
            weekday: parseInt(e.target.getAttribute('data-weekday')),
            startTime: e.target.getAttribute('data-start-time'),
            endTime: e.target.getAttribute('data-end-time')
        };
        e.dataTransfer.effectAllowed = 'move';
    }

    // Обработка drop на ячейку (резервный обработчик для всей сетки)
    scheduleGrid.addEventListener('dragover', function(e) {
        if (e.target.closest('.schedule-cell')) {
            e.preventDefault();
            e.dataTransfer.dropEffect = draggedFromPalette ? 'copy' : 'move';
        }
    });

    // Клик по занятию для редактирования
    function handleLessonClick(e) {
        const lessonId = e.target.getAttribute('data-lesson-id');
        const weekday = parseInt(e.target.getAttribute('data-weekday'));
        const startTime = e.target.getAttribute('data-start-time');
        const endTime = e.target.getAttribute('data-end-time');
        openLessonModal(lessonId, weekday, startTime, endTime);
    }

    // Открытие модального окна занятия
    function openLessonModal(lessonId, weekday, startTime, endTime = null) {
        // Устанавливаем lesson_id только если это валидное число
        const lessonIdInput = document.getElementById('lesson-id');
        if (lessonId && !isNaN(parseInt(lessonId))) {
            lessonIdInput.value = parseInt(lessonId);
        } else {
            lessonIdInput.value = '';
        }
        
        // Устанавливаем association_id из currentAssociationId или из селекта
        const associationIdInput = document.getElementById('lesson-association-id');
        let associationId = currentAssociationId;
        if (!associationId && associationSelect && associationSelect.value) {
            associationId = associationSelect.value;
        }
        associationIdInput.value = associationId || '';
        document.getElementById('lesson-weekday').value = weekday !== undefined ? weekday : 0;
        document.getElementById('lesson-start-time').value = startTime || '08:00';
        document.getElementById('lesson-end-time').value = endTime || '09:00';
        
        if (lessonId && !isNaN(parseInt(lessonId))) {
            document.getElementById('lessonModalTitle').textContent = 'Редактировать занятие';
            // Загрузить данные занятия через AJAX
        } else {
            document.getElementById('lessonModalTitle').textContent = 'Создать занятие';
        }
        
        // Правильно показываем модальное окно с обработкой событий
        lessonModal.show();
        
        // Убираем aria-hidden после показа модального окна
        const modalElement = document.getElementById('lessonModal');
        if (modalElement) {
            modalElement.addEventListener('shown.bs.modal', function() {
                this.removeAttribute('aria-hidden');
            }, { once: true });
        }
    }

    // Сохранение занятия
    const saveLessonBtn = document.getElementById('save-lesson-btn');
    if (saveLessonBtn) {
        saveLessonBtn.addEventListener('click', function() {
        const form = document.getElementById('lesson-form');
        const formData = new FormData(form);
        const lessonIdValue = formData.get('lesson_id');
        
        // Проверяем, что lesson_id является валидным числом или пустой строкой
        const lessonId = lessonIdValue && lessonIdValue.trim() !== '' && !isNaN(parseInt(lessonIdValue))
            ? parseInt(lessonIdValue)
            : null;
        
        // Получаем association_id из формы или из currentAssociationId или из селекта
        let associationId = formData.get('association_id');
        if (!associationId || associationId.trim() === '') {
            // Если в форме нет значения, используем currentAssociationId или значение из селекта
            associationId = currentAssociationId || (associationSelect && associationSelect.value ? associationSelect.value : null);
        }
        
        // Проверяем, что association_id является числом
        if (!associationId || isNaN(parseInt(associationId))) {
            alert('Ошибка: не выбрано объединение. Пожалуйста, выберите объединение в верхней панели.');
            return;
        }
        
        const data = {
            association_id: parseInt(associationId),
            weekday: parseInt(formData.get('weekday')),
            start_time: formData.get('start_time'),
            end_time: formData.get('end_time'),
            classroom: formData.get('classroom') || '',
            note: formData.get('note') || ''
        };
        
        const url = lessonId 
            ? `/schedule/lessons/${lessonId}/update/`
            : '/schedule/lessons/create/';
        const method = 'POST';
        
        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                lessonModal.hide();
                // Обновляем расписание без перезагрузки
                if (data.lesson) {
                    clearSchedule();
                    positionLesson(
                        data.lesson.id,
                        data.lesson.weekday,
                        data.lesson.start_time,
                        data.lesson.end_time,
                        data.lesson.color || currentAssociationColor
                    );
                }
                // Перезагружаем список занятий
                if (currentAssociationId) {
                    loadLessons(currentAssociationId);
                }
            } else {
                alert('Ошибка: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Произошла ошибка при сохранении');
        });
        });
    }

    // Перемещение занятия
    function moveLesson(lessonId, newWeekday, newStartTime) {
        fetch(`/schedule/lessons/${lessonId}/move/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                weekday: newWeekday,
                start_time: newStartTime
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Удаляем занятие из DOM
                const lessonBlock = document.querySelector(`[data-lesson-id="${lessonId}"]`);
                if (lessonBlock) {
                    const cell = lessonBlock.parentElement;
                    lessonBlock.remove();
                    // Восстанавливаем класс empty-cell
                    if (cell && !cell.querySelector('.lesson-block')) {
                        cell.classList.add('empty-cell');
                    }
                }
                // Обновляем список занятий
                if (currentAssociationId) {
                    loadLessons(currentAssociationId);
                }
            } else {
                alert('Ошибка: ' + data.error);
            }
        });
    }

    // Удаление занятия
    document.addEventListener('click', function(e) {
        if (e.target.closest('.delete-lesson-btn')) {
            const lessonId = e.target.closest('.delete-lesson-btn').getAttribute('data-lesson-id');
            if (confirm('Удалить занятие?')) {
                fetch(`/schedule/lessons/${lessonId}/delete/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken')
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        location.reload();
                    } else {
                        alert('Ошибка: ' + data.error);
                    }
                });
            }
        }
    });

    // Создание шаблона
    const createTemplateBtn = document.getElementById('create-template-btn');
    if (createTemplateBtn) {
        createTemplateBtn.addEventListener('click', function() {
            if (!currentAssociationId) {
                alert('Выберите объединение');
                return;
            }
            createTemplateModal.show();
            
            // Убираем aria-hidden после показа модального окна
            const modalElement = document.getElementById('createTemplateModal');
            if (modalElement) {
                modalElement.addEventListener('shown.bs.modal', function() {
                    this.removeAttribute('aria-hidden');
                }, { once: true });
            }
        });
    }

    const saveTemplateBtn = document.getElementById('save-template-btn');
    if (saveTemplateBtn) {
        saveTemplateBtn.addEventListener('click', function() {
            const name = document.getElementById('template-name').value;
            const description = document.getElementById('template-description').value;
            
            fetch('/schedule/lessons/template/create/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    association_id: currentAssociationId,
                    name: name,
                    description: description
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    createTemplateModal.hide();
                    if (currentAssociationId) {
                        loadLessons(currentAssociationId);
                    }
                } else {
                    alert('Ошибка: ' + data.error);
                }
            });
        });
    }

    // Применение шаблона
    const applyTemplateBtn = document.getElementById('apply-template-btn');
    if (applyTemplateBtn) {
        applyTemplateBtn.addEventListener('click', function() {
            if (!currentAssociationId) {
                alert('Выберите объединение');
                return;
            }
            templatesModal.show();
            
            // Убираем aria-hidden после показа модального окна
            const modalElement = document.getElementById('templatesModal');
            if (modalElement) {
                modalElement.addEventListener('shown.bs.modal', function() {
                    this.removeAttribute('aria-hidden');
                }, { once: true });
            }
        });
    }

    document.addEventListener('click', function(e) {
        if (e.target.closest('.apply-template-btn')) {
            const templateId = e.target.closest('.apply-template-btn').getAttribute('data-template-id');
            const replace = confirm('Заменить существующие занятия?');
            
            fetch('/schedule/lessons/template/apply/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    template_id: templateId,
                    association_id: currentAssociationId,
                    replace_existing: replace
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    templatesModal.hide();
                    location.reload();
                } else {
                    alert('Ошибка: ' + data.error);
                }
            });
        }
    });

    // Очистка недели
    const clearWeekBtn = document.getElementById('clear-week-btn');
    if (clearWeekBtn) {
        clearWeekBtn.addEventListener('click', function() {
            if (!currentAssociationId) {
                alert('Выберите объединение');
                return;
            }
            if (confirm('Очистить все занятия недели?')) {
                fetch('/schedule/lessons/clear-week/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        association_id: currentAssociationId
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        location.reload();
                    } else {
                        alert('Ошибка: ' + data.error);
                    }
                });
            }
        });
    }

    // Переключение вида
    const viewWeekBtn = document.getElementById('view-week-btn');
    if (viewWeekBtn) {
        viewWeekBtn.addEventListener('click', function() {
            document.getElementById('schedule-week-view').style.display = 'block';
            document.getElementById('schedule-list-view').style.display = 'none';
            this.classList.add('active');
            const viewListBtn = document.getElementById('view-list-btn');
            if (viewListBtn) {
                viewListBtn.classList.remove('active');
            }
        });
    }

    const viewListBtn = document.getElementById('view-list-btn');
    if (viewListBtn) {
        viewListBtn.addEventListener('click', function() {
            document.getElementById('schedule-week-view').style.display = 'none';
            document.getElementById('schedule-list-view').style.display = 'block';
            this.classList.add('active');
            const viewWeekBtn = document.getElementById('view-week-btn');
            if (viewWeekBtn) {
                viewWeekBtn.classList.remove('active');
            }
        });
    }

    // Показ подсказки при наведении
    function showLessonTooltip(e) {
        // Реализация tooltip
    }

    // Вспомогательная функция для получения CSRF токена
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});
