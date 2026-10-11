/* Shared navigation for the single workspace design. */
document.addEventListener('DOMContentLoaded', function () {
  var sidebar = document.querySelector('.studio-sidebar');
  if (!sidebar) return;
  var toggle = document.querySelector('[data-sidebar-toggle]');
  var close = document.querySelector('[data-sidebar-close]');
  function controls() {
    return Array.from(sidebar.querySelectorAll('a[href], button:not([disabled])'));
  }
  function setOpen(open, returnFocus) {
    document.body.classList.toggle('studio-menu-open', open);
    if (toggle) toggle.setAttribute('aria-expanded', String(open));
    var links = controls();
    if (open && links.length) links[0].focus();
    else if (returnFocus && toggle) toggle.focus();
  }
  if (toggle) toggle.addEventListener('click', function () {
    setOpen(!document.body.classList.contains('studio-menu-open'), true);
  });
  if (close) close.addEventListener('click', function () { setOpen(false, true); });
  document.addEventListener('keydown', function (event) {
    if (!document.body.classList.contains('studio-menu-open')) return;
    if (event.key === 'Escape') { event.preventDefault(); setOpen(false, true); }
    if (event.key === 'Tab') {
      var links = controls();
      if (!links.length) return;
      var first = links[0], last = links[links.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  var desktop = window.matchMedia('(min-width: 768px)');
  function resize(event) { if (event.matches) setOpen(false, false); }
  if (desktop.addEventListener) desktop.addEventListener('change', resize);
  else desktop.addListener(resize);
  var active = null;
  sidebar.querySelectorAll('.studio-nav a').forEach(function (link) {
    var path = link.getAttribute('href');
    if (path && (path === location.pathname || (path !== '/dashboard/' && location.pathname.startsWith(path)))) {
      if (!active || path.length > active.getAttribute('href').length) active = link;
    }
  });
  if (active) { active.classList.add('is-active'); active.setAttribute('aria-current', 'page'); }
});
