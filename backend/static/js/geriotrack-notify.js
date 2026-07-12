/* GérioTrack — cloche notifications */
(function () {
  function fmtTime(iso) {
    try {
      return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return '—';
    }
  }

  function iconFor(type) {
    if (type === 'fall') return '⚠';
    if (type === 'call') return '📞';
    if (type === 'message') return '✉';
    return '•';
  }

  function linkFor(n) {
    if (n.link) return n.link;
    if (n.type === 'fall' && n.fall_event_id) return '/alertes/?chute=' + n.fall_event_id;
    if (n.message_id) return '/alertes/?msg=' + n.message_id;
    return '/alertes/?notif=' + n.id;
  }

  async function pollNotifications() {
    const badges = document.querySelectorAll('[data-notif-badge]');
    const panels = document.querySelectorAll('[data-notif-panel]');
    try {
      const res = await fetch('/api/notifications/');
      if (!res.ok) return;
      const data = await res.json();
      const unread = data.unread || 0;
      badges.forEach((b) => {
        b.textContent = unread > 99 ? '99+' : String(unread);
        b.style.display = unread > 0 ? 'flex' : 'none';
      });
      panels.forEach((panel) => {
        const list = panel.querySelector('[data-notif-list]');
        if (!list) return;
        const items = data.notifications || [];
        if (!items.length) {
          list.innerHTML = '<div class="notif-empty">Aucune notification</div>';
          return;
        }
        list.innerHTML = items
          .slice(0, 12)
          .map(
            (n) => `<a class="notif-item ${n.read ? '' : 'unread'}" href="${linkFor(n)}" data-notif-id="${n.id}" style="text-decoration:none;color:inherit;display:flex">
          <div class="notif-ico">${iconFor(n.type)}</div>
          <div class="notif-body">
            <div class="notif-title">${n.title}</div>
            <div class="notif-sub">${fmtTime(n.created_at)} · ${n.nom || n.patient_id || ''}</div>
          </div>
        </a>`
          )
          .join('');

        list.querySelectorAll('a.notif-item').forEach((a) => {
          a.addEventListener('click', (e) => {
            e.stopPropagation();
            const id = a.getAttribute('data-notif-id');
            if (id) {
              fetch('/api/notifications/read/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: Number(id) }),
              });
            }
            // laisser la navigation href se faire
          });
        });
      });
    } catch (e) {}
  }

  function initBell(btn) {
    if (!btn || btn.dataset.notifInit) return;
    btn.dataset.notifInit = '1';
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const wrap = btn.closest('[data-notif-wrap]');
      const panel = wrap && wrap.querySelector('[data-notif-panel]');
      if (!panel) return;
      panel.classList.toggle('open');
    });
  }

  document.addEventListener('click', () => {
    document.querySelectorAll('[data-notif-panel].open').forEach((p) => p.classList.remove('open'));
  });

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-notif-btn]').forEach(initBell);
    pollNotifications();
    setInterval(pollNotifications, 3000);
  });
})();
