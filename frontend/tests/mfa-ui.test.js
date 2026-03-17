import { beforeEach, describe, expect, it, vi } from 'vitest';

function translate(key, vars = {}) {
  return key.replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ''));
}

describe('mfa settings UI', () => {
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

  it('opens the MFA modal and completes TOTP setup confirmation', async () => {
    const getMfaStatusMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        data: { totp_enabled: false, totp_pending: false, recovery_codes_remaining: 0 }
      })
      .mockResolvedValueOnce({
        ok: true,
        data: { totp_enabled: true, totp_pending: false, recovery_codes_remaining: 8 }
      });
    const setupTotpMock = vi.fn(async () => ({
      ok: true,
      data: { secret: 'ABC123', otpauth_url: 'otpauth://totp/test' }
    }));
    const confirmTotpMock = vi.fn(async () => ({
      ok: true,
      data: { totp_enabled: true, recovery_codes: ['RCODE-1111', 'RCODE-2222'] }
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

      async getMfaStatus() {
        return getMfaStatusMock();
      }

      async setupTotp() {
        return setupTotpMock();
      }

      async confirmTotp(code) {
        return confirmTotpMock(code);
      }

      async logout() {
        return { ok: true };
      }
    };

    await import('../js/auth.js');
    await window.initAuth();
    await new Promise(resolve => setTimeout(resolve, 0));

    const manageButton = document.getElementById('manage-mfa-button');
    expect(manageButton).not.toBeNull();
    expect(manageButton.hidden).toBe(false);

    manageButton.click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(getMfaStatusMock).toHaveBeenCalledTimes(1);
    expect(document.getElementById('mfa-modal').hidden).toBe(false);
    expect(document.getElementById('mfa-modal').textContent).toContain('mfaEnabledNo');

    document.getElementById('mfa-start-setup-button').click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(setupTotpMock).toHaveBeenCalledTimes(1);
    expect(document.getElementById('mfa-setup-secret').textContent).toContain('ABC123');

    const confirmInput = document.getElementById('mfa-confirm-code');
    confirmInput.value = '123456';
    document.getElementById('mfa-confirm-button').click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(confirmTotpMock).toHaveBeenCalledWith('123456');
    expect(getMfaStatusMock).toHaveBeenCalledTimes(2);
    expect(document.getElementById('mfa-modal').textContent).toContain('RCODE-1111');
    expect(document.getElementById('mfa-modal').textContent).toContain('RCODE-2222');
  });

  it('regenerates recovery codes for an enabled MFA account', async () => {
    const getMfaStatusMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        data: { totp_enabled: true, totp_pending: false, recovery_codes_remaining: 6 }
      })
      .mockResolvedValueOnce({
        ok: true,
        data: { totp_enabled: true, totp_pending: false, recovery_codes_remaining: 8 }
      });
    const regenerateMock = vi.fn(async () => ({
      ok: true,
      data: { recovery_codes: ['NEWCODE-1111', 'NEWCODE-2222'] }
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
            user_id: 2,
            username: 'bob@gmail.com',
            display_name: 'Bob',
            email: 'bob@gmail.com',
            auth_provider: 'google',
            google_avatar_url: null,
            theme_preference: 'dark'
          }
        };
      }

      async getSwitchableAccounts() {
        return { ok: true, data: { current_user_id: 2, accounts: [] } };
      }

      async getMfaStatus() {
        return getMfaStatusMock();
      }

      async regenerateRecoveryCodes(code) {
        return regenerateMock(code);
      }

      async logout() {
        return { ok: true };
      }
    };

    await import('../js/auth.js');
    await window.initAuth();
    await new Promise(resolve => setTimeout(resolve, 0));

    document.getElementById('manage-mfa-button').click();
    await new Promise(resolve => setTimeout(resolve, 0));

    const regenInput = document.getElementById('mfa-regenerate-code');
    regenInput.value = '654321';
    document.getElementById('mfa-regenerate-button').click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(regenerateMock).toHaveBeenCalledWith('654321');
    expect(getMfaStatusMock).toHaveBeenCalledTimes(2);
    expect(document.getElementById('mfa-modal').textContent).toContain('NEWCODE-1111');
    expect(document.getElementById('mfa-modal').textContent).toContain('NEWCODE-2222');
  });
});
