import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('login page setup wizard', () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = '<div id="app"></div>';

    window.APP_CONFIG = {
      API_BASE_URL: '',
      REQUEST_TIMEOUT: 5000
    };
    window.appApiClient = null;
    window.ytcvI18n = { t: key => key };
    window.ytcvPasskeys = { isSupported: () => false };
  });

  afterEach(() => {
    delete window.APP_CONFIG;
    delete window.appApiClient;
    delete window.ytcvI18n;
    delete window.ytcvPasskeys;
    delete window.APIClient;
    delete window.ytcvLoginPage;
  });

  it('requires matching password confirmation and supports show/hide toggles', async () => {
    const completeSetupMock = vi.fn(async () => ({
      ok: true,
      data: {
        authenticated: true,
        username: 'alice'
      }
    }));

    window.APIClient = class APIClient {
      async getAuthProvider() {
        return {
          ok: true,
          data: {
            auth_mode: 'google',
            google_login_url: '/api/auth/google'
          }
        };
      }

      async completeSetup(username, password) {
        return completeSetupMock(username, password);
      }
    };

    await import('../js/login-page.js');

    window.ytcvLoginPage.show({ wizard: true, username: 'alice' });

    const passwordInput = document.getElementById('lp-wizard-password');
    const confirmInput = document.getElementById('lp-wizard-password-confirm');
    const passwordToggle = document.getElementById('lp-wizard-password-toggle');
    const confirmToggle = document.getElementById('lp-wizard-password-confirm-toggle');

    expect(passwordInput).not.toBeNull();
    expect(confirmInput).not.toBeNull();
    expect(confirmInput.type).toBe('password');

    passwordToggle.click();
    confirmToggle.click();

    expect(passwordInput.type).toBe('text');
    expect(confirmInput.type).toBe('text');

    document.getElementById('lp-wizard-username').value = 'alice';
    passwordInput.value = 'Password123!';
    confirmInput.value = 'Password123?';

    document.getElementById('lp-wizard-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await Promise.resolve();

    expect(completeSetupMock).not.toHaveBeenCalled();
    expect(document.getElementById('lp-wizard-error').textContent).toBe('registerPasswordMismatch');
  });
});
