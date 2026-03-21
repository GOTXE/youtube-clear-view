// TV-mode action rail and focus helpers.

(() => {
  let initialized = false;
  let ui = null;
  let callbacks = null;

  function isTvMode() {
    return document.documentElement.dataset.mode === 'tv';
  }

  function sync() {
    if (!ui || !ui.bar) {
      return;
    }
    ui.bar.hidden = !isTvMode();
  }

  function initTvShell(options) {
    callbacks = options || {};
    ui = {
      bar: document.getElementById('tv-action-bar'),
      channels: document.getElementById('tv-action-channels'),
      filters: document.getElementById('tv-action-filters'),
      refresh: document.getElementById('tv-action-refresh'),
      display: document.getElementById('tv-action-display')
    };

    sync();

    if (initialized) {
      return { sync };
    }

    if (ui.channels) {
      ui.channels.addEventListener('click', () => {
        if (window.ytcvSidebarShell && typeof window.ytcvSidebarShell.toggle === 'function') {
          window.ytcvSidebarShell.toggle();
        }
      });
    }

    if (ui.filters) {
      ui.filters.addEventListener('click', () => {
        if (callbacks && typeof callbacks.openFilters === 'function') {
          callbacks.openFilters();
        }
      });
    }

    if (ui.refresh) {
      ui.refresh.addEventListener('click', () => {
        if (callbacks && typeof callbacks.triggerRefresh === 'function') {
          callbacks.triggerRefresh();
        }
      });
    }

    if (ui.display) {
      ui.display.addEventListener('click', () => {
        if (callbacks && typeof callbacks.openDisplaySetup === 'function') {
          callbacks.openDisplaySetup();
        }
      });
    }

    window.addEventListener('layout-mode:changed', sync);
    initialized = true;
    return { sync };
  }

  window.ytcvTvShell = {
    initTvShell
  };
})();
