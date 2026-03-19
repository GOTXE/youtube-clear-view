import { beforeEach, describe, expect, it, vi } from 'vitest';

function translate(key) {
  return key;
}

describe('admin observability UI', () => {
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

  it('shows admin observability for admin users and toggles detailed metrics', async () => {
    const getAdminSqliteObservabilityMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        data: {
          enabled: false,
          slow_write_threshold_ms: 100,
          write_count: 4,
          write_time_ms_avg: 2.4,
          write_time_ms_max: 8.1,
          slow_write_count: 0,
          lock_error_count: 0,
          active_manual_refreshes: [],
          recent_writes: [{ statement: 'UPDATE', duration_ms: 3.2 }]
        }
      })
      .mockResolvedValueOnce({
        ok: true,
        data: {
          enabled: true,
          slow_write_threshold_ms: 100,
          write_count: 4,
          write_time_ms_avg: 2.4,
          write_time_ms_max: 8.1,
          slow_write_count: 0,
          lock_error_count: 0,
          active_manual_refreshes: [],
          recent_writes: [{ statement: 'UPDATE', duration_ms: 3.2 }]
        }
      });
    const updateAdminSqliteObservabilityMock = vi.fn(async enabled => ({
      ok: true,
      data: {
        enabled,
        slow_write_threshold_ms: 100,
        write_count: 4,
        write_time_ms_avg: 2.4,
        write_time_ms_max: 8.1,
        slow_write_count: 0,
        lock_error_count: 0,
        active_manual_refreshes: [],
        recent_writes: [{ statement: 'UPDATE', duration_ms: 3.2 }]
      }
    }));
    const getAdminRuntimeStateMock = vi.fn(async () => ({
      ok: true,
      data: {
        users: [
          {
            id: 1,
            username: 'admin',
            display_name: 'Admin',
            has_active_session: true,
            device_count: 1,
            devices: [
              {
                id: 7,
                device_identifier: 'dev-admin',
                device_type: 'tv',
                frontend_mode: 'tv'
              }
            ]
          }
        ]
      }
    }));
    const getAdminPasswordPolicyMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        data: {
          password_policy: 'strong',
          options: [
            { value: 'simple', label: 'Simple' },
            { value: 'strong', label: 'Strong' },
            { value: 'unbreakable', label: 'Unbreakable' }
          ]
        }
      })
      .mockResolvedValueOnce({
        ok: true,
        data: {
          password_policy: 'unbreakable',
          options: [
            { value: 'simple', label: 'Simple' },
            { value: 'strong', label: 'Strong' },
            { value: 'unbreakable', label: 'Unbreakable' }
          ]
        }
      });
    const updateAdminPasswordPolicyMock = vi.fn(async passwordPolicy => ({
      ok: true,
      data: {
        password_policy: passwordPolicy,
        options: [
          { value: 'simple', label: 'Simple' },
          { value: 'strong', label: 'Strong' },
          { value: 'unbreakable', label: 'Unbreakable' }
        ]
      }
    }));

    window.APIClient = class APIClient {
      async getAuthProvider() {
        return {
          ok: true,
          data: {
            auth_mode: 'google',
            google_login_url: '/api/auth/google',
            local_signup_enabled: false
          }
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
            google_avatar_url: null,
            is_admin: true,
            theme_preference: 'dark'
          }
        };
      }

      async getSwitchableAccounts() {
        return { ok: true, data: { current_user_id: 1, accounts: [] } };
      }

      async getAdminSqliteObservability() {
        return getAdminSqliteObservabilityMock();
      }

      async getAdminRuntimeState() {
        return getAdminRuntimeStateMock();
      }

      async updateAdminSqliteObservability(enabled) {
        return updateAdminSqliteObservabilityMock(enabled);
      }

      async getAdminPasswordPolicy() {
        return getAdminPasswordPolicyMock();
      }

      async updateAdminPasswordPolicy(passwordPolicy) {
        return updateAdminPasswordPolicyMock(passwordPolicy);
      }

      async logout() {
        return { ok: true };
      }
    };

    await import('../js/auth.js');
    await window.initAuth();
    await new Promise(resolve => setTimeout(resolve, 0));

    const button = document.getElementById('manage-admin-button');
    expect(button).not.toBeNull();
    expect(button.hidden).toBe(false);

    button.click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(getAdminSqliteObservabilityMock).toHaveBeenCalledTimes(1);
    expect(getAdminRuntimeStateMock).toHaveBeenCalledTimes(1);
    expect(getAdminPasswordPolicyMock).toHaveBeenCalledTimes(1);
    expect(document.getElementById('admin-observability-modal').hidden).toBe(false);
    expect(document.getElementById('admin-observability-modal').textContent).toContain('adminMetricsWriteCount');
    expect(document.getElementById('admin-observability-modal').textContent).toContain('UPDATE');
    expect(document.getElementById('admin-observability-modal').textContent).toContain('adminRuntimeState');
    expect(document.getElementById('admin-observability-modal').textContent).toContain('dev-admin');
    expect(document.getElementById('admin-password-policy-select').value).toBe('strong');

    document.getElementById('admin-observability-toggle').click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(updateAdminSqliteObservabilityMock).toHaveBeenCalledWith(true);
    expect(document.getElementById('admin-observability-modal').textContent).toContain('adminMetricsEnabled');

    const policySelect = document.getElementById('admin-password-policy-select');
    policySelect.value = 'unbreakable';
    document.getElementById('admin-password-policy-save').click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(updateAdminPasswordPolicyMock).toHaveBeenCalledWith('unbreakable');
  });
});
