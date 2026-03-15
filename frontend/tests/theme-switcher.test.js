import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('theme switcher', () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
    document.body.innerHTML = `
      <div id="app"></div>
      <button id="theme-toggle" type="button">
        <span class="button__label"></span>
      </button>
    `;
    window.APP_CONFIG = {
      API_BASE_URL: 'http://localhost:5550',
      REQUEST_TIMEOUT: 5000
    };
    window.ytcvI18n = {
      t: (key, vars) => {
        if (key === 'themeDark') return 'Dark';
        if (key === 'themeLight') return 'Light';
        if (key === 'themeLabel') return `${vars.icon} ${vars.mode}`;
        return key;
      }
    };
    window.APIClient = class APIClient {
      async updateProfile() {
        return {};
      }
    };
    window.isAuthenticated = () => false;
    window.getCurrentUser = () => null;
  });

  afterEach(() => {
    delete window.APP_CONFIG;
    delete window.ytcvI18n;
    delete window.APIClient;
    delete window.appApiClient;
    delete window.isAuthenticated;
    delete window.getCurrentUser;
    delete window.initTheme;
    delete window.toggleTheme;
    delete window.setTheme;
    delete window.getCurrentTheme;
  });

  it('initializes with stored theme and updates DOM state', async () => {
    localStorage.setItem('ytcv_theme', 'light');
    await import('../js/theme-switcher.js');

    window.initTheme();

    expect(window.getCurrentTheme()).toBe('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(document.getElementById('app').getAttribute('data-theme')).toBe('light');
    expect(document.querySelector('.button__label').textContent).toBe('☀️ Light');
  });

  it('toggles theme and persists the new value locally', async () => {
    await import('../js/theme-switcher.js');

    window.initTheme();
    await window.toggleTheme();

    expect(window.getCurrentTheme()).toBe('light');
    expect(localStorage.getItem('ytcv_theme')).toBe('light');
    expect(document.getElementById('theme-toggle').getAttribute('aria-pressed')).toBe('false');
  });
});
