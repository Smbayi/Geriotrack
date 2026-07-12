/**
 * GérioTrack — menu latéral mobile + fermeture au clic
 */
(function () {
  if (document.querySelector('.bottom-nav')) return;

  var sidebar = document.querySelector('body > .sidebar');
  var topbar = document.querySelector('.topbar');
  if (!sidebar || !topbar) return;

  if (document.querySelector('.menu-toggle')) return;

  var backdrop = document.createElement('div');
  backdrop.className = 'sidebar-backdrop';
  backdrop.setAttribute('aria-hidden', 'true');
  document.body.appendChild(backdrop);

  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'menu-toggle';
  btn.setAttribute('aria-label', 'Ouvrir le menu');
  btn.innerHTML =
    '<svg viewBox="0 0 24 24"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>';

  var first = topbar.firstElementChild;
  if (first) first.insertBefore(btn, first.firstChild);
  else topbar.prepend(btn);

  function closeMenu() {
    document.body.classList.remove('sidebar-open');
    btn.setAttribute('aria-label', 'Ouvrir le menu');
  }

  function openMenu() {
    document.body.classList.add('sidebar-open');
    btn.setAttribute('aria-label', 'Fermer le menu');
  }

  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    if (document.body.classList.contains('sidebar-open')) closeMenu();
    else openMenu();
  });

  backdrop.addEventListener('click', closeMenu);

  sidebar.querySelectorAll('.nav-item').forEach(function (link) {
    link.addEventListener('click', function () {
      if (window.innerWidth <= 768) closeMenu();
    });
  });

  window.addEventListener('resize', function () {
    if (window.innerWidth > 768) closeMenu();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeMenu();
  });
})();
