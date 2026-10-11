(() => {
  'use strict';
  const sidebar = document.getElementById('nav-sidebar');
  const toggle = document.getElementById('toggle-nav-sidebar');
  const main = document.getElementById('main');
  if (!sidebar || !toggle || !main) return;
  const mobile = window.matchMedia('(max-width: 767px)');
  let desktopOpen = true;
  try { desktopOpen = localStorage.getItem('yamolod.admin.menuOpen') !== 'false'; } catch (_) {}
  let open = mobile.matches ? false : desktopOpen;
  function apply() {
    main.classList.toggle('shifted', open);
    toggle.setAttribute('aria-expanded', String(open));
    sidebar.setAttribute('aria-expanded', String(open));
  }
  apply();
  toggle.addEventListener('click', () => {
    open = !open; apply();
    if (!mobile.matches) { desktopOpen = open; try {localStorage.setItem('yamolod.admin.menuOpen', String(open));} catch (_) {} }
  });
  function resize() {open = mobile.matches ? false : desktopOpen; apply();}
  if (mobile.addEventListener) mobile.addEventListener('change', resize);
  else if (mobile.addListener) mobile.addListener(resize);
  const search = document.getElementById('yam-admin-search');
  const empty = sidebar.querySelector('[data-admin-search-empty]');
  const sections = Array.from(sidebar.querySelectorAll('[data-admin-section]'));
  const initial = new Map(sections.map(section => [section, section.open]));
  let filtering = false;
  if (!search) return;
  function filter() {
    const value = search.value.trim().toLocaleLowerCase('ru');
    if (value && !filtering) sections.forEach(section => initial.set(section, section.open));
    let matched = 0;
    sections.forEach(section => {
      let visible = 0;
      section.querySelectorAll('[data-admin-item]').forEach(item => {
        const matches = !value || item.dataset.searchText.toLocaleLowerCase('ru').includes(value);
        item.hidden = !matches; if (matches) visible++;
      });
      section.hidden = !visible;
      if (value) section.open = visible > 0;
      else section.open = initial.get(section);
      matched += visible;
    });
    if (empty) empty.hidden = matched > 0;
    filtering = Boolean(value);
  }
  search.addEventListener('input', filter);
  search.addEventListener('keydown', event => {
    if (event.key === 'Escape') {event.preventDefault(); search.value = ''; filter();}
  });
  const clear = sidebar.querySelector('[data-admin-search-clear]');
  if (clear) clear.addEventListener('click', () => {search.value = ''; filter(); search.focus();});
  document.addEventListener('keydown', event => {
    const target = event.target;
    if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey ||
        (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)))) return;
    event.preventDefault(); open = true; apply(); search.focus();
  });
})();
