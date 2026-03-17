import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('fallback login UI', () => {
  let fallbackLoginMock;

  beforeEach(() => {
    vi.resetModules();
    fallbackLoginMock = vi.fn(async () => ({
      ok: true,
      data: {
        authenticated: true,
        user_id: 5,
        username: 'fallback@example.com',
        display_name: 'Fallback User',
        email: 'fallback@example.com',
        auth_provider: 'google',
        google_avatar_url: null,
        theme_preference: 'dark'
      }
    }));

    document.body.innerHTML = `
      <div id="app"></div>
      <div class="session-info">
        <a id="current-user" class="session-info__label" href="#"></a>
        <span id="current-user-name" class="session-info__name"></span>
      </div>
      <div class="header-actions">
        <button id="google-login-button" class="menu-item" type="button" hidden></button>
        <button id="logout-button" class="menu-item" type="button" hidden></button>
        <div class="user-summary" aria-live="polite"></div>
      </div>
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
      isSupported: () => true
    };

    window.APIClient = class APIClient {
      async getAuthProvider() {
        return {
          ok: true,
          data: { auth_mode: 'google', google_login_url: '/api/auth/google' }
        };
      }

      async getCurrentUser() {
        return { ok: true, data: { authenticated: false } };
      }

      async getSwitchableAccounts() {
        return { ok: true, data: { current_user_id: null, accounts: [] } };
      }

      async fallbackLogin(identifier, code, method) {
        return fallbackLoginMock(identifier, code, method);
      }

      async logout() {
        return { ok: true };
      }
    };
  });

  it('opens fallback login and signs in with a recovery code', async () => {
    await import('../js/auth.js');
    await window.initAuth();

    const button = document.getElementById('fallback-login-button');
    expect(button).not.toBeNull();
    expect(button.hidden).toBe(false);

    button.click();
    await new Promise(resolve => setTimeout(resolve, 0));

    const modal = document.getElementById('fallback-login-modal');
    expect(modal).not.toBeNull();
    expect(modal.hidden).toBe(false);

    document.getElementById('fallback-login-identifier').value = 'fallback@example.com';
    document.getElementById('fallback-login-code').value = 'RECOVERY-1234';
    document.getElementById('fallback-login-recovery-button').click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(fallbackLoginMock).toHaveBeenCalledWith('fallback@example.com', 'RECOVERY-1234', 'recovery_code');
    expect(document.getElementById('current-user-name').textContent).toBe('Fallback User');
    expect(document.getElementById('fallback-login-modal').hidden).toBe(true);
  });
});
