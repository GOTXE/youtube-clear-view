import { readFileSync } from 'node:fs';
import path from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('menu organization', () => {
  beforeEach(() => {
    vi.resetModules();

    document.body.innerHTML = `
      <div id="app"></div>
      <div class="session-info">
        <a id="current-user" class="session-info__label" href="#"></a>
        <span id="current-user-name" class="session-info__name"></span>
      </div>
      <div id="menu-account-actions">
        <button id="google-login-button" class="menu-item" type="button" hidden></button>
        <button id="import-subscriptions-button" class="menu-item" type="button" hidden></button>
        <button id="logout-button" class="menu-item" type="button" hidden></button>
      </div>
      <div id="menu-system-actions"></div>
      <div class="user-summary" aria-live="polite"></div>
    `;

    window.APP_CONFIG = {
      API_BASE_URL: '',
      REQUEST_TIMEOUT: 5000
    };
    window.appApiClient = null;
    window.ytcvI18n = {
      t: key => key
    };
    window.ytcvPasskeys = {
      isSupported: () => true,
      authenticateWithPasskey: vi.fn(),
      registerPasskey: vi.fn()
    };

    window.APIClient = class APIClient {
      async getAuthProvider() {
        return {
          ok: true,
          data: { auth_mode: 'google', google_login_url: '/api/auth/google' }
        };
      }

      async getCurrentUser() {
        return {
          ok: true,
          data: {
            authenticated: true,
            user_id: 1,
            username: 'admin',
            display_name: 'Admin',
            email: 'admin@example.com',
            auth_provider: 'google',
            is_admin: true,
            theme_preference: 'dark'
          }
        };
      }

      async getSwitchableAccounts() {
        return { ok: true, data: { current_user_id: 1, accounts: [] } };
      }

      async logout() {
        return { ok: true };
      }
    };
  });

  it('keeps account actions separate from system actions', async () => {
    await import('../js/auth.js');
    await window.initAuth();
    await new Promise(resolve => setTimeout(resolve, 0));

    const accountActions = document.getElementById('menu-account-actions');
    const systemActions = document.getElementById('menu-system-actions');

    expect(accountActions.querySelector('#manage-passkeys-button')).not.toBeNull();
    expect(accountActions.querySelector('#manage-mfa-button')).not.toBeNull();
    expect(accountActions.querySelector('#switch-google-account-button')).not.toBeNull();
    expect(systemActions.querySelector('#manage-admin-button')).not.toBeNull();
  });

  it('keeps menu section headings available for i18n in both locales', () => {
    const english = JSON.parse(readFileSync(path.resolve(process.cwd(), 'i18n/en.json'), 'utf8'));
    const spanish = JSON.parse(readFileSync(path.resolve(process.cwd(), 'i18n/es.json'), 'utf8'));

    expect(english.menuSectionAccount).toBeTruthy();
    expect(english.menuSectionViewing).toBeTruthy();
    expect(english.menuSectionSystem).toBeTruthy();
    expect(spanish.menuSectionAccount).toBeTruthy();
    expect(spanish.menuSectionViewing).toBeTruthy();
    expect(spanish.menuSectionSystem).toBeTruthy();
  });

  it('renders section hooks for highlighted menu cards', () => {
    const html = readFileSync(path.resolve(process.cwd(), 'index.html'), 'utf8');

    expect(html).toContain('id="menu-heading-account"');
    expect(html).toContain('id="menu-heading-viewing"');
    expect(html).toContain('id="menu-heading-system"');
    expect(html).toContain('menu-panel__section--account');
    expect(html).toContain('menu-panel__section--viewing');
    expect(html).toContain('menu-panel__section--system');
  });
});
