// Desktop/tablet shell behavior for the floating filter panel.

(() => {
  const STORAGE_KEY = 'ytcv_desktop_filters_docked';
  const MIN_DOCK_WIDTH = 1200;

  let initialized = false;
  let ui = null;

  const t = key => (
    window.ytcvI18n && typeof window.ytcvI18n.t === 'function'
      ? window.ytcvI18n.t(key)
      : key
  );

  function isDesktopTabletMode() {
    return document.documentElement.dataset.mode === 'desktop_tablet';
  }

  function isWideDesktop() {
    return (window.innerWidth || 0) >= MIN_DOCK_WIDTH;
  }

  function safeStorageGet() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return null;
    }
  }

  function safeStorageSet(value) {
    try {
      localStorage.setItem(STORAGE_KEY, value ? 'true' : 'false');
    } catch (error) {
      return;
    }
  }

  function ensureDockButton() {
    if (!ui || !ui.header) {
      return;
    }

    let controls = ui.header.querySelector('.filter-panel__header-controls');
    if (!controls) {
      controls = document.createElement('div');
      controls.className = 'filter-panel__header-controls';
      ui.header.appendChild(controls);
    }

    if (ui.closeButton && ui.closeButton.parentElement !== controls) {
      controls.appendChild(ui.closeButton);
    }

    let dockButton = controls.querySelector('#filters-dock-toggle');
    if (!dockButton) {
      dockButton = document.createElement('button');
      dockButton.id = 'filters-dock-toggle';
      dockButton.className = 'filter-panel__dock';
      dockButton.type = 'button';
      controls.insertBefore(dockButton, ui.closeButton || null);
    }

    ui.dockButton = dockButton;
  }

  function resolveDockedPreference() {
    const stored = safeStorageGet();
    if (stored === 'true') {
      return true;
    }
    if (stored === 'false') {
      return false;
    }
    return false;
  }

  function renderDockButton(docked) {
    if (!ui || !ui.dockButton) {
      return;
    }

    ui.dockButton.hidden = !isDesktopTabletMode();
    ui.dockButton.setAttribute('aria-pressed', docked ? 'true' : 'false');
    ui.dockButton.textContent = docked ? t('undockFilters') : t('dockFilters');
    ui.dockButton.setAttribute('aria-label', docked ? t('undockFilters') : t('dockFilters'));
  }

  function applyDockState(docked, options = {}) {
    if (!ui || !ui.panel) {
      return;
    }

    const { persist = true } = options;
    const active = isDesktopTabletMode();
    const effectiveDocked = Boolean(active && docked && isWideDesktop());

    ui.panel.classList.toggle('is-docked', effectiveDocked);
    document.body.classList.toggle('desktop-filters-docked', effectiveDocked);

    if (effectiveDocked) {
      ui.panel.hidden = false;
      ui.panel.style.left = 'auto';
      ui.panel.style.right = '80px';
      ui.panel.style.top = '140px';
    } else if (!active) {
      ui.panel.hidden = true;
    }

    renderDockButton(effectiveDocked);

    if (persist) {
      safeStorageSet(docked);
    }
  }

  function toggleDock() {
    const nextDocked = !ui.panel.classList.contains('is-docked');
    applyDockState(nextDocked);
  }

  function sync() {
    if (!ui || !ui.panel) {
      return;
    }

    ensureDockButton();
    applyDockState(resolveDockedPreference(), { persist: false });
  }

  function initDesktopShell() {
    ui = {
      panel: document.getElementById('filter-panel'),
      header: document.querySelector('.filter-panel__header'),
      closeButton: document.getElementById('filters-close'),
      dockButton: document.getElementById('filters-dock-toggle')
    };

    if (!ui.panel || !ui.header) {
      return { sync };
    }

    ensureDockButton();
    sync();

    if (initialized) {
      return { sync };
    }

    if (ui.dockButton) {
      ui.dockButton.addEventListener('click', () => {
        toggleDock();
      });
    }

    window.addEventListener('layout-mode:changed', sync);
    window.addEventListener('resize', sync);

    initialized = true;
    return { sync };
  }

  window.ytcvDesktopShell = {
    initDesktopShell
  };
})();
