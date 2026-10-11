document.addEventListener('DOMContentLoaded', function () {
  const forms = document.querySelectorAll('[data-bulk-form]');
  forms.forEach(form => {
    const boxes = Array.from(document.querySelectorAll('input[data-bulk-task]')).filter(box => box.form === form);
    const all = form.querySelector('[data-bulk-all]');
    const counter = form.querySelector('[data-bulk-count]');
    const submit = form.querySelector('[data-bulk-submit]');
    function refresh() {
      const count = boxes.filter(box => box.checked).length;
      counter.textContent = String(count);
      submit.disabled = count === 0;
      all.disabled = boxes.length === 0;
      all.checked = boxes.length > 0 && count === boxes.length;
      all.indeterminate = count > 0 && count < boxes.length;
    }
    all.addEventListener('change', () => { boxes.forEach(box => box.checked = all.checked); refresh(); });
    boxes.forEach(box => box.addEventListener('change', refresh));
    form.addEventListener('submit', event => { if (!boxes.some(box => box.checked)) event.preventDefault(); });
    refresh();
  });
});
