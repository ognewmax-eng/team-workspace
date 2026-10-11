(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    const root = document.querySelector('[data-lessons]'); if (!root) return;
    const lessons = JSON.parse(document.getElementById('planner-lessons-data').textContent || '[]');
    const feedback = root.querySelector('[data-planner-feedback]');
    const notice = text => { feedback.textContent = text; feedback.hidden = !text; };
    const storageKey = 'yamolod-lessons-view-' + root.dataset.user;
    function setView(view) {
      const week = root.querySelector('[data-lessons-week]'), list = root.querySelector('[data-lessons-list]');
      if (!week || !list) return;
      week.hidden = view === 'list'; list.hidden = view !== 'list';
      root.querySelectorAll('[data-lessons-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.lessonsView === view)));
      try { localStorage.setItem(storageKey, view); } catch (_) {}
    }
    try { setView(localStorage.getItem(storageKey) === 'list' ? 'list' : 'week'); } catch (_) { setView('week'); }
    root.querySelectorAll('[data-lessons-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.lessonsView)));
    const flashKey = 'yamolod-lessons-flash-' + root.dataset.user;
    try { notice(sessionStorage.getItem(flashKey) || ''); sessionStorage.removeItem(flashKey); } catch (_) {}
    function reload(message) {
      try { sessionStorage.setItem(flashKey, message); } catch (_) {}
      const url = new URL(window.location.href); url.searchParams.delete('lesson'); window.location.assign(url.toString());
    }
    function csrf() {
      const field = document.querySelector('[name=csrfmiddlewaretoken]');
      if (field) return field.value;
      const cookie = document.cookie.split(';').map(item => item.trim()).find(item => item.startsWith('csrftoken='));
      return cookie ? decodeURIComponent(cookie.slice(10)) : '';
    }
    let busy = false;
    async function request(url, method, data) {
      if (busy) throw new Error('Дождитесь завершения предыдущего действия.');
      busy = true;
      const buttons = Array.from(root.querySelectorAll('button')).filter(button => !button.disabled);
      buttons.forEach(button => { button.disabled = true; });
      const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 30000);
      try {
        const options = { method: method || 'GET', credentials: 'same-origin', signal: controller.signal, headers: { Accept: 'application/json' } };
        if (method && method !== 'GET') { options.headers['Content-Type'] = 'application/json'; options.headers['X-CSRFToken'] = csrf(); options.body = JSON.stringify(data || {}); }
        const response = await fetch(url, options);
        if (response.redirected) throw new Error('Сессия закончилась. Обновите страницу и войдите снова.');
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) throw new Error('Сервер не подтвердил действие. Обновите страницу и проверьте результат.');
        const result = await response.json();
        if (!response.ok || result.success === false) throw new Error(result.error || 'Не удалось выполнить действие.');
        return result;
      } catch (error) {
        if (error.name === 'AbortError') throw new Error('Ответ не получен. Обновите страницу и проверьте результат перед повтором.');
        throw error;
      } finally { clearTimeout(timeout); busy = false; buttons.forEach(button => { button.disabled = false; }); }
    }
    function modal(element) {
      if (!window.bootstrap || !element) { notice('Окно не загрузилось. Обновите страницу.'); return null; }
      return bootstrap.Modal.getOrCreateInstance(element);
    }
    const path = id => '/schedule/lessons/' + id + '/';
    const templatePath = id => '/schedule/lessons/template/' + id + '/';
    const weekData = () => ({ association_id: root.dataset.association, schedule_version: root.dataset.scheduleVersion });
    const form = root.querySelector('[data-lesson-form]');
    let editing = null, mode = 'create';
    function openLesson(id, action, weekday) {
      if (!form || root.dataset.canEdit !== 'true') return;
      editing = lessons.find(item => String(item.id) === String(id)) || null; mode = action || 'create';
      form.reset();
      const error = form.querySelector('[data-modal-error]'); error.hidden = true; error.textContent = '';
      const defaults = editing || { weekday: weekday || 0, start_time: '10:00', end_time: '11:00', classroom: '', note: '' };
      ['weekday', 'start_time', 'end_time', 'classroom', 'note'].forEach(key => { form.elements[key].value = defaults[key]; });
      if (mode === 'copy') form.elements.weekday.value = (editing.weekday + 1) % 7;
      document.getElementById('plannerLessonTitle').textContent = mode === 'copy' ? 'Копировать занятие' : editing ? 'Изменить занятие' : 'Новое занятие';
      const instance = modal(document.getElementById('plannerLessonModal')); if (instance) instance.show();
    }
    root.querySelectorAll('[data-add-lesson]').forEach(button => button.addEventListener('click', () => openLesson(null, 'create', 0)));
    root.querySelectorAll('[data-add-day]').forEach(button => button.addEventListener('click', () => openLesson(null, 'create', Number(button.dataset.addDay))));
    root.querySelectorAll('[data-edit-lesson]').forEach(button => button.addEventListener('click', () => openLesson(button.dataset.editLesson, 'edit')));
    root.querySelectorAll('[data-copy-lesson]').forEach(button => button.addEventListener('click', () => openLesson(button.dataset.copyLesson, 'copy')));
    if (form) form.addEventListener('submit', async event => {
      event.preventDefault(); if (!form.reportValidity()) return;
      const error = form.querySelector('[data-modal-error]'); error.hidden = true;
      const data = weekData();
      ['weekday', 'start_time', 'end_time', 'classroom', 'note'].forEach(key => { data[key] = form.elements[key].value; });
      data.weekday = Number(data.weekday);
      if (data.end_time <= data.start_time) { error.textContent = 'Окончание должно быть позже начала в тот же день.'; error.hidden = false; return; }
      let url = root.dataset.createUrl;
      if (editing) { data.version = editing.version; url = path(editing.id) + (mode === 'copy' ? 'duplicate/' : 'update/'); }
      try { await request(url, 'POST', data); reload('Занятие сохранено. Изменена типовая неделя.'); }
      catch (exception) { error.textContent = exception.message; error.hidden = false; }
    });
    root.querySelectorAll('[data-delete-lesson]').forEach(button => button.addEventListener('click', async () => {
      const lesson = lessons.find(item => String(item.id) === button.dataset.deleteLesson);
      if (!lesson || !confirm('Удалить это занятие из всей типовой недели, а не только с одной даты?')) return;
      try { await request(path(lesson.id) + 'delete/', 'DELETE', { version: lesson.version }); reload('Занятие удалено.'); } catch (error) { notice(error.message); }
    }));
    let previewId = null;
    async function preview(id, apply) {
      try {
        const result = await request(templatePath(id) + 'preview/');
        const body = root.querySelector('[data-template-content]'); body.replaceChildren();
        document.getElementById('plannerPreviewTitle').textContent = result.name;
        const names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
        result.lessons.forEach(item => {
          const row = document.createElement('p'); row.textContent = names[item.weekday] + ' · ' + item.start_time + '–' + item.end_time + ' · ' + (item.classroom || 'Без аудитории') + (item.note ? '\n' + item.note : ''); body.append(row);
        });
        if (!result.lessons.length) body.textContent = 'Шаблон пуст.';
        const actions = root.querySelector('[data-preview-actions]'); actions.hidden = !apply || !result.lessons.length;
        const replace = actions.querySelector('[value=replace]'); replace.checked = true;
        previewId = apply ? id : null;
        const instance = modal(document.getElementById('plannerPreviewModal')); if (instance) instance.show();
      } catch (error) { notice(error.message); }
    }
    root.querySelectorAll('[data-template-preview]').forEach(button => button.addEventListener('click', () => preview(button.dataset.templatePreview, false)));
    root.querySelectorAll('[data-template-apply]').forEach(button => button.addEventListener('click', () => preview(button.dataset.templateApply, true)));
    root.querySelector('[data-confirm-template]').addEventListener('click', async () => {
      if (!previewId || busy) return;
      const replace = root.querySelector('[name=template-mode]:checked').value === 'replace';
      if (!confirm(replace ? 'Заменить всю типовую неделю? Прежние занятия сохранятся в отдельном шаблоне.' : 'Добавить занятия шаблона к типовой неделе?')) return;
      try { const result = await request(root.dataset.templateApply, 'POST', Object.assign(weekData(), { template_id: previewId, replace_existing: replace })); reload(result.backup_template ? 'Шаблон применён. Прежняя неделя сохранена в шаблонах.' : 'Шаблон применён.'); }
      catch (error) { const body = root.querySelector('[data-template-content]'); const message = document.createElement('p'); message.className = 'planner-modal-error'; message.textContent = error.message; body.append(message); }
    });
    root.querySelectorAll('[data-template-delete]').forEach(button => button.addEventListener('click', async () => {
      if (!confirm('Удалить шаблон? Текущие занятия останутся.')) return;
      try { await request(templatePath(button.dataset.templateDelete) + 'delete/', 'DELETE'); reload('Шаблон удалён.'); } catch (error) { notice(error.message); }
    }));
    const save = root.querySelector('[data-save-template]'); if (save) save.addEventListener('click', async () => {
      const name = prompt('Название шаблона типовой недели:'); if (name === null) return;
      if (!name.trim() || name.trim().length > 200) { notice('Укажите название от 1 до 200 символов.'); return; }
      try { await request(root.dataset.templateCreate, 'POST', Object.assign(weekData(), { name: name.trim() })); reload('Типовая неделя сохранена в шаблон.'); } catch (error) { notice(error.message); }
    });
    const clear = root.querySelector('[data-clear-schedule]'); if (clear) clear.addEventListener('click', async () => {
      if (!confirm('Очистить всю типовую неделю объединения? Прежние занятия автоматически сохранятся в шаблон «До очистки».')) return;
      try { await request(root.dataset.clear, 'POST', weekData()); reload('Неделя очищена. Для восстановления примените шаблон «До очистки».'); } catch (error) { notice(error.message); }
    });
    const selected = new URLSearchParams(window.location.search).get('lesson');
    if (selected && lessons.some(item => String(item.id) === selected)) {
      const card = root.querySelector('[data-lesson-card="' + Number(selected) + '"]'); if (card) card.classList.add('planner-selected');
      if (root.dataset.canEdit === 'true') openLesson(selected, 'edit');
    }
  });
})();
