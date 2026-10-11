(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-member-search]').forEach(input => {
      const picker = input.parentElement.querySelector('[data-member-picker]');
      if (!picker) return;
      input.addEventListener('input', function () {
        const text = input.value.trim().toLocaleLowerCase('ru');
        picker.querySelectorAll('label').forEach(label => {
          const checkbox = label.querySelector('input');
          const row = label.parentElement;
          // Selected people remain visible while searching so they're not forgotten.
          row.hidden = !(label.textContent.toLocaleLowerCase('ru').includes(text) || (checkbox && checkbox.checked));
        });
      });
    });
    document.querySelectorAll('form[data-confirm]').forEach(form => {
      form.addEventListener('submit', event => { if (!confirm(form.dataset.confirm)) event.preventDefault(); });
    });
  });
})();
