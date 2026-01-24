// Light/dark theme switcher with persistence.

(() => {
  const STORAGE_KEY = 'ytcv_theme';
  const THEMES = ['light', 'dark'];

  let currentTheme = 'light';

  const ui = {
    toggleButton: document.getElementById('theme-toggle'),
    appRoot: document.getElementById('app')
  };

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
    const safeTheme = THEMES.includes(theme) ? theme : 'light';
    currentTheme = safeTheme;

    document.documentElement.setAttribute('data-theme', safeTheme);
    if (ui.appRoot) {
      ui.appRoot.setAttribute('data-theme', safeTheme);
    }

    if (ui.toggleButton) {
      const label = safeTheme === 'dark' ? 'Dark' : 'Light';
      const icon = safeTheme === 'dark' ? '🌙' : '☀️';
      ui.toggleButton.setAttribute('aria-pressed', safeTheme === 'dark');
      const labelSpan = ui.toggleButton.querySelector('.button__label');
      const text = `Theme: ${label} ${icon}`;
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
    let theme = 'light';

    if (typeof window.getCurrentUser === 'function') {
      const user = window.getCurrentUser();
      if (user && user.theme_preference) {
        theme = user.theme_preference;
      }
    }

    if (!THEMES.includes(theme)) {
      const stored = readStoredTheme();
      theme = THEMES.includes(stored) ? stored : 'light';
    }

    applyTheme(theme);

    if (ui.toggleButton) {
      ui.toggleButton.addEventListener('click', () => {
        toggleTheme();
      });
    }

    window.addEventListener('auth:changed', event => {
      const user = event.detail ? event.detail.user : null;
      if (user && user.theme_preference) {
        applyTheme(user.theme_preference);
      }
    });
  }

  window.initTheme = initTheme;
  window.toggleTheme = toggleTheme;
  window.setTheme = setTheme;
  window.getCurrentTheme = getCurrentTheme;
})();
