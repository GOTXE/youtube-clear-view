// Phone-mode bottom actions and subscriptions sheet.

(() => {
  let initialized = false;
  let ui = null;
  let callbacks = null;
  let channelsActiveTimer = null;

  function isPhoneMode() {
    return document.documentElement.dataset.mode === 'phone';
  }

  function setNavActive(activeId = null) {
    if (!ui) {
      return;
    }

    [ui.channelsButton, ui.filtersButton, ui.menuButton].forEach(button => {
      if (!button) {
        return;
      }
      button.classList.toggle('is-active', Boolean(activeId) && button.id === activeId);
    });
  }

  function closeChannelSheet() {
    document.body.classList.remove('phone-sidebar-open');
    if (ui && ui.backdrop) {
      ui.backdrop.hidden = true;
    }
  }

  function openChannelSheet() {
    if (!isPhoneMode()) {
      return;
    }
    document.body.classList.add('phone-sidebar-open');
    if (ui && ui.backdrop) {
      ui.backdrop.hidden = false;
    }
    setNavActive(ui && ui.channelsButton ? ui.channelsButton.id : null);
    if (ui && ui.channelsButton) {
      ui.channelsButton.classList.add('is-temporary-active');
    }
    if (channelsActiveTimer) {
      window.clearTimeout(channelsActiveTimer);
    }
    channelsActiveTimer = window.setTimeout(() => {
      if (document.body.classList.contains('phone-sidebar-open')) {
        setNavActive(null);
      }
      if (ui && ui.channelsButton) {
        ui.channelsButton.classList.remove('is-temporary-active');
      }
      channelsActiveTimer = null;
    }, 2000);
  }

  function toggleChannelSheet() {
    if (document.body.classList.contains('phone-sidebar-open')) {
      closeChannelSheet();
    } else {
      openChannelSheet();
    }
  }

  function showPhoneNav() {
    if (!ui || !ui.nav) {
      return;
    }
    ui.nav.hidden = !isPhoneMode();
    if (!isPhoneMode()) {
      closeChannelSheet();
    }
  }

  function initPhoneShell(options) {
    callbacks = options || {};
    ui = {
      nav: document.getElementById('phone-nav'),
      channelsButton: document.getElementById('phone-nav-channels'),
      filtersButton: document.getElementById('phone-nav-filters'),
      menuButton: document.getElementById('phone-nav-menu'),
      backdrop: document.getElementById('channel-sidebar-backdrop'),
      closeButton: document.getElementById('channel-sidebar-close')
    };

    showPhoneNav();

    if (initialized) {
      return {
        openChannelSheet,
        closeChannelSheet,
        toggleChannelSheet,
        sync: showPhoneNav
      };
    }

    if (ui.channelsButton) {
      ui.channelsButton.addEventListener('click', () => {
        toggleChannelSheet();
      });
    }

    if (ui.filtersButton) {
      ui.filtersButton.addEventListener('click', () => {
        closeChannelSheet();
        setNavActive(ui.filtersButton.id);
        if (callbacks && typeof callbacks.openFilters === 'function') {
          callbacks.openFilters();
        }
        window.setTimeout(() => {
          if (!document.body.classList.contains('phone-sidebar-open')) {
            setNavActive(null);
          }
        }, 150);
      });
    }

    if (ui.menuButton) {
      ui.menuButton.addEventListener('click', () => {
        closeChannelSheet();
        setNavActive(ui.menuButton.id);
        if (callbacks && typeof callbacks.openMenu === 'function') {
          callbacks.openMenu();
        }
        window.setTimeout(() => {
          if (!document.body.classList.contains('phone-sidebar-open')) {
            setNavActive(null);
          }
        }, 150);
      });
    }

    if (ui.backdrop) {
      ui.backdrop.addEventListener('click', () => {
        closeChannelSheet();
      });
    }

    if (ui.closeButton) {
      ui.closeButton.addEventListener('click', () => {
        closeChannelSheet();
      });
    }

    window.addEventListener('layout-mode:changed', () => {
      showPhoneNav();
    });

    initialized = true;
    return {
      openChannelSheet,
      closeChannelSheet,
      toggleChannelSheet,
      sync: showPhoneNav
    };
  }

  window.ytcvPhoneShell = {
    initPhoneShell
  };
})();
