(function initTopNav() {
  const nav = document.querySelector('.top-nav');
  const toggleBtn = document.getElementById('navMenuBtn');
  const linksEl = document.getElementById('topNavLinks');

  if (!nav || !toggleBtn || !linksEl) {
    return;
  }

  function isMobileLayout() {
    return window.matchMedia('(max-width: 768px)').matches;
  }

  function setNavOpen(isOpen) {
    const shouldOpen = isOpen && isMobileLayout();
    nav.classList.toggle('is-open', shouldOpen);
    toggleBtn.setAttribute('aria-expanded', String(shouldOpen));
  }

  toggleBtn.addEventListener('click', () => {
    const nextOpen = !nav.classList.contains('is-open');
    setNavOpen(nextOpen);
  });

  linksEl.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => setNavOpen(false));
  });

  window.addEventListener('resize', () => {
    if (!isMobileLayout()) {
      setNavOpen(false);
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      setNavOpen(false);
    }
  });
})();
