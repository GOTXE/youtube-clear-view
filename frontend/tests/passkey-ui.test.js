import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('passkey auth UI', () => {
  let authenticateWithPasskeyMock;
  let registerPasskeyMock;
  let getPasskeysMock;

  beforeEach(() => {
    vi.resetModules();
    authenticateWithPasskeyMock = vi.fn(async () => ({
      ok: true,
      data: {
        authenticated: true,
        user_id: 3,
        username: 'carol@gmail.com',
        display_name: 'Carol',
        email: 'carol@gmail.com',
        auth_provider: 'google',
        google_avatar_url: null,
        theme_preference: 'dark'
      }
    }));
    registerPasskeyMock = vi.fn(async () => ({ ok: true }));
    getPasskeysMock = vi.fn(async () => ({
      ok: true,
      data: {
        passkeys: [
          {
            id: 11,
            label: 'Laptop',
            credential_id: 'credential-1'
          }
        ]
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
      isSupported: () => true,
      authenticateWithPasskey: authenticateWithPasskeyMock,
      registerPasskey: registerPasskeyMock
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

      async getPasskeys() {
        return getPasskeysMock();
      }

      async deletePasskey() {
        return { ok: true };
      }

      async logout() {
        return { ok: true };
      }
    };
  });

  it('shows a passkey sign-in action when unauthenticated and signs in successfully', async () => {
    await import('../js/auth.js');
    await window.initAuth();

    const button = document.getElementById('passkey-login-button');
    expect(button).not.toBeNull();
    expect(button.hidden).toBe(false);

    button.click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(authenticateWithPasskeyMock).toHaveBeenCalled();
    expect(document.getElementById('current-user-name').textContent).toBe('Carol');
  });

  it('opens the passkey management modal and lists registered passkeys', async () => {
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
            username: 'alice@gmail.com',
            display_name: 'Alice',
            email: 'alice@gmail.com',
            auth_provider: 'google',
            google_avatar_url: null,
            theme_preference: 'dark'
          }
        };
      }

      async getSwitchableAccounts() {
        return { ok: true, data: { current_user_id: 1, accounts: [] } };
      }

      async getPasskeys() {
        return getPasskeysMock();
      }

      async deletePasskey() {
        return { ok: true };
      }

      async logout() {
        return { ok: true };
      }
    };

    await import('../js/auth.js');
    await window.initAuth();
    await new Promise(resolve => setTimeout(resolve, 0));

    const button = document.getElementById('manage-passkeys-button');
    expect(button).not.toBeNull();
    expect(button.hidden).toBe(false);

    button.click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(getPasskeysMock).toHaveBeenCalled();
    const modal = document.getElementById('passkey-modal');
    expect(modal).not.toBeNull();
    expect(modal.hidden).toBe(false);
    expect(modal.textContent).toContain('Laptop');
  });
});
