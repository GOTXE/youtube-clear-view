// Light/dark theme switcher with persistence.

(() => {
  const STORAGE_KEY = 'ytcv_theme';
  const THEMES = ['light', 'dark'];
  const DEFAULT_THEME = 'dark';

  let currentTheme = DEFAULT_THEME;

  const ui = {
    toggleButton: document.getElementById('theme-toggle'),
    appRoot: document.getElementById('app')
  };

  const t = (key, vars) => (
    window.ytcvI18n && typeof window.ytcvI18n.t === 'function'
      ? window.ytcvI18n.t(key, vars)
      : key
  );

  function getApiClient() {
    if (!window.APIClient || !window.APP_CONFIG) {
      return null;
    }

    if (!window.appApiClient) {
      window.appApiClient = new window.APIClient(
        window.APP_CONFIG.API_BASE_URL,
        window.APP_CONFIG.REQUEST_TIMEOUT
      );
    }

    return window.appApiClient;
  }

  function readStoredTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return null;
    }
  }

  function saveTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (error) {
      return;
    }
  }

  function applyTheme(theme) {
    const safeTheme = THEMES.includes(theme) ? theme : DEFAULT_THEME;
    currentTheme = safeTheme;

    document.documentElement.setAttribute('data-theme', safeTheme);
    if (ui.appRoot) {
      ui.appRoot.setAttribute('data-theme', safeTheme);
    }

    if (ui.toggleButton) {
      const nextTheme = safeTheme === 'dark' ? 'light' : 'dark';
      const icon = nextTheme === 'dark' ? '🌙' : '☀️';
      const modeKey = nextTheme === 'dark' ? 'themeDark' : 'themeLight';
      const label = t(modeKey);
      ui.toggleButton.setAttribute('aria-pressed', safeTheme === 'dark');
      const labelSpan = ui.toggleButton.querySelector('.button__label');
      const text = t('themeLabel', { mode: label, icon });
      if (labelSpan) {
        labelSpan.textContent = text;
      } else {
        ui.toggleButton.textContent = text;
      }
    }
  }

  async function persistTheme(theme) {
    saveTheme(theme);

    if (typeof window.isAuthenticated === 'function' && window.isAuthenticated()) {
      const api = getApiClient();
      if (api) {
        await api.updateProfile({ theme_preference: theme });
      }
    }
  }

  function getCurrentTheme() {
    return currentTheme;
  }

  function setTheme(theme) {
    applyTheme(theme);
    persistTheme(theme);
  }

  function toggleTheme() {
    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
  }

  function initTheme() {
    applyTheme(DEFAULT_THEME);

    if (ui.toggleButton) {
      ui.toggleButton.addEventListener('click', () => {
        toggleTheme();
      });
    }

    window.addEventListener('auth:changed', event => {
      const user = event.detail ? event.detail.user : null;
      if (!user) {
        applyTheme(DEFAULT_THEME);
      }
    });
  }

  window.initTheme = initTheme;
  window.toggleTheme = toggleTheme;
  window.setTheme = setTheme;
  window.getCurrentTheme = getCurrentTheme;
})();
