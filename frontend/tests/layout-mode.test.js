import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

function translate(key, vars = {}) {
  const messages = {
    tvScaleRecommendationValue: 'Recommended scale: {scale}'
  };
  return (messages[key] || key).replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ''));
}

describe('frontend layout mode system', () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
    document.documentElement.removeAttribute('data-mode');
    document.documentElement.removeAttribute('data-tv-scale');
    document.body.innerHTML = `
      <button id="menu-display-mode" type="button" hidden></button>
    `;

    window.APP_CONFIG = {
      API_BASE_URL: '/api',
      REQUEST_TIMEOUT: 5000
    };

    window.ytcvI18n = { t: translate };

    Object.defineProperty(window, 'innerWidth', {
      value: 1366,
      configurable: true
    });

    window.APIClient = class APIClient {
      async setDeviceType(_deviceId, deviceType) {
        return {
          ok: true,
          data: {
            id: 7,
            device_type: deviceType,
            device_type_confirmed: true,
            frontend_mode: 'tv',
            tv_scale: 'L',
            tv_scale_confirmed_at: '2026-03-17T12:00:00',
            screen_size_inches: 55,
            viewing_distance_m: 2.5
          }
        };
      }

      async updateDevicePreferences(_deviceId, preferences) {
        return {
          ok: true,
          data: {
            id: 7,
            device_type: 'tv',
            device_type_confirmed: true,
            frontend_mode: preferences.frontend_mode,
            tv_scale: preferences.tv_scale,
            tv_scale_confirmed_at: preferences.frontend_mode === 'tv' && preferences.tv_scale
              ? '2026-03-17T12:00:00'
              : null,
            screen_size_inches: preferences.screen_size_inches ? Number(preferences.screen_size_inches) : null,
            viewing_distance_m: preferences.viewing_distance_m ? Number(preferences.viewing_distance_m) : null
          }
        };
      }
    };

    window.getCurrentUser = () => ({ id: 1, username: 'alice' });
  });

  afterEach(() => {
    delete window.APP_CONFIG;
    delete window.ytcvI18n;
    delete window.APIClient;
    delete window.getCurrentUser;
    delete window.appApiClient;
    delete window.ytcvLayoutMode;
    delete window.confirmDeviceType;
    delete window.getCurrentDeviceType;
  });

  it('applies saved mode and tv scale on initialization', async () => {
    localStorage.setItem('ytcv_frontend_mode', 'tv');
    localStorage.setItem('ytcv_tv_scale', 'XL');

    await import('../js/layout-mode.js');

    expect(document.documentElement.dataset.mode).toBe('tv');
    expect(document.documentElement.dataset.tvScale).toBe('XL');
    expect(window.ytcvLayoutMode.getCurrentMode()).toBe('tv');
    expect(window.ytcvLayoutMode.getCurrentTvScale()).toBe('XL');
  });

  it('derives mode from synced device data when no saved override exists', async () => {
    await import('../js/layout-mode.js');

    window.ytcvLayoutMode.syncFromDevice({
      id: 7,
      device_type: 'mobile',
      frontend_mode: null,
      tv_scale: null
    });

    expect(document.documentElement.dataset.mode).toBe('phone');
    expect(window.ytcvLayoutMode.getCurrentMode()).toBe('phone');
  });

  it('opens the display mode modal and persists tv preferences', async () => {
    await import('../js/layout-mode.js');
    window.confirmDeviceType = vi.fn(async deviceType => ({
      id: 7,
      device_type: deviceType,
      device_type_confirmed: true
    }));
    window.getCurrentDeviceType = () => 'tv';

    window.ytcvLayoutMode.syncFromDevice({
      id: 7,
      device_type: 'tv',
      device_type_confirmed: true,
      frontend_mode: 'tv',
      tv_scale: 'L',
      screen_size_inches: 55,
      viewing_distance_m: 2.5
    });

    const button = document.getElementById('menu-display-mode');
    expect(button.hidden).toBe(false);

    button.click();

    const modal = document.getElementById('layout-mode-modal');
    expect(modal).not.toBeNull();
    expect(modal.querySelector('#tv-scale-recommendation').textContent).toContain('Recommended scale: XL');

    modal.querySelector('input[name="device-type"][value="desktop"]').checked = true;
    modal.querySelector('input[name="layout-mode"][value="tv"]').checked = true;
    modal.querySelector('input[type="number"]').value = '65';
    modal.querySelector('input[type="number"]').dispatchEvent(new Event('input'));
    modal.querySelectorAll('input[type="number"]')[1].value = '3.5';
    modal.querySelectorAll('input[type="number"]')[1].dispatchEvent(new Event('input'));
    modal.querySelector('#tv-scale-recommendation-button').click();
    expect(modal.querySelector('select').value).toBe('XXL');
    expect(modal.querySelector('#tv-scale-preview').dataset.tvScale).toBe('XXL');

    const saveButton = Array.from(modal.querySelectorAll('button')).find(node => node.textContent === 'save');
    saveButton.click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(window.confirmDeviceType).toHaveBeenCalledWith('desktop');
    expect(document.documentElement.dataset.mode).toBe('tv');
    expect(document.documentElement.dataset.tvScale).toBe('XXL');
    expect(localStorage.getItem('ytcv_frontend_mode')).toBe('tv');
    expect(localStorage.getItem('ytcv_tv_scale')).toBe('XXL');
    expect(document.getElementById('layout-mode-modal')).toBeNull();
  });
});
