import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('google account switching', () => {
  let switchAccountMock;

  beforeEach(() => {
    vi.resetModules();
    switchAccountMock = vi.fn(async userId => ({
      ok: true,
      data: {
        authenticated: true,
        user_id: userId,
        username: 'bob@gmail.com',
        display_name: 'Bob',
        email: 'bob@gmail.com',
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
      API_BASE_URL: 'http://localhost:5550',
      REQUEST_TIMEOUT: 5000
    };
    window.ytcvI18n = {
      t: (key, vars) => {
        if (key === 'signedInAsPrefix') return 'Signed in as';
        if (key === 'switchAccount') return 'Switch account';
        if (key === 'signOut') return 'Logout';
        if (key === 'accountSwitcherTitle') return 'Switch Google account';
        if (key === 'accountSwitcherDescription') return 'Choose an account';
        if (key === 'addGoogleAccount') return 'Add Google account';
        if (key === 'noGoogleAccountsYet') return 'No accounts yet';
        if (key === 'currentAccountLabel') return 'Current';
        if (key === 'close') return 'Close';
        if (key === 'statusSignInGoogle') return 'Sign in with Google';
        if (key === 'notSignedIn') return 'Not signed in';
        return vars && vars.name ? `${key}:${vars.name}` : key;
      }
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
            username: 'alice@gmail.com',
            display_name: 'Alice',
            email: 'alice@gmail.com',
            auth_provider: 'google',
            google_avatar_url: null,
            theme_preference: 'light'
          }
        };
      }

      async getSwitchableAccounts() {
        return {
          ok: true,
          data: {
            current_user_id: 1,
            accounts: [
              {
                id: 1,
                username: 'alice@gmail.com',
                display_name: 'Alice',
                email: 'alice@gmail.com',
                auth_provider: 'google',
                google_avatar_url: null,
                is_current: true
              },
              {
                id: 2,
                username: 'bob@gmail.com',
                display_name: 'Bob',
                email: 'bob@gmail.com',
                auth_provider: 'google',
                google_avatar_url: null,
                is_current: false
              }
            ]
          }
        };
      }

      async switchAccount(userId) {
        return switchAccountMock(userId);
      }

      async logout() {
        return { ok: true };
      }
    };
  });

  it('opens the account modal and switches to another known Google user', async () => {
    await import('../js/auth.js');
    await window.initAuth();

    const openButton = document.getElementById('switch-google-account-button');
    expect(openButton).not.toBeNull();

    openButton.click();
    await new Promise(resolve => setTimeout(resolve, 0));

    const accountButton = document.querySelector('#account-switcher-list button[data-user-id="2"]');
    expect(accountButton).not.toBeNull();

    accountButton.click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(switchAccountMock).toHaveBeenCalledWith(2);
    expect(document.getElementById('current-user-name').textContent).toBe('Bob');
  });
});
