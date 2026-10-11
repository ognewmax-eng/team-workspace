/* Status writes are confirmed by the server; drag position is never treated as truth. */
document.addEventListener('DOMContentLoaded', function () {
  const workspace = document.querySelector('[data-workspace]');
  if (!workspace) return;
  const feedback = workspace.querySelector('[data-task-feedback]');
  const flashKey = 'yamolod-task-feedback:' + workspace.dataset.userId;
  let busy = false;
  const sortables = [];
  function announce(message, error) {
    feedback.hidden = false;
    feedback.classList.toggle('is-error', !!error);
    feedback.textContent = message;
    if (error) {
      const refresh = document.createElement('button');
      refresh.type = 'button'; refresh.textContent = 'Обновить страницу';
      refresh.addEventListener('click', () => location.assign(location.pathname + location.search));
      feedback.appendChild(refresh);
    }
  }
  try {
    const flash = sessionStorage.getItem(flashKey);
    if (flash) { sessionStorage.removeItem(flashKey); announce(flash, false); }
  } catch (_) {}
  function csrf() {
    const value = document.cookie.split(';').map(v => v.trim()).find(v => v.startsWith('csrftoken='));
    if (value) return decodeURIComponent(value.slice('csrftoken='.length));
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }
  function lock(value) {
    busy = value; workspace.setAttribute('aria-busy', String(value));
    workspace.querySelectorAll('[data-status-select]').forEach(select => select.disabled = value);
    sortables.forEach(sortable => sortable.option('disabled', value));
  }
  function recount() {
    workspace.querySelectorAll('[data-column]').forEach(column => {
      const empty = column.querySelector('.task-column-empty');
      if (empty) empty.hidden = !!column.querySelector('.task-board-card');
    });
  }
  function moveCard(card, status) {
    const target = workspace.querySelector('.task-board-cards[data-status="' + status + '"]');
    if (target) target.insertBefore(card, target.querySelector('.task-column-empty'));
  }
  async function update(card, status, restore) {
    if (busy) { if (restore) restore(); return; }
    const originalStatus = card.dataset.taskStatus;
    const select = card.querySelector('[data-status-select]');
    const originalPersonal = select ? select.dataset.current : null;
    lock(true); card.classList.add('is-saving');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(card.dataset.updateUrl, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf()},
        body: new URLSearchParams({status: status, version: card.dataset.version || ''})
      });
      let data;
      try { data = await response.json(); } catch (_) { throw new Error('Сервер не подтвердил сохранение. Проверьте состояние после обновления страницы.'); }
      if (!response.ok || !data.success) throw new Error(data.message || 'Не удалось изменить статус.');
      if (!['assigned','in_progress','pending','completed'].includes(data.status)) throw new Error('Не удалось определить общий статус. Обновите страницу.');
      card.dataset.taskStatus = data.status;
      card.dataset.version = data.version;
      if (select) { select.value = data.personal_status || data.status; select.dataset.current = select.value; }
      const label = card.querySelector('[data-status-label]');
      if (label) { label.textContent = data.status_label; label.className = 'task-state state-' + data.status; }
      const progress = card.querySelector('.task-assignee-progress');
      if (progress) progress.textContent = 'Завершили: ' + data.completed_count + ' из ' + data.assignee_count;
      if (workspace.dataset.workspace === 'board') {
        moveCard(card, data.status);
        if (originalStatus !== data.status) {
          const oldCounter = workspace.querySelector('[data-column="' + originalStatus + '"] [data-column-count]');
          const newCounter = workspace.querySelector('[data-column="' + data.status + '"] [data-column-count]');
          if (oldCounter) oldCounter.textContent = Math.max(0, Number(oldCounter.textContent) - 1);
          if (newCounter) newCounter.textContent = Number(newCounter.textContent) + 1;
        }
      }
      announce(data.message, false);
      try { sessionStorage.setItem(flashKey, data.message); } catch (_) {}
      // Re-render from the DB so counts, deadlines, order and filters stay accurate.
      location.assign(location.pathname + location.search);
    } catch (error) {
      if (restore) restore();
      if (select) select.value = originalPersonal;
      announce(error.name === 'AbortError' ? 'Ответ сервера задерживается. Сохранение могло завершиться: обновите страницу перед повторной попыткой.' : (error.message || 'Соединение потеряно. Обновите страницу и проверьте статус.'), true);
    } finally {
      clearTimeout(timer); card.classList.remove('is-saving'); lock(false); recount();
    }
  }
  workspace.querySelectorAll('[data-status-select]').forEach(select => {
    select.addEventListener('change', () => update(select.closest('[data-task-id]'), select.value));
  });
  if (workspace.dataset.workspace === 'board' && typeof Sortable !== 'undefined') {
    workspace.querySelectorAll('.task-board-cards').forEach(column => {
      sortables.push(new Sortable(column, {
        group: 'tasks', animation: 150, sort: false,
        draggable: '.task-board-card[data-editable="true"]', handle: '.task-drag-handle',
        ghostClass: 'task-drag-ghost', dragClass: 'task-drag-active',
        onStart: event => { event.item._taskNextSibling = event.item.nextSibling; },
        onEnd: event => {
          if (event.from === event.to) return;
          const restore = () => {
            const next = event.item._taskNextSibling;
            event.from.insertBefore(event.item, next && next.parentNode === event.from ? next : event.from.querySelector('.task-column-empty'));
          };
          update(event.item, event.to.dataset.status, restore);
        }
      }));
    });
  }
  const key = 'yamolod-task-filter:' + workspace.dataset.userId + ':' + workspace.dataset.workspace;
  const savedLink = workspace.querySelector('[data-saved-filter]');
  function restoreSavedLink() {
    try {
      const query = localStorage.getItem(key);
      if (savedLink && query !== null) { savedLink.href = location.pathname + (query ? '?' + query : ''); savedLink.hidden = false; }
    } catch (_) { /* Browser may disallow storage. Filtering still works. */ }
  }
  restoreSavedLink();
  const saveFilter = workspace.querySelector('[data-save-filter]');
  if (saveFilter) saveFilter.addEventListener('click', () => {
    const form = workspace.querySelector('[data-task-filter]');
    const query = new URLSearchParams(new FormData(form));
    for (const [key, value] of Array.from(query.entries())) if (!value) query.delete(key);
    try { localStorage.setItem(key, query.toString()); restoreSavedLink(); announce('Фильтр сохранён в этом браузере. Примените его кнопкой «Мой сохранённый фильтр».', false); }
    catch (_) { announce('Браузер запрещает сохранение настроек. Обычные фильтры доступны.', true); }
  });
});
