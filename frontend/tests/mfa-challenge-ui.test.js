import { beforeEach, describe, expect, it, vi } from 'vitest';

function translate(key, vars = {}) {
  return key.replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ''));
}

describe('mfa challenge UI', () => {
  beforeEach(() => {
    vi.resetModules();
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
    window.ytcvI18n = { t: translate };
    window.ytcvPasskeys = {
      isSupported: () => false
    };
  });

  it('opens an MFA challenge from bootstrap and completes it with a TOTP code', async () => {
    const verifyMfaChallengeMock = vi.fn(async () => ({
      ok: true,
      data: {
        authenticated: true,
        user_id: 1,
        username: 'alice@gmail.com',
        display_name: 'Alice',
        email: 'alice@gmail.com',
        auth_provider: 'google',
        google_avatar_url: null,
        theme_preference: 'dark',
        google_auth_status: 'active',
        totp_enabled: true
      }
    }));

    window.APIClient = class APIClient {
      async getAuthProvider() {
        return { ok: true, data: { auth_mode: 'google', google_login_url: '/api/auth/google' } };
      }

      async getCurrentUser() {
        return {
          ok: true,
          data: {
            authenticated: false,
            mfa_required: true,
            user_id: 1,
            display_name: 'Alice',
            email: 'alice@gmail.com',
            available_methods: ['totp', 'recovery_code']
          }
        };
      }

      async getSwitchableAccounts() {
        return { ok: true, data: { current_user_id: null, accounts: [] } };
      }

      async verifyMfaChallenge(code, method) {
        return verifyMfaChallengeMock(code, method);
      }

      async logout() {
        return { ok: true };
      }
    };

    await import('../js/auth.js');
    await window.initAuth();
    await new Promise(resolve => setTimeout(resolve, 0));

    const modal = document.getElementById('mfa-challenge-modal');
    expect(modal).not.toBeNull();
    expect(modal.hidden).toBe(false);

    const input = document.getElementById('mfa-challenge-code');
    input.value = '123456';
    document.getElementById('mfa-challenge-verify-button').click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(verifyMfaChallengeMock).toHaveBeenCalledWith('123456', 'totp');
    expect(document.getElementById('current-user-name').textContent).toBe('Alice');
  });

  it('opens an MFA challenge after account switch and completes it with a recovery code', async () => {
    const verifyMfaChallengeMock = vi.fn(async () => ({
      ok: true,
      data: {
        authenticated: true,
        user_id: 2,
        username: 'bob@gmail.com',
        display_name: 'Bob',
        email: 'bob@gmail.com',
        auth_provider: 'google',
        google_avatar_url: null,
        theme_preference: 'dark',
        google_auth_status: 'active',
        totp_enabled: true
      }
    }));

    window.APIClient = class APIClient {
      async getAuthProvider() {
        return { ok: true, data: { auth_mode: 'google', google_login_url: '/api/auth/google' } };
      }

      async getCurrentUser() {
        return {
          ok: true,
          data: {
            authenticated: true,
            user_id: 1,
            username: 'alice@gmail.com',
            display_name: 'Alice',
            email: 'alice@gmail.com',
            auth_provider: 'google',
            google_avatar_url: null,
            theme_preference: 'dark',
            google_auth_status: 'active',
            totp_enabled: false
          }
        };
      }

      async getSwitchableAccounts() {
        return {
          ok: true,
          data: {
            current_user_id: 1,
            accounts: [
              { id: 2, display_name: 'Bob', username: 'bob@gmail.com', email: 'bob@gmail.com', is_current: false }
            ]
          }
        };
      }

      async switchAccount() {
        return {
          ok: true,
          data: {
            authenticated: false,
            mfa_required: true,
            user_id: 2,
            display_name: 'Bob',
            email: 'bob@gmail.com',
            available_methods: ['totp', 'recovery_code']
          }
        };
      }

      async verifyMfaChallenge(code, method) {
        return verifyMfaChallengeMock(code, method);
      }

      async logout() {
        return { ok: true };
      }
    };

    await import('../js/auth.js');
    await window.initAuth();
    await new Promise(resolve => setTimeout(resolve, 0));

    document.getElementById('switch-google-account-button').click();
    await new Promise(resolve => setTimeout(resolve, 0));
    document.querySelector('#account-switcher-list button').click();
    await new Promise(resolve => setTimeout(resolve, 0));

    const input = document.getElementById('mfa-challenge-code');
    input.value = 'RECOVERY-1';
    document.getElementById('mfa-challenge-recovery-button').click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(verifyMfaChallengeMock).toHaveBeenCalledWith('RECOVERY-1', 'recovery_code');
    expect(document.getElementById('current-user-name').textContent).toBe('Bob');
  });
});
