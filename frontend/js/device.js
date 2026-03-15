// Device detection and registration management.

(() => {
  const STORAGE_KEY = 'ytcv_device_id';
  const DEVICE_TYPES = (window.APP_CONFIG && window.APP_CONFIG.DEVICE_TYPES) || {
    TV: 'tv',
    TABLET: 'tablet',
    MOBILE: 'mobile',
    DESKTOP: 'desktop'
  };
  const DEVICE_CLASSNAMES = [
    DEVICE_TYPES.TV,
    DEVICE_TYPES.TABLET,
    DEVICE_TYPES.MOBILE,
    DEVICE_TYPES.DESKTOP
  ];

  let currentDeviceId = null;
  let currentDeviceType = null;
  let deviceIdentifier = null;
  let modal = null;

  const ui = {
    deviceLabel: document.getElementById('device-type')
  };

  const t = (key, vars) => (
    window.ytcvI18n && typeof window.ytcvI18n.t === 'function'
      ? window.ytcvI18n.t(key, vars)
      : key
  );

  function getApiClient() {
    if (!window.APIClient || !window.APP_CONFIG) {
      return null;
    }

    if (!window.appApiClient) {
      window.appApiClient = new window.APIClient(
        window.APP_CONFIG.API_BASE_URL,
        window.APP_CONFIG.REQUEST_TIMEOUT
      );
    }

    return window.appApiClient;
  }

  function hashString(value) {
    let hash = 2166136261;
    for (let i = 0; i < value.length; i += 1) {
      hash ^= value.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16);
  }

  function buildDeviceIdentifier() {
    const userAgent = navigator.userAgent || '';
    const width = window.screen ? window.screen.width : 0;
    const height = window.screen ? window.screen.height : 0;
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    const language = navigator.language || '';
    const fingerprint = `${userAgent}|${width}x${height}|${timezone}|${language}`;
    return `dev-${hashString(fingerprint)}`;
  }

  function getDeviceId() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return null;
    }
  }

  function setDeviceId(id) {
    if (!id) {
      return;
    }

    try {
      localStorage.setItem(STORAGE_KEY, String(id));
    } catch (error) {
      return;
    }
  }

  function getDeviceLabel(type) {
    if (!type) {
      return '--';
    }

    const map = {
      [DEVICE_TYPES.TV]: t('deviceTypeTv'),
      [DEVICE_TYPES.TABLET]: t('deviceTypeTablet'),
      [DEVICE_TYPES.MOBILE]: t('deviceTypeMobile'),
      [DEVICE_TYPES.DESKTOP]: t('deviceTypeDesktop')
    };

    return (map[type] || type).toUpperCase();
  }

  function updateDeviceLabel(type) {
    if (!ui.deviceLabel) {
      return;
    }

    const label = getDeviceLabel(type);
    ui.deviceLabel.textContent = t('deviceLabel', { device: label });
  }

  function applyDeviceClass(type) {
    if (!document.body) {
      return;
    }

    DEVICE_CLASSNAMES.forEach(deviceType => {
      document.body.classList.remove(`device-${deviceType}`);
    });

    if (type) {
      document.body.classList.add(`device-${type}`);
    }
  }

  function setCurrentDevice(type) {
    currentDeviceType = type;
    applyDeviceClass(type);
    updateDeviceLabel(type);
  }

  async function detectDevice() {
    const api = getApiClient();
    if (!api) {
      return null;
    }

    const width = window.screen ? window.screen.width : 0;
    const height = window.screen ? window.screen.height : 0;
    const response = await api.detectDevice(navigator.userAgent || '', width, height);
    if (!response.ok) {
      return null;
    }

    return response.data;
  }

  async function registerDevice() {
    const api = getApiClient();
    if (!api) {
      return null;
    }

    if (!deviceIdentifier) {
      deviceIdentifier = buildDeviceIdentifier();
    }

    const response = await api.registerDevice(deviceIdentifier, navigator.userAgent || '');
    if (!response.ok) {
      return null;
    }

    return response.data;
  }

  async function confirmDeviceType(type) {
    const api = getApiClient();
    if (!api || !currentDeviceId) {
      return false;
    }

    const response = await api.setDeviceType(currentDeviceId, type);
    if (!response.ok) {
      return false;
    }

    setCurrentDevice(type);
    return true;
  }

  function buildDeviceModal(suggestedType) {
    if (modal) {
      return modal;
    }

    const overlay = document.createElement('div');
    overlay.className = 'modal';
    overlay.id = 'device-type-modal';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');

    const content = document.createElement('div');
    content.className = 'modal__content';

    const title = document.createElement('h2');
    title.className = 'heading-2';
    title.textContent = t('confirmDeviceTitle');

    const message = document.createElement('p');
    message.className = 'body';
    message.textContent = t('confirmDeviceMessage', { device: getDeviceLabel(suggestedType) });

    const fieldset = document.createElement('fieldset');
    fieldset.className = 'field';

    const legend = document.createElement('span');
    legend.className = 'field__label';
    legend.textContent = t('confirmDeviceLegend');

    fieldset.appendChild(legend);

    const types = [DEVICE_TYPES.TV, DEVICE_TYPES.TABLET, DEVICE_TYPES.MOBILE, DEVICE_TYPES.DESKTOP];
    types.forEach(type => {
      const label = document.createElement('label');
      label.className = 'checkbox';

      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'device-type';
      input.value = type;
      if (type === suggestedType) {
        input.checked = true;
      }

      const text = document.createElement('span');
      text.textContent = getDeviceLabel(type);

      label.appendChild(input);
      label.appendChild(text);
      fieldset.appendChild(label);
    });

    const actions = document.createElement('div');
    actions.className = 'field__group';

    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.className = 'button button--ghost';
    cancelButton.textContent = t('cancel');

    const confirmButton = document.createElement('button');
    confirmButton.type = 'button';
    confirmButton.className = 'button';
    confirmButton.textContent = t('confirm');

    actions.appendChild(cancelButton);
    actions.appendChild(confirmButton);

    content.appendChild(title);
    content.appendChild(message);
    content.appendChild(fieldset);
    content.appendChild(actions);

    overlay.appendChild(content);

    cancelButton.addEventListener('click', () => {
      closeDeviceModal();
      if (currentDeviceType) {
        setCurrentDevice(currentDeviceType);
      }
    });

    confirmButton.addEventListener('click', async () => {
      const selected = overlay.querySelector('input[name="device-type"]:checked');
      const chosenType = selected ? selected.value : suggestedType;
      confirmButton.disabled = true;
      const ok = await confirmDeviceType(chosenType);
      confirmButton.disabled = false;
      if (ok) {
        closeDeviceModal();
      }
    });

    overlay.addEventListener('click', event => {
      if (event.target === overlay) {
        closeDeviceModal();
      }
    });

    modal = overlay;
    return modal;
  }

  function openDeviceModal(suggestedType) {
    const overlay = buildDeviceModal(suggestedType);
    if (!overlay.parentNode) {
      document.body.appendChild(overlay);
    }
  }

  function closeDeviceModal() {
    if (!modal || !modal.parentNode) {
      return;
    }

    modal.parentNode.removeChild(modal);
  }

  async function initDevice() {
    deviceIdentifier = buildDeviceIdentifier();
    const suggestion = await detectDevice();
    const suggestedType = suggestion && suggestion.suggested_type
      ? suggestion.suggested_type
      : DEVICE_TYPES.DESKTOP;

    const registration = await registerDevice();
    if (!registration) {
      setCurrentDevice(DEVICE_TYPES.DESKTOP);
      return null;
    }

    currentDeviceId = registration.id;
    currentDeviceType = registration.device_type;
    setDeviceId(currentDeviceId);
    const normalizedSuggestedType = suggestedType || DEVICE_TYPES.DESKTOP;
    const normalizedCurrentType = currentDeviceType || DEVICE_TYPES.DESKTOP;
    const isNew = normalizedCurrentType === DEVICE_TYPES.DESKTOP
      && normalizedSuggestedType !== DEVICE_TYPES.DESKTOP;

    if (isNew) {
      openDeviceModal(suggestedType);
    } else {
      setCurrentDevice(currentDeviceType);
    }

    return registration;
  }

  function getCurrentDeviceType() {
    return currentDeviceType;
  }

  window.initDevice = initDevice;
  window.detectDevice = detectDevice;
  window.registerDevice = registerDevice;
  window.confirmDeviceType = confirmDeviceType;
  window.getDeviceId = getDeviceId;
  window.getCurrentDeviceType = getCurrentDeviceType;
})();
