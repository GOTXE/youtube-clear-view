import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('pairing auth UI', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.useFakeTimers();

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
    window.ytcvI18n = { t: key => key };
    window.ytcvPasskeys = {
      isSupported: () => true
    };
  });

  afterEach(() => {
    vi.useRealTimers();
    delete window.APP_CONFIG;
    delete window.appApiClient;
    delete window.ytcvI18n;
    delete window.ytcvPasskeys;
    delete window.APIClient;
    delete window.initAuth;
    delete window.getCurrentUser;
    delete window.isAuthenticated;
    delete window.logout;
    delete window.switchUser;
    delete window.setAuthStatus;
    delete window.signInWithPasskey;
  });

  it('starts a pairing flow and completes sign-in after approval is claimed', async () => {
    const startPairingMock = vi.fn(async () => ({
      ok: true,
      data: {
        status: 'pending',
        public_id: 'public-123',
        pairing_code: 'ABCD-EFGH'
      }
    }));
    const claimPairingMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        data: {
          status: 'pending',
          public_id: 'public-123',
          pairing_code: 'ABCD-EFGH'
        }
      })
      .mockResolvedValueOnce({
        ok: true,
        data: {
          authenticated: true,
          user_id: 3,
          username: 'carol@gmail.com',
          display_name: 'Carol',
          email: 'carol@gmail.com',
          auth_provider: 'google',
          google_avatar_url: null,
          theme_preference: 'dark',
          pairing_claimed: true
        }
      });

    window.APIClient = class APIClient {
      async getAuthProvider() {
        return { ok: true, data: { auth_mode: 'google', google_login_url: '/api/auth/google' } };
      }

      async getCurrentUser() {
        return { ok: true, data: { authenticated: false } };
      }

      async getSwitchableAccounts() {
        return { ok: true, data: { current_user_id: null, accounts: [] } };
      }

      async startPairing() {
        return startPairingMock();
      }

      async claimPairing() {
        return claimPairingMock();
      }
    };

    await import('../js/auth.js');
    await window.initAuth();

    const button = document.getElementById('pairing-login-button');
    expect(button).not.toBeNull();
    expect(button.hidden).toBe(false);

    button.click();
    await vi.advanceTimersByTimeAsync(0);

    expect(startPairingMock).toHaveBeenCalledTimes(1);
    const modal = document.getElementById('pairing-login-modal');
    expect(modal).not.toBeNull();
    expect(modal.hidden).toBe(false);
    expect(modal.textContent).toContain('ABCD-EFGH');

    await vi.advanceTimersByTimeAsync(3000);
    expect(claimPairingMock).toHaveBeenCalledTimes(1);
    expect(document.getElementById('current-user-name').textContent).toBe('');

    await vi.advanceTimersByTimeAsync(3000);
    expect(claimPairingMock).toHaveBeenCalledTimes(2);
    expect(document.getElementById('current-user-name').textContent).toBe('Carol');
    expect(document.getElementById('pairing-login-modal').hidden).toBe(true);
  });

  it('opens the pairing approval modal for authenticated users and approves a code', async () => {
    const approvePairingMock = vi.fn(async code => ({
      ok: true,
      data: {
        status: 'approved',
        public_id: 'public-123',
        pairing_code: code
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
            theme_preference: 'dark'
          }
        };
      }

      async getSwitchableAccounts() {
        return { ok: true, data: { current_user_id: 1, accounts: [] } };
      }

      async approvePairing(code) {
        return approvePairingMock(code);
      }

      async logout() {
        return { ok: true };
      }
    };

    await import('../js/auth.js');
    await window.initAuth();
    await Promise.resolve();

    const button = document.getElementById('approve-pairing-button');
    expect(button).not.toBeNull();
    expect(button.hidden).toBe(false);

    button.click();
    await Promise.resolve();

    const modal = document.getElementById('pairing-approve-modal');
    expect(modal).not.toBeNull();
    expect(modal.hidden).toBe(false);

    const input = document.getElementById('pairing-approve-code');
    input.value = 'abcd-efgh';
    document.getElementById('pairing-approve-button').click();
    await vi.advanceTimersByTimeAsync(0);

    expect(approvePairingMock).toHaveBeenCalledWith('ABCD-EFGH');
    expect(document.getElementById('pairing-approve-modal').hidden).toBe(true);
  });
});
