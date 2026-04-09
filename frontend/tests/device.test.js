import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('device rehydration after user switch', () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
    document.body.innerHTML = `
      <div id="device-type"></div>
    `;

    window.APP_CONFIG = {
      API_BASE_URL: 'http://localhost:5550',
      REQUEST_TIMEOUT: 5000,
      DEVICE_TYPES: {
        TV: 'tv',
        TABLET: 'tablet',
        MOBILE: 'mobile',
        DESKTOP: 'desktop'
      }
    };

    window.ytcvI18n = {
      t: (key, vars) => {
        if (key === 'deviceLabel') {
          return `Device: ${vars.device}`;
        }
        if (key === 'deviceTypeTv') return 'TV';
        if (key === 'deviceTypeTablet') return 'TABLET';
        if (key === 'deviceTypeMobile') return 'MOBILE';
        if (key === 'deviceTypeDesktop') return 'DESKTOP';
        if (key === 'confirmDeviceTitle') return 'Confirm device';
        if (key === 'confirmDeviceMessage') return `Detected ${vars.device}`;
        if (key === 'confirmDeviceLegend') return 'Choose';
        if (key === 'cancel') return 'Cancel';
        if (key === 'confirm') return 'Confirm';
        return key;
      }
    };

    Object.defineProperty(window, 'screen', {
      value: { width: 1920, height: 1080 },
      configurable: true
    });

    Object.defineProperty(navigator, 'language', {
      value: 'en-US',
      configurable: true
    });

    window.APIClient = class APIClient {
      async detectDevice() {
        return {
          ok: true,
          data: {
            suggested_type: 'tv',
            confidence: 0.9
          }
        };
      }

      async registerDevice() {
        return {
          ok: true,
          data: {
            id: 42,
            device_type: 'tv',
            device_type_confirmed: true
          }
        };
      }

      async setDeviceType() {
        return { ok: true };
      }
    };
    window.getCurrentUser = () => ({ id: 1, username: 'alice' });
  });

  afterEach(() => {
    delete window.APIClient;
    delete window.appApiClient;
    delete window.getCurrentUser;
    delete window.initDevice;
    delete window.detectDevice;
    delete window.registerDevice;
    delete window.confirmDeviceType;
    delete window.getDeviceId;
    delete window.getCurrentDeviceType;
    delete window.getCurrentDevice;
    delete window.openDeviceTypeModal;
  });

  it('reuses the current user device type without reopening confirmation when ids change', async () => {
    localStorage.setItem('ytcv_device_id', '11');

    await import('../js/device.js');
    const registration = await window.initDevice();

    expect(registration.id).toBe(42);
    expect(window.getDeviceId()).toBe('42');
    expect(window.getCurrentDeviceType()).toBe('tv');
    expect(document.getElementById('device-type').textContent).toBe('Device: TV');
    expect(document.getElementById('device-type-modal')).toBeNull();
  });

  it('opens the device modal automatically when the device is still unconfirmed', async () => {
    window.APIClient = class APIClient {
      async detectDevice() {
        return {
          ok: true,
          data: { suggested_type: 'tv', confidence: 0.9 }
        };
      }

      async registerDevice() {
        return {
          ok: true,
          data: {
            id: 42,
            device_type: 'desktop',
            device_type_confirmed: false
          }
        };
      }

      async setDeviceType() {
        return { ok: true };
      }
    };

    await import('../js/device.js');
    await window.initDevice();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(document.getElementById('device-type-modal')).not.toBeNull();
  });

  it('closes the device modal after confirmation even when the API client returns ok without data', async () => {
    const setDeviceTypeMock = vi.fn(async () => ({ ok: true }));

    window.APIClient = class APIClient {
      async detectDevice() {
        return {
          ok: true,
          data: { suggested_type: 'tv', confidence: 0.9 }
        };
      }

      async registerDevice() {
        return {
          ok: true,
          data: {
            id: 42,
            device_type: 'desktop',
            device_type_confirmed: false
          }
        };
      }

      async setDeviceType() {
        return setDeviceTypeMock();
      }
    };

    await import('../js/device.js');
    await window.initDevice();
    await new Promise(resolve => setTimeout(resolve, 0));

    const modal = document.getElementById('device-type-modal');
    expect(modal).not.toBeNull();

    modal.querySelectorAll('button.button')[1].click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(setDeviceTypeMock).toHaveBeenCalledTimes(1);
    expect(document.getElementById('device-type-modal')).toBeNull();
    expect(window.getCurrentDeviceType()).toBe('tv');
  });
});
