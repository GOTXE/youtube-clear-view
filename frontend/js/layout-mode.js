// Frontend layout mode resolver and per-device UI mode persistence.

(() => {
  const MODE_STORAGE_KEY = 'ytcv_frontend_mode';
  const TV_SCALE_STORAGE_KEY = 'ytcv_tv_scale';
  const SCREEN_SIZE_STORAGE_KEY = 'ytcv_tv_screen_size_inches';
  const VIEWING_DISTANCE_STORAGE_KEY = 'ytcv_tv_viewing_distance_m';

  const MODES = {
    PHONE: 'phone',
    DESKTOP_TABLET: 'desktop_tablet',
    TV: 'tv'
  };

  const TV_SCALES = ['M', 'L', 'XL', 'XXL'];

  let currentMode = null;
  let currentTvScale = null;
  let currentPreferences = null;
  let currentDevice = null;
  let modal = null;

  const ui = {
    menuDisplayMode: document.getElementById('menu-display-mode')
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

  function safeStorageGet(key) {
    try {
      return localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function safeStorageSet(key, value) {
    try {
      if (value === null || value === undefined || value === '') {
        localStorage.removeItem(key);
      } else {
        localStorage.setItem(key, String(value));
      }
    } catch (error) {
      return;
    }
  }

  function inferModeFromViewport() {
    const width = window.innerWidth || (window.screen ? window.screen.width : 0) || 0;
    return width > 0 && width < 768 ? MODES.PHONE : MODES.DESKTOP_TABLET;
  }

  function mapDeviceTypeToMode(deviceType) {
    if (deviceType === 'tv') {
      return MODES.TV;
    }
    if (deviceType === 'mobile') {
      return MODES.PHONE;
    }
    return MODES.DESKTOP_TABLET;
  }

  function inferDefaultTvScale() {
    const width = window.innerWidth || (window.screen ? window.screen.width : 0) || 0;
    if (width >= 3400) {
      return 'XXL';
    }
    if (width >= 2500) {
      return 'XL';
    }
    return 'L';
  }

  function applyMode(mode) {
    currentMode = mode;
    document.documentElement.dataset.mode = mode;
    document.body.dataset.mode = mode;
  }

  function applyTvScale(scale) {
    currentTvScale = scale;
    if (scale) {
      document.documentElement.dataset.tvScale = scale;
    } else {
      delete document.documentElement.dataset.tvScale;
    }
  }

  function getStoredOverridePreferences() {
    return {
      frontend_mode: safeStorageGet(MODE_STORAGE_KEY),
      tv_scale: safeStorageGet(TV_SCALE_STORAGE_KEY),
      screen_size_inches: safeStorageGet(SCREEN_SIZE_STORAGE_KEY),
      viewing_distance_m: safeStorageGet(VIEWING_DISTANCE_STORAGE_KEY)
    };
  }

  function updateCurrentPreferences(preferences) {
    currentPreferences = {
      frontend_mode: preferences.frontend_mode || null,
      tv_scale: preferences.tv_scale || null,
      screen_size_inches: preferences.screen_size_inches || null,
      viewing_distance_m: preferences.viewing_distance_m || null
    };
  }

  function saveOverridePreferences(preferences) {
    safeStorageSet(MODE_STORAGE_KEY, preferences.frontend_mode || null);
    safeStorageSet(TV_SCALE_STORAGE_KEY, preferences.tv_scale || null);
    safeStorageSet(SCREEN_SIZE_STORAGE_KEY, preferences.screen_size_inches || null);
    safeStorageSet(VIEWING_DISTANCE_STORAGE_KEY, preferences.viewing_distance_m || null);
    updateCurrentPreferences(preferences);
  }

  function resolveMode(device = null) {
    const storedOverride = getStoredOverridePreferences();
    if (storedOverride.frontend_mode) {
      return storedOverride.frontend_mode;
    }
    if (device && device.frontend_mode) {
      return device.frontend_mode;
    }
    if (device && device.device_type) {
      return mapDeviceTypeToMode(device.device_type);
    }
    return inferModeFromViewport();
  }

  function resolveTvScale(device = null, mode = null) {
    const effectiveMode = mode || currentMode || resolveMode(device);
    if (effectiveMode !== MODES.TV) {
      return null;
    }

    const storedOverride = getStoredOverridePreferences();
    if (storedOverride.tv_scale && TV_SCALES.includes(storedOverride.tv_scale)) {
      return storedOverride.tv_scale;
    }
    if (device && device.tv_scale && TV_SCALES.includes(device.tv_scale)) {
      return device.tv_scale;
    }
    return inferDefaultTvScale();
  }

  function applyResolvedMode(device = null) {
    const mode = resolveMode(device);
    const tvScale = resolveTvScale(device, mode);
    applyMode(mode);
    applyTvScale(tvScale);
    updateCurrentPreferences({
      frontend_mode: mode,
      tv_scale: tvScale,
      screen_size_inches: device && device.screen_size_inches ? device.screen_size_inches : currentPreferences && currentPreferences.screen_size_inches,
      viewing_distance_m: device && device.viewing_distance_m ? device.viewing_distance_m : currentPreferences && currentPreferences.viewing_distance_m
    });
    window.dispatchEvent(new CustomEvent('layout-mode:changed', {
      detail: { mode, tvScale }
    }));
    return { mode, tvScale };
  }

  async function persistPreferences(preferences) {
    const api = getApiClient();
    if (!api || !currentDevice || !currentDevice.id) {
      saveOverridePreferences(preferences);
      applyResolvedMode({ ...currentDevice, ...preferences });
      return true;
    }

    const response = await api.updateDevicePreferences(currentDevice.id, preferences);
    if (!response.ok) {
      return false;
    }

    currentDevice = response.data;
    saveOverridePreferences(response.data);
    applyResolvedMode(response.data);
    return true;
  }

  function buildModal() {
    if (modal && modal.parentNode) {
      modal.parentNode.removeChild(modal);
    }
    modal = null;

    const overlay = document.createElement('div');
    overlay.className = 'modal';
    overlay.id = 'layout-mode-modal';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');

    const content = document.createElement('div');
    content.className = 'modal__content layout-mode-modal';

    const title = document.createElement('h2');
    title.className = 'heading-2';
    title.textContent = t('displaySetupTitle');

    const intro = document.createElement('p');
    intro.className = 'body';
    intro.textContent = t('displaySetupDescription');

    const deviceFieldset = document.createElement('fieldset');
    deviceFieldset.className = 'field';

    const deviceLegend = document.createElement('span');
    deviceLegend.className = 'field__label';
    deviceLegend.textContent = t('confirmDeviceLegend');
    deviceFieldset.appendChild(deviceLegend);

    const currentDeviceType = (currentDevice && currentDevice.device_type) || (
      typeof window.getCurrentDeviceType === 'function' ? window.getCurrentDeviceType() : null
    ) || 'desktop';

    [
      ['tv', t('deviceTypeTv')],
      ['tablet', t('deviceTypeTablet')],
      ['mobile', t('deviceTypeMobile')],
      ['desktop', t('deviceTypeDesktop')]
    ].forEach(([value, labelText]) => {
      const label = document.createElement('label');
      label.className = 'checkbox';

      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'device-type';
      input.value = value;
      if (value === currentDeviceType) {
        input.checked = true;
      }

      const text = document.createElement('span');
      text.textContent = labelText;

      label.appendChild(input);
      label.appendChild(text);
      deviceFieldset.appendChild(label);
    });

    const modeFieldset = document.createElement('fieldset');
    modeFieldset.className = 'field';

    const modeLegend = document.createElement('span');
    modeLegend.className = 'field__label';
    modeLegend.textContent = t('displayModeLegend');
    modeFieldset.appendChild(modeLegend);

    [
      [MODES.PHONE, t('displayModePhone')],
      [MODES.DESKTOP_TABLET, t('displayModeDesktopTablet')],
      [MODES.TV, t('displayModeTv')]
    ].forEach(([value, labelText]) => {
      const label = document.createElement('label');
      label.className = 'checkbox';

      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'layout-mode';
      input.value = value;
      if (value === currentMode) {
        input.checked = true;
      }

      const text = document.createElement('span');
      text.textContent = labelText;

      label.appendChild(input);
      label.appendChild(text);
      modeFieldset.appendChild(label);
    });

    const tvOptions = document.createElement('div');
    tvOptions.className = 'layout-mode-modal__tv-options';

    const scaleLabel = document.createElement('label');
    scaleLabel.className = 'field';
    const scaleCaption = document.createElement('span');
    scaleCaption.className = 'field__label';
    scaleCaption.textContent = t('tvScaleLabel');
    const scaleSelect = document.createElement('select');
    scaleSelect.className = 'field__input';
    TV_SCALES.forEach(scale => {
      const option = document.createElement('option');
      option.value = scale;
      option.textContent = scale;
      if (scale === currentTvScale) {
        option.selected = true;
      }
      scaleSelect.appendChild(option);
    });
    scaleLabel.appendChild(scaleCaption);
    scaleLabel.appendChild(scaleSelect);

    const sizeLabel = document.createElement('label');
    sizeLabel.className = 'field';
    const sizeCaption = document.createElement('span');
    sizeCaption.className = 'field__label';
    sizeCaption.textContent = t('tvScreenSizeLabel');
    const sizeInput = document.createElement('input');
    sizeInput.className = 'field__input';
    sizeInput.type = 'number';
    sizeInput.min = '20';
    sizeInput.max = '150';
    sizeInput.step = '1';
    sizeInput.value = currentPreferences && currentPreferences.screen_size_inches
      ? currentPreferences.screen_size_inches
      : '';
    sizeLabel.appendChild(sizeCaption);
    sizeLabel.appendChild(sizeInput);

    const distanceLabel = document.createElement('label');
    distanceLabel.className = 'field';
    const distanceCaption = document.createElement('span');
    distanceCaption.className = 'field__label';
    distanceCaption.textContent = t('tvViewingDistanceLabel');
    const distanceInput = document.createElement('input');
    distanceInput.className = 'field__input';
    distanceInput.type = 'number';
    distanceInput.min = '0.5';
    distanceInput.max = '20';
    distanceInput.step = '0.1';
    distanceInput.value = currentPreferences && currentPreferences.viewing_distance_m
      ? currentPreferences.viewing_distance_m
      : '';
    distanceLabel.appendChild(distanceCaption);
    distanceLabel.appendChild(distanceInput);

    tvOptions.appendChild(scaleLabel);
    tvOptions.appendChild(sizeLabel);
    tvOptions.appendChild(distanceLabel);

    const actions = document.createElement('div');
    actions.className = 'field__group';

    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.className = 'button button--ghost';
    cancelButton.textContent = t('cancel');

    const saveButton = document.createElement('button');
    saveButton.type = 'button';
    saveButton.className = 'button';
    saveButton.textContent = t('save');

    actions.appendChild(cancelButton);
    actions.appendChild(saveButton);

    function updateTvOptionsVisibility() {
      const selectedMode = overlay.querySelector('input[name="layout-mode"]:checked');
      tvOptions.hidden = !selectedMode || selectedMode.value !== MODES.TV;
    }

    modeFieldset.addEventListener('change', updateTvOptionsVisibility);
    updateTvOptionsVisibility();

    cancelButton.addEventListener('click', () => {
      closeDisplayModeModal();
    });

    saveButton.addEventListener('click', async () => {
      const selectedDeviceType = overlay.querySelector('input[name="device-type"]:checked');
      const selectedMode = overlay.querySelector('input[name="layout-mode"]:checked');
      const deviceType = selectedDeviceType ? selectedDeviceType.value : currentDeviceType;
      const frontendMode = selectedMode ? selectedMode.value : currentMode || inferModeFromViewport();
      const payload = {
        frontend_mode: frontendMode,
        tv_scale: frontendMode === MODES.TV ? scaleSelect.value : null,
        screen_size_inches: frontendMode === MODES.TV ? sizeInput.value : null,
        viewing_distance_m: frontendMode === MODES.TV ? distanceInput.value : null
      };

      saveButton.disabled = true;
      let ok = true;
      if (
        typeof window.confirmDeviceType === 'function'
        && currentDevice
        && currentDevice.id
        && deviceType
        && deviceType !== currentDeviceType
      ) {
        ok = Boolean(await window.confirmDeviceType(deviceType));
      }
      if (ok) {
        ok = await persistPreferences(payload);
      }
      saveButton.disabled = false;
      if (ok) {
        closeDisplayModeModal();
      }
    });

    overlay.addEventListener('click', event => {
      if (event.target === overlay) {
        closeDisplayModeModal();
      }
    });

    content.appendChild(title);
    content.appendChild(intro);
    content.appendChild(deviceFieldset);
    content.appendChild(modeFieldset);
    content.appendChild(tvOptions);
    content.appendChild(actions);
    overlay.appendChild(content);
    modal = overlay;
    return modal;
  }

  function openDisplayModeModal() {
    const overlay = buildModal();
    if (!overlay.parentNode) {
      document.body.appendChild(overlay);
    }
  }

  function closeDisplayModeModal() {
    if (!modal || !modal.parentNode) {
      return;
    }
    modal.parentNode.removeChild(modal);
    modal = null;
  }

  function setupMenuDisplayMode() {
    if (!ui.menuDisplayMode) {
      return;
    }
    if (ui.menuDisplayMode.dataset.listenerAttached === 'true') {
      return;
    }
    ui.menuDisplayMode.hidden = typeof window.getCurrentUser !== 'function' || !window.getCurrentUser();
    ui.menuDisplayMode.addEventListener('click', () => {
      openDisplayModeModal();
    });
    ui.menuDisplayMode.dataset.listenerAttached = 'true';

    window.addEventListener('auth:changed', event => {
      const user = event.detail ? event.detail.user : null;
      ui.menuDisplayMode.hidden = !user;
    });
  }

  function syncFromDevice(device) {
    currentDevice = device || null;
    if (device) {
      updateCurrentPreferences({
        frontend_mode: device.frontend_mode || null,
        tv_scale: device.tv_scale || null,
        screen_size_inches: device.screen_size_inches || null,
        viewing_distance_m: device.viewing_distance_m || null
      });
    }
    return applyResolvedMode(device);
  }

  function getCurrentMode() {
    return currentMode;
  }

  function getCurrentTvScale() {
    return currentTvScale;
  }

  function initLayoutMode() {
    applyResolvedMode();
    setupMenuDisplayMode();
  }

  window.ytcvLayoutMode = {
    MODES,
    TV_SCALES,
    initLayoutMode,
    inferModeFromViewport,
    mapDeviceTypeToMode,
    resolveMode,
    resolveTvScale,
    syncFromDevice,
    getCurrentMode,
    getCurrentTvScale,
    openDisplayModeModal
  };

  initLayoutMode();
})();
