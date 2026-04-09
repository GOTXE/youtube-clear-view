// Phone-mode bottom actions and subscriptions sheet.

(() => {
  let initialized = false;
  let ui = null;
  let callbacks = null;
  let activeView = 'home';
  const VALID_VIEWS = new Set(['home', 'channels', 'categories', 'settings']);

  function isPhoneMode() {
    return document.documentElement.dataset.mode === 'phone';
  }

  function normalizeView(view) {
    return VALID_VIEWS.has(view) ? view : 'home';
  }

  function setNavActive(view = 'home') {
    if (!ui) {
      return;
    }

    [ui.homeButton, ui.channelsButton, ui.categoriesButton, ui.settingsButton].forEach(button => {
      if (!button) {
        return;
      }
      const isActive = button.dataset.phoneView === view;
      button.classList.toggle('is-active', isActive);
      button.setAttribute('aria-current', isActive ? 'page' : 'false');
    });
  }

  function closeChannelSheet() {
    setActiveView('home');
  }

  function notifyViewChange(view, source = 'programmatic') {
    if (callbacks && typeof callbacks.onViewChange === 'function') {
      callbacks.onViewChange(view, { source });
    }
  }

  function setActiveView(view, options = {}) {
    const normalizedView = normalizeView(view);
    const { pushHistory = false, source = 'programmatic' } = options;

    activeView = normalizedView;
    setNavActive(normalizedView);
    notifyViewChange(normalizedView, source);

    if (pushHistory && isPhoneMode() && window.history && typeof window.history.pushState === 'function') {
      window.history.pushState({ ytcvPhoneView: normalizedView }, '', window.location.href);
    }

    if (ui && ui.backdrop) {
      ui.backdrop.hidden = true;
    }
  }

  function openChannelSheet() {
    if (!isPhoneMode()) {
      return;
    }
    setActiveView('channels');
  }

  function toggleChannelSheet() {
    setActiveView(activeView === 'channels' ? 'home' : 'channels');
  }

  function showPhoneNav() {
    if (!ui || !ui.nav) {
      return;
    }
    ui.nav.hidden = !isPhoneMode();
    if (!isPhoneMode()) {
      activeView = 'home';
      setNavActive('home');
      notifyViewChange('home', 'layout');
    }
  }

  function initPhoneShell(options) {
    callbacks = options || {};
    ui = {
      nav: document.getElementById('phone-nav'),
      homeButton: document.getElementById('phone-nav-home'),
      channelsButton: document.getElementById('phone-nav-channels'),
      categoriesButton: document.getElementById('phone-nav-categories'),
      settingsButton: document.getElementById('phone-nav-settings'),
      backdrop: document.getElementById('channel-sidebar-backdrop'),
      closeButton: document.getElementById('channel-sidebar-close')
    };

    [
      ui.homeButton,
      ui.channelsButton,
      ui.categoriesButton,
      ui.settingsButton
    ].forEach(button => {
      if (button) {
        button.dataset.phoneView = button.id.replace('phone-nav-', '');
      }
    });

    showPhoneNav();

    if (initialized) {
      return {
        setActiveView,
        getActiveView: () => activeView,
        openChannelSheet,
        closeChannelSheet,
        toggleChannelSheet,
        sync: showPhoneNav
      };
    }

    if (ui.homeButton) {
      ui.homeButton.addEventListener('click', () => {
        setActiveView('home', { pushHistory: true, source: 'user' });
      });
    }

    if (ui.channelsButton) {
      ui.channelsButton.addEventListener('click', () => {
        setActiveView('channels', { pushHistory: true, source: 'user' });
      });
    }

    if (ui.categoriesButton) {
      ui.categoriesButton.addEventListener('click', () => {
        setActiveView('categories', { pushHistory: true, source: 'user' });
      });
    }

    if (ui.settingsButton) {
      ui.settingsButton.addEventListener('click', () => {
        setActiveView('settings', { pushHistory: true, source: 'user' });
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

    window.addEventListener('popstate', event => {
      const nextView = event.state && event.state.ytcvPhoneView
        ? normalizeView(event.state.ytcvPhoneView)
        : 'home';

      if (!isPhoneMode()) {
        return;
      }

      setActiveView(nextView, { pushHistory: false, source: 'history' });
    });

    window.addEventListener('layout-mode:changed', () => {
      showPhoneNav();
    });

    setActiveView(
      window.history && window.history.state && window.history.state.ytcvPhoneView
        ? window.history.state.ytcvPhoneView
        : 'home',
      { pushHistory: false, source: 'init' }
    );

    initialized = true;
    return {
      setActiveView,
      getActiveView: () => activeView,
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
