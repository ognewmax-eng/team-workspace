(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    const root = document.querySelector('[data-calendar]');
    if (!root) return;
    const feedback = root.querySelector('[data-planner-feedback]');
    const notice = text => { feedback.textContent = text; feedback.hidden = !text; };
    if (!window.FullCalendar) { notice('Календарная сетка не загрузилась. Откройте повестку по ссылке ниже.'); return; }
    const key = 'yamolod-calendar-view-' + root.dataset.user;
    const views = ['dayGridMonth', 'timeGridWeek', 'listWeek'];
    let view = window.innerWidth < 700 ? 'listWeek' : 'timeGridWeek';
    try { const saved = localStorage.getItem(key); if (views.includes(saved)) view = saved; } catch (_) {}
    const calendar = new FullCalendar.Calendar(root.querySelector('#planner-calendar'), {
      locale: 'ru', firstDay: 1, initialDate: root.dataset.initial, initialView: view,
      // The feed uses the site's wall clock for both dated events and recurring lessons.
      // UTC mode prevents the viewer's computer timezone from shifting those strings.
      timeZone: 'UTC', now: root.dataset.now, nowIndicator: true,
      headerToolbar: { left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek,listWeek' },
      buttonText: { today: 'Сегодня', month: 'Месяц', week: 'Неделя', list: 'Повестка' },
      height: 'auto', contentHeight: 640, allDaySlot: false, dayMaxEvents: 4,
      slotDuration: '00:30:00', scrollTime: '09:00:00', editable: false,
      eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
      slotLabelFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
      noEventsContent: 'В этом периоде нет событий по выбранным фильтрам.',
      datesSet: info => { try { localStorage.setItem(key, info.view.type); } catch (_) {} },
      events: function (info, success, failure) {
        const params = new URLSearchParams(window.location.search);
        params.set('start', info.startStr.slice(0, 10)); params.set('end', info.endStr.slice(0, 10));
        notice('Загрузка событий…');
        fetch(root.dataset.feed + '?' + params.toString(), { credentials: 'same-origin', headers: { Accept: 'application/json' } })
          .then(async response => {
            if (response.redirected) throw new Error('Сессия закончилась. Обновите страницу и войдите снова.');
            const data = await response.json();
            if (!response.ok || !Array.isArray(data)) throw new Error(data.error || 'Не удалось загрузить события.');
            return data;
          }).then(data => { notice(''); success(data); })
          .catch(error => { notice(error.message || 'Не удалось загрузить события. Откройте повестку.'); failure(error); });
      },
      eventDidMount: info => {
        const props = info.event.extendedProps;
        info.el.title = [props.type, info.event.title, props.location, props.description].filter(Boolean).join('\n');
      },
      eventContent: info => {
        const container = document.createElement('span');
        container.className = 'planner-calendar-event';
        const title = document.createElement('strong'); title.textContent = (info.timeText ? info.timeText + ' ' : '') + info.event.title;
        const details = document.createElement('small');
        details.textContent = [info.event.extendedProps.type, info.event.extendedProps.location].filter(Boolean).join(' · ');
        container.append(title, details); return { domNodes: [container] };
      },
      dateClick: info => {
        if (!root.dataset.create) return;
        const start = info.allDay ? info.dateStr + 'T10:00' : info.dateStr.slice(0, 16);
        const endDate = new Date(start + ':00Z'); endDate.setUTCHours(endDate.getUTCHours() + 1);
        const params = new URLSearchParams({ start: start, end: endDate.toISOString().slice(0, 16) });
        window.location.assign(root.dataset.create + '?' + params.toString());
      }
    });
    calendar.render();
  });
})();
