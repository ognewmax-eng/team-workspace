(() => {
  'use strict';
  const form = document.querySelector('[data-knowledge-editor]');
  if (!form) return;
  const text = form.querySelector('[name="content"]');
  const preview = form.querySelector('[data-knowledge-preview]');
  const toggle = form.querySelector('[data-preview-toggle]');
  const status = form.querySelector('[data-preview-status]');
  if (!text || !preview || !toggle) return;
  let timer, requestNumber = 0, controller;
  async function refresh() {
    if (preview.hidden) return;
    const number = ++requestNumber;
    if (controller) controller.abort();
    controller = new AbortController();
    status.textContent = 'Обновляю предпросмотр…';
    const data = new URLSearchParams({content: text.value});
    try {
      const response = await fetch(form.dataset.previewUrl, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: {'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value}, body: data
      });
      if (!response.ok) throw new Error('preview');
      const result = await response.json();
      if (number !== requestNumber || preview.hidden) return;
      // Only HTML escaped and rendered by the authenticated server endpoint.
      preview.innerHTML = result.html;
      status.textContent = 'Предпросмотр обновлён. Статья ещё не сохранена.';
    } catch (error) {
      if (error.name !== 'AbortError' && number === requestNumber && !preview.hidden) {
        preview.textContent = '';
        status.textContent = 'Предпросмотр недоступен. Текст остаётся в редакторе.';
      }
    }
  }
  toggle.addEventListener('click', () => {
    preview.hidden = !preview.hidden;
    toggle.setAttribute('aria-expanded', String(!preview.hidden));
    if (preview.hidden) {requestNumber++; if (controller) controller.abort(); status.textContent = '';}
    else refresh();
  });
  text.addEventListener('input', () => {clearTimeout(timer); timer = setTimeout(refresh, 400);});
  form.querySelectorAll('[data-format]').forEach(button => button.addEventListener('click', () => {
    const start = text.selectionStart, end = text.selectionEnd;
    const selected = text.value.slice(start, end) || 'Текст';
    const map = {bold: '**' + selected + '**', heading: '\n## ' + selected + '\n',
      list: '\n' + selected.split('\n').map(line => '- ' + line).join('\n') + '\n',
      quote: '\n> ' + selected + '\n', code: '\n```\n' + selected + '\n```\n',
      link: '[' + selected + '](https://example.com)'};
    const replacement = map[button.dataset.format];
    if (replacement === undefined) return;
    text.setRangeText(replacement, start, end, 'select'); text.focus();
    text.dispatchEvent(new Event('input', {bubbles: true}));
  }));
})();
