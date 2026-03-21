// Shared sidebar toggle for desktop/tablet and TV layouts.

(() => {
  let initialized = false;
  let ui = null;

  const t = key => (
    window.ytcvI18n && typeof window.ytcvI18n.t === 'function'
      ? window.ytcvI18n.t(key)
      : key
  );

  function currentMode() {
    return document.documentElement.dataset.mode || 'desktop_tablet';
  }

  function supportsToggle() {
    const mode = currentMode();
    return mode === 'desktop_tablet' || mode === 'tv';
  }

  function isHidden() {
    return Boolean(ui && ui.layout && ui.layout.classList.contains('sidebar-hidden'));
  }

  function updateControlLabels(hidden) {
    const label = hidden ? t('showSubscriptions') : t('hideSubscriptions');
    const chevron = hidden ? '›' : '‹';

    if (ui.toggle) {
      ui.toggle.hidden = !supportsToggle();
      ui.toggle.setAttribute('aria-label', label);
      ui.toggle.setAttribute('title', label);
      ui.toggle.setAttribute('aria-pressed', String(!hidden));
      const chevronNode = ui.toggle.querySelector('.app-layout__sidebar-toggle-chevron');
      if (chevronNode) {
        chevronNode.textContent = chevron;
      }
    }

    if (ui.tvChannels) {
      ui.tvChannels.setAttribute('aria-label', label);
      ui.tvChannels.setAttribute('title', label);
      ui.tvChannels.setAttribute('aria-pressed', String(!hidden));
      const chevronNode = ui.tvChannels.querySelector('.tv-action-bar__sidebar-chevron');
      if (chevronNode) {
        chevronNode.textContent = chevron;
      }
    }
  }

  function notifyResize() {
    window.setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 320);
  }

  function applyHidden(hidden, options = {}) {
    if (!ui || !ui.layout) {
      return;
    }

    const active = supportsToggle();
    const nextHidden = Boolean(active && hidden);
    ui.layout.classList.toggle('sidebar-hidden', nextHidden);
    updateControlLabels(nextHidden);

    notifyResize();
  }

  function toggle() {
    applyHidden(!isHidden());
  }

  function sync() {
    if (!ui || !ui.layout) {
      return;
    }

    if (!supportsToggle()) {
      ui.layout.classList.remove('sidebar-hidden');
      updateControlLabels(false);
      if (ui.toggle) {
        ui.toggle.hidden = true;
      }
      return;
    }

    applyHidden(true);
  }

  function initSidebarShell() {
    ui = {
      layout: document.querySelector('.app-layout'),
      tvChannels: document.getElementById('tv-action-channels')
    };

    sync();

    if (initialized) {
      return { toggle, sync, isHidden };
    }

    window.addEventListener('layout-mode:changed', sync);
    initialized = true;
    return { toggle, sync, isHidden };
  }

  window.ytcvSidebarShell = {
    initSidebarShell,
    toggle,
    sync,
    isHidden
  };
})();
