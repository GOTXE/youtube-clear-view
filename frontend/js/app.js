// Main application orchestrator for YT Clear View.

// Registro del service worker para soporte PWA
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  const root = document.getElementById('app');
  if (!root) {
    return;
  }

  const t = (key, vars) => (
    window.ytcvI18n && typeof window.ytcvI18n.t === 'function'
      ? window.ytcvI18n.t(key, vars)
      : key
  );
  const markI18nReady = () => {
    document.documentElement.classList.add('i18n-ready');
  };

  if (typeof window.APP_CONFIG === 'undefined') {
    const message = document.createElement('p');
    message.className = 'body';
    message.textContent = t('missingConfig');
    root.appendChild(message);
    markI18nReady();
    return;
  }

  const api = window.appApiClient || new window.APIClient(
    window.APP_CONFIG.API_BASE_URL,
    window.APP_CONFIG.REQUEST_TIMEOUT
  );
  window.appApiClient = api;

  const state = {
    currentUser: null,
    currentDevice: null,
    channels: [],
    selectedChannelId: null,
    selectedChannelYtId: null,
    prefetchedThumbnails: new Set(),
    filters: {
      unwatched: false,
      month: false
    },
    carousels: [],
    searchActive: false,
    searchQuery: '',
    channelFilterQuery: '',
    autoImportAttempted: false,
    autoRefreshAttempted: false,
    categoryManager: null,
    categorySelector: null,
    categoriesLoaded: false,
    settings: null,
    presets: null,
    refreshProgress: null,
    initialContentReady: false,
    autoRefreshPromise: null,
    autoRefreshKeepsLoadingState: false,
    setMenuOpen: null
  };

  const ui = {
    appSubtitle: document.getElementById('app-subtitle'),
    appSubtitleSecondary: document.getElementById('app-subtitle-secondary'),
    headerContext: document.getElementById('header-context'),
    headerContextMedia: document.getElementById('header-context-media'),
    headerContextImage: document.getElementById('header-context-image'),
    headerContextEyebrow: document.getElementById('header-context-eyebrow'),
    headerContextTitle: document.getElementById('header-context-title'),
    headerContextDescription: document.getElementById('header-context-description'),
    headerContextMetrics: document.getElementById('header-context-metrics'),
    subscriptionsTitle: document.getElementById('subscriptions-title'),
    filtersTitle: document.getElementById('filters-title'),
    filtersSearchLabel: document.getElementById('filters-search-label'),
    channelSidebar: document.querySelector('.channel-sidebar'),
    channelSidebarBackdrop: document.getElementById('channel-sidebar-backdrop'),
    phoneNav: document.getElementById('phone-nav'),
    tvActionBar: document.getElementById('tv-action-bar'),
    themeToggle: document.getElementById('theme-toggle'),
    menuToggle: document.getElementById('menu-toggle'),
    menuPanel: document.getElementById('menu-panel'),
    menuHeadingAccount: document.getElementById('menu-heading-account'),
    menuHeadingChannels: document.getElementById('menu-heading-channels'),
    menuHeadingViewing: document.getElementById('menu-heading-viewing'),
    menuHeadingSystem: document.getElementById('menu-heading-system'),
    menuFilters: document.getElementById('menu-filters'),
    menuCategoryGuide: document.getElementById('menu-category-guide'),
    menuDisplayMode: document.getElementById('menu-display-mode'),
    menuSettings: document.getElementById('menu-settings'),
    myAccountButton: document.getElementById('my-account-button'),
    logoutButton: document.getElementById('logout-button'),
    languageButtons: document.querySelectorAll('.menu-language__button'),
    filterPanel: document.getElementById('filter-panel'),
    filterPanelClose: document.getElementById('filters-close'),
    filterPanelClear: document.getElementById('filters-clear'),
    guidePanel: document.getElementById('category-guide'),
    guideClose: document.getElementById('guide-close'),
    settingsModal: document.getElementById('settings-modal'),
    settingsClose: document.getElementById('settings-close'),
    settingsCancel: document.getElementById('settings-cancel'),
    settingsSave: document.getElementById('settings-save'),
    confirmModal: document.getElementById('confirm-modal'),
    confirmTitle: document.getElementById('confirm-title'),
    confirmMessage: document.getElementById('confirm-message'),
    confirmAccept: document.getElementById('confirm-accept'),
    confirmCancel: document.getElementById('confirm-cancel'),
    confirmClose: document.getElementById('confirm-close'),
    presetRadios: document.querySelectorAll('input[name="preset"]'),
    scheduleSelects: [
      document.getElementById('schedule-1'),
      document.getElementById('schedule-2'),
      document.getElementById('schedule-3'),
      document.getElementById('schedule-4')
    ],
    scheduleLabels: [
      document.getElementById('schedule-label-1'),
      document.getElementById('schedule-label-2'),
      document.getElementById('schedule-label-3'),
      document.getElementById('schedule-label-4')
    ],
    presetTitle: document.getElementById('preset-title'),
    scheduleTitle: document.getElementById('schedule-title'),
    quotaTitle: document.getElementById('quota-title'),
    scheduleHint: document.getElementById('schedule-hint'),
    quotaStatus: document.getElementById('quota-status'),
    quotaHint: document.getElementById('quota-hint'),
    backfillStatus: document.getElementById('backfill-status'),
    inProgressCarousel: document.getElementById('in-progress-carousel'),
    inProgressSection: document.getElementById('in-progress-section'),
    inProgressCount: document.getElementById('in-progress-count'),
    inProgressLabel: document.getElementById('in-progress-label'),
    latestCarousel: document.getElementById('latest-carousel'),
    latestTitle: document.getElementById('latest-title'),
    shortsCarousel: document.getElementById('shorts-carousel'),
    olderCarousel: document.getElementById('older-carousel'),
    shortsSection: document.getElementById('shorts-section'),
    olderSection: document.getElementById('older-section'),
    olderTitle: document.getElementById('older-title'),
    refreshButton: document.getElementById('refresh-videos'),
    importButton: document.getElementById('import-subscriptions-button'),
    refreshProgress: document.getElementById('refresh-progress'),
    lastUpdatedLabel: document.getElementById('last-updated'),
    channelList: document.getElementById('channel-list'),
    channelCount: document.getElementById('channel-count'),
    channelSearchLabel: document.getElementById('channel-search-label'),
    channelSearchInput: document.getElementById('channel-search-input'),
    channelSearchClear: document.getElementById('channel-search-clear'),
    videosCount: document.getElementById('videos-count'),
    shortsCount: document.getElementById('shorts-count'),
    videosLabel: document.getElementById('videos-label'),
    shortsLabel: document.getElementById('shorts-label'),
    searchInput: document.getElementById('search-input'),
    filterUnwatched: document.getElementById('filter-unwatched'),
    filterMonth: document.getElementById('filter-month'),
    githubLabel: document.getElementById('github-label'),
    sessionInfo: document.querySelector('.session-info'),
    currentUserName: document.getElementById('current-user-name'),
    categoriesSection: document.getElementById('categories-section'),
    categoryCarousels: document.getElementById('category-carousels'),
    categoriesLabel: document.getElementById('categories-label'),
    categoriesDescription: document.getElementById('categories-description'),
    reclassifyBtn: document.getElementById('reclassify-btn'),
    classifyButton: document.getElementById('classify-channels-button')
  };

  const AUTO_REFRESH_STALE_HOURS = 6;
  const deferredTask = callback => {
    if (typeof window.requestIdleCallback === 'function') {
      window.requestIdleCallback(() => {
        callback();
      }, { timeout: 1200 });
      return;
    }

    window.setTimeout(() => {
      callback();
    }, 0);
  };

  const isVisibleForKeyboardNav = element => {
    if (!element || element.hidden || element.getAttribute('aria-hidden') === 'true') {
      return false;
    }

    const style = window.getComputedStyle(element);
    if (style.display === 'none' || style.visibility === 'hidden') {
      return false;
    }

    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };

  const getKeyboardNavigableElements = () => (
    Array.from(document.querySelectorAll(
      [
        '.menu-toggle',
        '.menu-item:not([hidden])',
        '.filter-panel__close',
        '.filter-pill',
        '.button',
        '.channel-item',
        '.video-card',
        '.carousel-control',
        '.field__input',
        '.menu-language__button'
      ].join(', ')
    )).filter(element => !element.disabled && isVisibleForKeyboardNav(element))
  );

  const getDirectionalCandidate = (current, direction) => {
    if (!current) {
      return null;
    }

    const currentRect = current.getBoundingClientRect();
    const currentCenterX = currentRect.left + currentRect.width / 2;
    const currentCenterY = currentRect.top + currentRect.height / 2;

    const candidates = getKeyboardNavigableElements()
      .filter(element => element !== current)
      .map(element => {
        const rect = element.getBoundingClientRect();
        return {
          element,
          centerX: rect.left + rect.width / 2,
          centerY: rect.top + rect.height / 2
        };
      })
      .filter(candidate => {
        if (direction === 'left') {
          return candidate.centerX < currentCenterX - 4;
        }
        if (direction === 'right') {
          return candidate.centerX > currentCenterX + 4;
        }
        if (direction === 'up') {
          return candidate.centerY < currentCenterY - 4;
        }
        if (direction === 'down') {
          return candidate.centerY > currentCenterY + 4;
        }
        return false;
      });

    if (!candidates.length) {
      return null;
    }

    candidates.sort((a, b) => {
      const primaryA = direction === 'left' || direction === 'right'
        ? Math.abs(a.centerX - currentCenterX)
        : Math.abs(a.centerY - currentCenterY);
      const primaryB = direction === 'left' || direction === 'right'
        ? Math.abs(b.centerX - currentCenterX)
        : Math.abs(b.centerY - currentCenterY);

      if (primaryA !== primaryB) {
        return primaryA - primaryB;
      }

      const secondaryA = direction === 'left' || direction === 'right'
        ? Math.abs(a.centerY - currentCenterY)
        : Math.abs(a.centerX - currentCenterX);
      const secondaryB = direction === 'left' || direction === 'right'
        ? Math.abs(b.centerY - currentCenterY)
        : Math.abs(b.centerX - currentCenterX);

      return secondaryA - secondaryB;
    });

    return candidates[0].element;
  };

  function applyLocalizedCopy() {
    if (ui.appSubtitle) {
      ui.appSubtitle.textContent = t('subtitlePrimary');
    }
    if (ui.appSubtitleSecondary) {
      ui.appSubtitleSecondary.textContent = t('subtitleSecondary');
    }
    if (ui.subscriptionsTitle) {
      ui.subscriptionsTitle.textContent = t('subscriptions');
    }
    if (ui.filtersTitle) {
      ui.filtersTitle.textContent = t('filters');
    }
    if (ui.filtersSearchLabel) {
      ui.filtersSearchLabel.textContent = t('searchLabel');
    }
    if (ui.channelSearchLabel) {
      ui.channelSearchLabel.textContent = t('searchChannelsLabel');
    }
    if (ui.searchInput) {
      ui.searchInput.placeholder = t('searchPlaceholder');
      ui.searchInput.setAttribute('aria-label', t('searchAriaLabel'));
    }
    if (ui.channelSearchInput) {
      ui.channelSearchInput.placeholder = t('searchChannelsPlaceholder');
      ui.channelSearchInput.setAttribute('aria-label', t('searchChannelsAriaLabel'));
    }
    if (ui.channelSearchClear) {
      ui.channelSearchClear.setAttribute('aria-label', t('clearChannelSearch'));
      ui.channelSearchClear.title = t('clearChannelSearch');
    }
    if (ui.refreshButton) {
      ui.refreshButton.textContent = t('refresh');
    }
    if (ui.inProgressLabel) {
      ui.inProgressLabel.textContent = t('continueWatching');
    }
    if (ui.videosLabel) {
      ui.videosLabel.textContent = t('videos');
    }
    if (ui.shortsLabel) {
      ui.shortsLabel.textContent = t('shorts');
    }
    if (ui.olderTitle) {
      ui.olderTitle.textContent = t('olderVideosShorts');
    }
    if (ui.menuFilters) {
      ui.menuFilters.textContent = t('filters');
    }
    if (ui.menuHeadingAccount) {
      ui.menuHeadingAccount.textContent = t('menuSectionAccount');
    }
    if (ui.menuHeadingChannels) {
      ui.menuHeadingChannels.textContent = t('menuSectionChannels');
    }
    if (ui.menuHeadingViewing) {
      ui.menuHeadingViewing.textContent = t('menuSectionViewing');
    }
    if (ui.menuHeadingSystem) {
      ui.menuHeadingSystem.textContent = t('menuSectionSystem');
    }
    if (ui.menuCategoryGuide) {
      ui.menuCategoryGuide.textContent = t('categoryGuideLabel');
    }
    if (ui.menuDisplayMode) {
      ui.menuDisplayMode.textContent = t('displayModeMenuLabel');
    }
    if (ui.menuSettings) {
      ui.menuSettings.textContent = t('autoUpdatesLabel');
    }
    if (ui.myAccountButton) {
      ui.myAccountButton.textContent = t('myAccount');
    }
    if (ui.importButton) {
      ui.importButton.textContent = t('importChannels');
    }
    if (ui.classifyButton) {
      ui.classifyButton.textContent = t('classifyChannels');
    }
    updateHeaderContext();
    const googleButton = document.getElementById('google-login-button');
    if (googleButton) {
      googleButton.textContent = t('signInWithGoogle');
    }
    if (ui.filterUnwatched) {
      ui.filterUnwatched.textContent = t('unwatched');
    }
    if (ui.filterMonth) {
      ui.filterMonth.textContent = t('lastMonth');
    }
    if (ui.filterPanelClear) {
      ui.filterPanelClear.textContent = t('clear');
    }
    if (ui.filterPanelClose) {
      ui.filterPanelClose.setAttribute('aria-label', t('close'));
    }
    if (ui.guideClose) {
      ui.guideClose.setAttribute('aria-label', t('close'));
    }
    if (ui.settingsClose) {
      ui.settingsClose.setAttribute('aria-label', t('close'));
    }
    if (ui.confirmClose) {
      ui.confirmClose.setAttribute('aria-label', t('close'));
    }
    if (ui.settingsCancel) {
      ui.settingsCancel.textContent = t('cancel');
    }
    if (ui.settingsSave) {
      ui.settingsSave.textContent = t('save');
    }
    if (ui.confirmTitle) {
      ui.confirmTitle.textContent = t('confirmTitle');
    }
    if (ui.confirmCancel) {
      ui.confirmCancel.textContent = t('cancel');
    }
    if (ui.confirmAccept) {
      ui.confirmAccept.textContent = t('confirm');
    }
    const settingsTitle = document.getElementById('settings-title');
    if (settingsTitle) {
      settingsTitle.textContent = t('autoUpdatesLabel');
    }
    if (ui.presetTitle) {
      ui.presetTitle.textContent = t('presetTitle');
    }
    if (ui.scheduleTitle) {
      ui.scheduleTitle.textContent = t('scheduleTitle');
    }
    if (ui.quotaTitle) {
      ui.quotaTitle.textContent = t('quotaTitle');
    }
    if (ui.scheduleHint) {
      ui.scheduleHint.textContent = t('scheduleHint');
    }
    if (ui.quotaHint) {
      ui.quotaHint.textContent = t('quotaHint');
    }
    if (ui.scheduleLabels && ui.scheduleLabels.length) {
      ui.scheduleLabels.forEach((label, index) => {
        if (label) {
          label.textContent = t('scheduleSlot', { index: index + 1 });
        }
      });
    }
    const presetLabels = document.querySelectorAll('[data-preset-label]');
    presetLabels.forEach(node => {
      const key = node.dataset.presetLabel;
      node.textContent = t(`presetLabel${key.charAt(0).toUpperCase()}${key.slice(1)}`);
    });
    const presetDescs = document.querySelectorAll('[data-preset-desc]');
    presetDescs.forEach(node => {
      const key = node.dataset.presetDesc;
      node.textContent = t(`presetDesc${key.charAt(0).toUpperCase()}${key.slice(1)}`);
    });
    if (ui.themeToggle) {
      const activeTheme = document.documentElement.getAttribute('data-theme') === 'light'
        ? 'light'
        : 'dark';
      const icon = activeTheme === 'dark' ? '🌙' : '☀️';
      const modeKey = activeTheme === 'dark' ? 'themeDark' : 'themeLight';
      const label = t('themeLabel', { mode: t(modeKey), icon });
      const labelSpan = ui.themeToggle.querySelector('.button__label');
      if (labelSpan) {
        labelSpan.textContent = label;
      } else {
        ui.themeToggle.textContent = label;
      }
    }
    if (ui.channelSidebar) {
      ui.channelSidebar.setAttribute('aria-label', t('subscriptionsAria'));
    }
    if (ui.filterPanel) {
      ui.filterPanel.setAttribute('aria-label', t('filtersAria'));
    }
    if (ui.phoneNav) {
      ui.phoneNav.setAttribute('aria-label', t('mobileNavigationLabel'));
    }
    const phoneChannels = document.getElementById('phone-nav-channels');
    if (phoneChannels) {
      phoneChannels.textContent = t('subscriptions');
    }
    const phoneFilters = document.getElementById('phone-nav-filters');
    if (phoneFilters) {
      phoneFilters.textContent = t('filters');
    }
    const phoneMenu = document.getElementById('phone-nav-menu');
    if (phoneMenu) {
      phoneMenu.textContent = t('menu');
    }
    const tvActionBar = ui.tvActionBar;
    if (tvActionBar) {
      tvActionBar.setAttribute('aria-label', t('tvQuickActionsLabel'));
    }
    const tvChannels = document.getElementById('tv-action-channels');
    if (tvChannels) {
      tvChannels.textContent = t('subscriptions');
    }
    const tvFilters = document.getElementById('tv-action-filters');
    if (tvFilters) {
      tvFilters.textContent = t('filters');
    }
    const tvRefresh = document.getElementById('tv-action-refresh');
    if (tvRefresh) {
      tvRefresh.textContent = t('refresh');
    }
    const tvDisplay = document.getElementById('tv-action-display');
    if (tvDisplay) {
      tvDisplay.textContent = t('displayModeMenuLabel');
    }
    const sidebarClose = document.getElementById('channel-sidebar-close');
    if (sidebarClose) {
      sidebarClose.setAttribute('aria-label', t('close'));
    }
    if (ui.githubLabel) {
      ui.githubLabel.textContent = t('viewOnGitHub');
    }
    const issuesLabel = document.getElementById('issues-label');
    if (issuesLabel) {
      issuesLabel.textContent = t('reportIssue');
    }
    const currentUser = document.getElementById('current-user');
    if (currentUser) {
      currentUser.textContent = t('notSignedIn');
    }
    if (ui.sessionInfo) {
      ui.sessionInfo.classList.add('session-info--alert');
    }
    const menuToggleLabel = document.querySelector('#menu-toggle .sr-only');
    if (menuToggleLabel) {
      menuToggleLabel.textContent = t('openMenu');
    }
    if (ui.menuPanel) {
      ui.menuPanel.setAttribute('aria-label', t('menuLabel'));
    }

    const guideTitle = document.getElementById('guide-title');
    if (guideTitle) {
      guideTitle.textContent = t('categoryGuideTitle');
    }
    const guideIntro = document.getElementById('guide-intro');
    if (guideIntro) {
      guideIntro.textContent = t('categoryGuideIntro');
    }
    const guideSteps = document.getElementById('guide-steps');
    if (guideSteps) {
      const steps = [
        t('categoryGuideStep1'),
        t('categoryGuideStep2'),
        t('categoryGuideStep3'),
        t('categoryGuideStep4')
      ];
      guideSteps.innerHTML = steps.map(step => `<li>${step}</li>`).join('');
    }
  }

  (window.ytcvI18nReady || Promise.resolve()).then(() => {
    applyLocalizedCopy();
    markI18nReady();
  });

  function showNotification(message, type = 'info') {
    if (typeof window.showNotification === 'function') {
      window.showNotification(message, type);
      return;
    }

    // Fallback for environments without toast utilities.
    alert(message);
  }

  function openGuide() {
    if (!ui.guidePanel) {
      return;
    }
    ui.guidePanel.hidden = false;
    if (ui.guideClose) {
      ui.guideClose.focus();
    }
  }

  function closeGuide() {
    if (!ui.guidePanel) {
      return;
    }
    ui.guidePanel.hidden = true;
  }

  function setupGuide() {
    if (!ui.guidePanel) {
      return;
    }

    const onClose = () => closeGuide();

    if (ui.guideClose) {
      ui.guideClose.addEventListener('click', onClose);
    }

    ui.guidePanel.addEventListener('click', event => {
      if (event.target === ui.guidePanel) {
        onClose();
      }
    });

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !ui.guidePanel.hidden) {
        onClose();
      }
    });
  }

  function getTimezone() {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      return tz || 'UTC';
    } catch (error) {
      return 'UTC';
    }
  }

  function buildScheduleOptions(select) {
    if (!select) {
      return;
    }
    select.innerHTML = '';
    const offOption = document.createElement('option');
    offOption.value = 'off';
    offOption.textContent = t('off');
    select.appendChild(offOption);
    for (let hour = 0; hour < 24; hour += 1) {
      const option = document.createElement('option');
      option.value = String(hour);
      option.textContent = `${String(hour).padStart(2, '0')}:00`;
      select.appendChild(option);
    }
  }

  let confirmResolver = null;

  function closeConfirmModal(result) {
    if (!ui.confirmModal) {
      return;
    }
    ui.confirmModal.hidden = true;
    const resolver = confirmResolver;
    confirmResolver = null;
    if (resolver) {
      resolver(Boolean(result));
    }
  }

  function openConfirmModal(message) {
    if (!ui.confirmModal || !ui.confirmMessage) {
      return Promise.resolve(false);
    }
    ui.confirmMessage.textContent = message;
    ui.confirmModal.hidden = false;
    if (ui.confirmAccept) {
      ui.confirmAccept.focus();
    }
    return new Promise(resolve => {
      confirmResolver = resolve;
    });
  }

  function openSettingsModal() {
    if (!ui.settingsModal) {
      return;
    }
    if (state.currentUser) {
      loadSettings();
    }
    ui.settingsModal.hidden = false;
  }

  function closeSettingsModal() {
    if (!ui.settingsModal) {
      return;
    }
    ui.settingsModal.hidden = true;
  }

  function populateSettingsForm() {
    if (!state.settings) {
      return;
    }
    ui.presetRadios.forEach(radio => {
      const isActive = radio.value === state.settings.preset;
      radio.checked = isActive;
      const option = radio.closest('.preset-option');
      if (option) {
        option.classList.toggle('is-selected', isActive);
      }
    });
    const schedule = state.settings.schedule_hours || [];
    ui.scheduleSelects.forEach((select, idx) => {
      if (!select) {
        return;
      }
      const value = schedule[idx];
      select.value = value === null || typeof value === 'undefined' ? 'off' : String(value);
    });
    if (ui.quotaStatus && state.settings.quota) {
      const quota = state.settings.quota;
      ui.quotaStatus.textContent = t('quotaStatus', {
        used: quota.used,
        cap: quota.cap
      });
    }
    if (ui.backfillStatus) {
      ui.backfillStatus.textContent = state.settings.backfill_active
        ? t('backfillRunning')
        : '';
    }
  }

  async function loadSettings() {
    if (!state.currentUser || !api.getSettings) {
      return;
    }
    const response = await api.getSettings();
    if (!response.ok) {
      return;
    }
    state.settings = response.data;
    state.presets = response.data.presets || {};
    populateSettingsForm();
  }

  async function saveSettings() {
    if (!state.settings || !api.updateSettings) {
      return;
    }

    const selectedPreset = Array.from(ui.presetRadios).find(radio => radio.checked);
    const nextPreset = selectedPreset ? selectedPreset.value : state.settings.preset;
    const schedule = ui.scheduleSelects.map(select => {
      if (!select) {
        return null;
      }
      const value = select.value;
      return value === 'off' ? null : Number(value);
    });

    const presetChanged = nextPreset !== state.settings.preset;
    const scheduleChanged = JSON.stringify(schedule) !== JSON.stringify(state.settings.schedule_hours || []);
    const changed = presetChanged || scheduleChanged;

    if (!changed) {
      closeSettingsModal();
      return;
    }

    if (!(await openConfirmModal(t('settingsConfirm1')))) {
      return;
    }
    if (!(await openConfirmModal(t('settingsConfirm2')))) {
      return;
    }

    const payload = {
      preset: nextPreset,
      schedule_hours: schedule,
      timezone: getTimezone(),
      start_backfill: presetChanged,
      run_now: scheduleChanged
    };

    const response = await api.updateSettings(payload);
    if (!response.ok) {
      showNotification(response.error || t('settingsSaveFailed'), 'error');
      return;
    }
    await loadSettings();
    await loadApp();
    closeSettingsModal();
    showNotification(t('settingsSaved'), 'success');
  }

  function setupSettingsModal() {
    if (!ui.settingsModal) {
      return;
    }

    ui.scheduleSelects.forEach(select => buildScheduleOptions(select));
    ui.presetRadios.forEach(radio => {
      radio.addEventListener('change', () => {
        ui.presetRadios.forEach(node => {
          const option = node.closest('.preset-option');
          if (option) {
            option.classList.toggle('is-selected', node.checked);
          }
        });
      });
    });

    if (ui.settingsClose) {
      ui.settingsClose.addEventListener('click', closeSettingsModal);
    }
    if (ui.settingsCancel) {
      ui.settingsCancel.addEventListener('click', closeSettingsModal);
    }
    if (ui.settingsSave) {
      ui.settingsSave.addEventListener('click', saveSettings);
    }

    ui.settingsModal.addEventListener('click', event => {
      if (event.target === ui.settingsModal) {
        closeSettingsModal();
      }
    });

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && ui.settingsModal && !ui.settingsModal.hidden) {
        closeSettingsModal();
      }
    });
  }

  function setupConfirmModal() {
    if (!ui.confirmModal) {
      return;
    }

    if (ui.confirmAccept) {
      ui.confirmAccept.addEventListener('click', () => closeConfirmModal(true));
    }
    if (ui.confirmCancel) {
      ui.confirmCancel.addEventListener('click', () => closeConfirmModal(false));
    }
    if (ui.confirmClose) {
      ui.confirmClose.addEventListener('click', () => closeConfirmModal(false));
    }

    ui.confirmModal.addEventListener('click', event => {
      if (event.target === ui.confirmModal) {
        closeConfirmModal(false);
      }
    });

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && ui.confirmModal && !ui.confirmModal.hidden) {
        closeConfirmModal(false);
      }
    });
  }

  function setLoading(show, containerId) {
    if (typeof window.loadingSpinner === 'function') {
      window.loadingSpinner(show, containerId);
    }
  }

  function renderSectionLoadingState(container, messageKey = 'loadingContent') {
    if (!container) {
      return;
    }

    container.innerHTML = `
      <div class="section-loading" role="status" aria-live="polite">
        <span class="section-loading__text">${t(messageKey)}</span>
      </div>
    `;
  }

  function renderPrimaryLoadingStates() {
    renderSectionLoadingState(ui.latestCarousel, 'loadingVideos');
    if (ui.shortsSection) {
      ui.shortsSection.hidden = false;
    }
    renderSectionLoadingState(ui.shortsCarousel, 'loadingShorts');
    if (ui.olderSection) {
      ui.olderSection.hidden = false;
    }
    renderSectionLoadingState(ui.olderCarousel, 'loadingOlder');
  }

  function renderChannelListLoading() {
    if (!ui.channelList) {
      return;
    }
    ui.channelList.innerHTML = `
      <p class="channel-list__loading caption" role="status" aria-live="polite">
        ${t('loadingChannels')}
      </p>
    `;
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function reportImportStatus(message, type = 'info') {
    if (typeof window.setAuthStatus === 'function') {
      window.setAuthStatus(message, type);
      return;
    }

    if (message) {
      showNotification(message, type);
    }
  }

  function resolveHeaderMediaUrl(media) {
    if (!media || !media.url) {
      return '';
    }
    if (/^https?:\/\//.test(media.url)) {
      return media.url;
    }
    const configuredBase = window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL
      ? window.APP_CONFIG.API_BASE_URL.replace(/\/$/, '')
      : '';
    return configuredBase ? `${configuredBase}${media.url}` : media.url;
  }

  function updateHeaderContext() {
    if (!ui.headerContext || typeof window.buildHeaderContext !== 'function') {
      return;
    }

    const context = window.buildHeaderContext(
      state.channels,
      state.selectedChannelId,
      state.selectedChannelYtId,
      state.settings,
      t
    );

    if (ui.headerContextEyebrow) {
      ui.headerContextEyebrow.textContent = context.eyebrow || '';
    }
    if (ui.headerContextTitle) {
      ui.headerContextTitle.textContent = context.title || '';
    }
    if (ui.headerContextDescription) {
      ui.headerContextDescription.textContent = context.description || '';
    }

    if (ui.headerContextMetrics) {
      ui.headerContextMetrics.innerHTML = '';
      (context.metrics || []).slice(0, 4).forEach(metric => {
        const wrapper = document.createElement('div');
        wrapper.className = 'header-context__metric';

        const title = document.createElement('dt');
        title.textContent = metric.label || '';

        const value = document.createElement('dd');
        value.textContent = metric.value || '';

        wrapper.appendChild(title);
        wrapper.appendChild(value);
        ui.headerContextMetrics.appendChild(wrapper);
      });
    }

    if (ui.headerContextMedia && ui.headerContextImage) {
      const resolvedUrl = resolveHeaderMediaUrl(context.media);
      if (resolvedUrl) {
        ui.headerContextMedia.hidden = false;
        ui.headerContextImage.src = resolvedUrl;
        ui.headerContextImage.alt = context.media.alt || '';
      } else {
        ui.headerContextMedia.hidden = true;
        ui.headerContextImage.removeAttribute('src');
        ui.headerContextImage.alt = '';
      }
    }
  }

  function setRefreshProgress(message, status = 'running') {
    state.refreshProgress = message
      ? {
          message,
          status
        }
      : null;

    if (!ui.refreshProgress) {
      return;
    }

    if (!message) {
      ui.refreshProgress.hidden = true;
      ui.refreshProgress.textContent = '';
      ui.refreshProgress.removeAttribute('data-state');
      return;
    }

    ui.refreshProgress.hidden = false;
    ui.refreshProgress.textContent = message;
    ui.refreshProgress.setAttribute('data-state', status);
  }

  function updateRefreshProgressFromEvent(payload) {
    if (!payload || !payload.type) {
      return;
    }

    if (payload.type === 'stream_opened' || payload.type === 'start') {
      setRefreshProgress(t('refreshProgressWaiting'));
      return;
    }

    if (payload.type === 'channel_started') {
      const total = payload.total_channels || '?';
      const current = payload.current_channel || 0;
      const title = payload.channel_title || t('unknownChannel');
      setRefreshProgress(t('refreshProgressChannels', { current, total, title }));
      return;
    }

    if (payload.type === 'complete') {
      setRefreshProgress(
        t('refreshProgressDone', { count: payload.new_videos || 0 }),
        'complete'
      );
      window.setTimeout(() => {
        if (state.refreshProgress && state.refreshProgress.status === 'complete') {
          setRefreshProgress('');
        }
      }, 2500);
      return;
    }

    if (payload.type === 'blocked') {
      const helper = window.ytcvRefreshGovernance;
      if (payload.reason === 'refresh_in_progress') {
        setRefreshProgress(
          helper ? helper.getBlockedProgressMessage(t, payload) : t('refreshProgressAlreadyRunning'),
          'warning'
        );
      } else {
        setRefreshProgress(
          helper ? helper.getBlockedProgressMessage(t, payload) : t('refreshProgressCooldown', { minutes: 1 }),
          'warning'
        );
      }
      window.setTimeout(() => {
        if (state.refreshProgress && state.refreshProgress.status === 'warning') {
          setRefreshProgress('');
        }
      }, 4000);
    }
  }

  function buildRefreshStreamUrl(channelId = null, backfill = false) {
    const configuredBaseUrl = (api && api.baseURL) || ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || '');
    const baseUrl = configuredBaseUrl.endsWith('/api')
      ? configuredBaseUrl
      : `${configuredBaseUrl}/api`;
    const params = new URLSearchParams();
    if (channelId !== null && channelId !== undefined) {
      params.set('channel_id', String(channelId));
    }
    if (backfill) {
      params.set('backfill', 'true');
    }
    const query = params.toString();
    return `${baseUrl}/channels/refresh/stream${query ? `?${query}` : ''}`;
  }

  function streamRefresh(channelId = null, options = {}) {
    const {
      backfill = false,
      onProgress = null,
      onComplete = null,
      onError = null
    } = options;

    return new Promise((resolve, reject) => {
      if (typeof window.EventSource !== 'function') {
        reject(new Error('SSE not supported'));
        return;
      }

      const source = new window.EventSource(buildRefreshStreamUrl(channelId, backfill), {
        withCredentials: true
      });
      let finished = false;

      const close = () => {
        source.close();
      };

      source.addEventListener('refresh', async event => {
        let payload = null;
        try {
          payload = JSON.parse(event.data);
        } catch (error) {
          return;
        }

        if (typeof onProgress === 'function') {
          await onProgress(payload);
        }

        if (payload.type === 'complete' || payload.type === 'blocked') {
          finished = true;
          close();
          if (typeof onComplete === 'function') {
            await onComplete(payload);
          }
          resolve(payload);
        }
      });

      source.onerror = async () => {
        close();
        const error = new Error('Refresh stream failed');
        setRefreshProgress(t('refreshProgressError'), 'error');
        if (!finished && typeof onError === 'function') {
          await onError(error);
        }
        reject(error);
      };
    });
  }

  function applyFilters(payload) {
    if (!payload || !Array.isArray(payload.videos)) {
      return payload;
    }

    const filtered = payload.videos.filter(item => {
      if (state.selectedChannelId !== null || state.selectedChannelYtId) {
        const channelId = item.channel && item.channel.id
          ? item.channel.id
          : item.video && item.video.channel_id
            ? item.video.channel_id
            : null;
        const ytChannelId = item.channel && item.channel.yt_channel_id
          ? item.channel.yt_channel_id
          : null;
        const matchesId = state.selectedChannelId !== null
          && String(channelId) === String(state.selectedChannelId);
        const matchesYt = Boolean(state.selectedChannelYtId)
          && ytChannelId
          && ytChannelId === state.selectedChannelYtId;
        if (!matchesId && !matchesYt) {
          return false;
        }
      }

      if (state.filters.unwatched && item.watched) {
        return false;
      }

      const published = item.video && item.video.published_at ? new Date(item.video.published_at) : null;
      if (published && !Number.isNaN(published.getTime())) {
        const days = Math.floor((Date.now() - published.getTime()) / (1000 * 60 * 60 * 24));
      if (state.filters.month && days > 30) {
        return false;
      }
      }

      return true;
    });

    return { ...payload, videos: filtered };
  }

  function clearCarousels(preserveDOM = false) {
    state.carousels.forEach(carousel => carousel.destroy(preserveDOM));
    state.carousels = [];

    if (!preserveDOM && ui.inProgressCarousel) {
      ui.inProgressCarousel.innerHTML = '';
    }
    if (ui.inProgressSection) {
      ui.inProgressSection.hidden = true;
    }
    if (!preserveDOM && ui.latestCarousel) {
      ui.latestCarousel.innerHTML = '';
    }
    if (!preserveDOM && ui.shortsCarousel) {
      ui.shortsCarousel.innerHTML = '';
    }
    if (!preserveDOM && ui.olderCarousel) {
      ui.olderCarousel.innerHTML = '';
    }
    if (!preserveDOM && ui.themeCarousels) {
      ui.themeCarousels.innerHTML = '';
    }
  }

  async function renderInProgressCarousel() {
    if (!ui.inProgressCarousel || !ui.inProgressSection) {
      return;
    }

    let totalCount = 0;
    const carousel = new window.Carousel('in-progress-carousel', async (offset, limit) => {
      const response = await api.getInProgressVideos(limit, offset);
      if (!response.ok) {
        return { videos: [], has_more: false, next_offset: null };
      }
      const data = response.data;
      if (offset === 0) {
        totalCount = data.videos.length;
      } else {
        totalCount += data.videos.length;
      }
      return data;
    }, { preserveContentOnInit: true });

    await carousel.init();
    state.carousels.push(carousel);

    if (totalCount > 0) {
      ui.inProgressSection.hidden = false;
      if (ui.inProgressCount) {
        ui.inProgressCount.textContent = totalCount;
      }
    } else {
      ui.inProgressSection.hidden = true;
    }
  }

  async function renderMainCarousel() {
    if (!ui.latestCarousel) {
      return;
    }

    const carousel = new window.Carousel('latest-carousel', async (offset, limit) => {
      const params = {
        content_type: 'video',
        since_days: 7,
        only_unwatched: state.selectedChannelId === null && !state.selectedChannelYtId
      };
      if (state.selectedChannelId !== null) {
        params.channel_id = state.selectedChannelId;
      }
      if (state.selectedChannelYtId) {
        params.yt_channel_id = state.selectedChannelYtId;
      }
      const response = await api.getLatestVideos(limit, offset, params);
      if (!response.ok) {
        return { videos: [], has_more: false, next_offset: null };
      }
      return applyFilters(response.data);
    }, { preserveContentOnInit: true });

    await carousel.init();
    state.carousels.push(carousel);
  }

  async function renderShortsCarousel() {
    if (!ui.shortsCarousel) {
      return;
    }

    const carousel = new window.Carousel('shorts-carousel', async (offset, limit) => {
      const params = {
        content_type: 'short',
        since_days: 7,
        only_unwatched: state.selectedChannelId === null && !state.selectedChannelYtId
      };
      if (state.selectedChannelId !== null) {
        params.channel_id = state.selectedChannelId;
      }
      if (state.selectedChannelYtId) {
        params.yt_channel_id = state.selectedChannelYtId;
      }
      const response = await api.getLatestVideos(limit, offset, params);
      if (!response.ok) {
        return { videos: [], has_more: false, next_offset: null };
      }
      return applyFilters(response.data);
    }, {
      showTitle: false,
      showDescription: false,
      preserveContentOnInit: true
    });

    await carousel.init();
    state.carousels.push(carousel);
  }

  async function renderOlderCarousel() {
    if (!ui.olderCarousel) {
      return;
    }

    const carousel = new window.Carousel('older-carousel', async (offset, limit) => {
      const params = {
        older_than_days: 7,
        since_days: 30,
        randomize: true,
        only_unwatched: state.selectedChannelId === null && !state.selectedChannelYtId
      };
      if (state.selectedChannelId !== null) {
        params.channel_id = state.selectedChannelId;
      }
      if (state.selectedChannelYtId) {
        params.yt_channel_id = state.selectedChannelYtId;
      }
      const response = await api.getLatestVideos(limit, offset, params);
      if (!response.ok) {
        return { videos: [], has_more: false, next_offset: null };
      }
      return applyFilters(response.data);
    }, {
      hideTextForShorts: true,
      preserveContentOnInit: true
    });

    await carousel.init();
    state.carousels.push(carousel);
  }

  function renderChannelList(channels) {
    if (!ui.channelList) {
      return;
    }

    ui.channelList.innerHTML = '';
    syncChannelSearchUI();

    const allItem = document.createElement('div');
    allItem.className = 'channel-item';
    allItem.setAttribute('role', 'listitem');
    allItem.dataset.channelId = '';
    allItem.dataset.ytChannelId = '';
    allItem.innerHTML = `
      <div class="channel-item__thumb">${t('allChannels').toUpperCase()}</div>
      <span class="channel-item__name">${t('allChannels')}</span>
    `;
    ui.channelList.appendChild(allItem);

    const sorted = [...(channels || [])].sort((a, b) => {
      const nameA = (a.title || '').toLowerCase();
      const nameB = (b.title || '').toLowerCase();
      return nameA.localeCompare(nameB);
    });

    const channelMatchesFilters = channel => {
      const monthFilter = state.filters.month;
      const unwatchedFilter = state.filters.unwatched;

      const recent7 = Number(channel.recent_total_7 || 0);
      const recent7Unwatched = Number(channel.recent_unwatched_7 || 0);
      const recent30 = Number(channel.recent_total_30 || 0);
      const recent30Unwatched = Number(channel.recent_unwatched_30 || 0);
      const totalUnwatched = Number(channel.unwatched_total || 0);

      if (monthFilter) {
        return unwatchedFilter ? recent30Unwatched > 0 : recent30 > 0;
      }
      if (unwatchedFilter) {
        return recent7Unwatched > 0;
      }
      return true;
    };

    if (!sorted.length) {
      const empty = document.createElement('p');
      empty.className = 'caption';
      empty.textContent = t('noSubscriptions');
      ui.channelList.appendChild(empty);
    }

    const sidebarFiltered = sorted.length
      ? (
          typeof window.filterChannelsForSidebar === 'function'
            ? window.filterChannelsForSidebar(sorted, state.channelFilterQuery)
            : sorted
        )
      : [];
    const filtered = sidebarFiltered.length ? sidebarFiltered.filter(channelMatchesFilters) : [];

    if (sorted.length && !filtered.length) {
      const empty = document.createElement('p');
      empty.className = 'caption';
      empty.textContent = state.channelFilterQuery
        ? t('noChannelsSearchMatch')
        : t('noChannelsMatch');
      ui.channelList.appendChild(empty);
    }

    const buildInitials = value => {
      const safe = (value || '').trim();
      if (!safe) {
        return '?';
      }
      const parts = safe.split(/\s+/).filter(Boolean);
      const initials = parts.slice(0, 2).map(part => part[0]).join('');
      return (initials || safe[0] || '?').toUpperCase();
    };

    const buildPlaceholder = channel => {
      const thumb = document.createElement('div');
      thumb.className = 'channel-item__thumb';
      thumb.textContent = buildInitials(channel.title || channel.yt_channel_id);
      return thumb;
    };

    const buildThumbnail = channel => {
      const baseUrl = window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL
        ? window.APP_CONFIG.API_BASE_URL.replace(/\/$/, '')
        : '';
      const localUrl = channel.thumbnail_local_url && baseUrl
        ? `${baseUrl}${channel.thumbnail_local_url}`
        : null;
      const sourceUrl = localUrl || channel.thumbnail_url;

      if (!sourceUrl) {
        return buildPlaceholder(channel);
      }

      const thumb = document.createElement('div');
      thumb.className = 'channel-item__thumb';

      const img = document.createElement('img');
      img.className = 'channel-item__thumb-image';
      img.src = sourceUrl;
      img.alt = channel.title || t('channelThumbnailAlt');
      img.loading = 'lazy';
      img.addEventListener('error', () => {
        const placeholder = buildPlaceholder(channel);
        thumb.replaceWith(placeholder);
      });

      thumb.appendChild(img);
      return thumb;
    };

    filtered.forEach(channel => {
      const item = document.createElement('div');
      item.className = 'channel-item';
      item.setAttribute('role', 'listitem');
      item.dataset.channelId = String(channel.id);
      item.dataset.ytChannelId = channel.yt_channel_id || '';

      item.appendChild(buildThumbnail(channel));

      const name = document.createElement('span');
      name.className = 'channel-item__name';
      name.textContent = channel.title || channel.yt_channel_id || t('unknownChannel');
      item.appendChild(name);

      const meta = document.createElement('div');
      meta.className = 'channel-item__meta';

      if (typeof window.createCategoryBadge === 'function') {
        const categoryData = channel.category && channel.category.category
          ? channel.category.category
          : null;
        const badge = window.createCategoryBadge(categoryData, () => {
          if (!state.categorySelector) {
            return;
          }
          state.categorySelector.open(
            channel.id,
            channel.title,
            categoryData ? categoryData.id : null
          );
        });
        badge.classList.add('channel-item__category');
        meta.appendChild(badge);
      }

      const status = document.createElement('span');
      status.className = 'channel-item__status';
      if (Number(channel.recent_total_7 || 0) > 0) {
        status.classList.add('is-active');
      }
      status.setAttribute('aria-hidden', 'true');
      meta.appendChild(status);

      item.appendChild(meta);

      ui.channelList.appendChild(item);
    });

    ui.channelList.querySelectorAll('.channel-item').forEach(item => {
      const id = item.dataset.channelId || null;
      const ytId = item.dataset.ytChannelId || null;
      const isAllSelected = state.selectedChannelId === null && !state.selectedChannelYtId;
      const matchesId = state.selectedChannelId !== null && String(state.selectedChannelId) === id;
      const matchesYt = state.selectedChannelYtId && ytId === state.selectedChannelYtId;
      if ((isAllSelected && !id) || matchesId || matchesYt) {
        item.classList.add('is-active');
      }
      item.tabIndex = 0;
      item.setAttribute('role', 'button');
      item.setAttribute('aria-pressed', item.classList.contains('is-active') ? 'true' : 'false');
      item.addEventListener('click', () => {
        const rawId = item.dataset.channelId;
        const parsedId = rawId ? Number(rawId) : null;
        const nextId = Number.isFinite(parsedId) ? parsedId : null;
        const nextYtId = item.dataset.ytChannelId || null;
        state.selectedChannelId = nextId;
        state.selectedChannelYtId = nextYtId || null;
        ui.channelList.querySelectorAll('.channel-item').forEach(node => {
          const nodeId = node.dataset.channelId || null;
          const nodeYtId = node.dataset.ytChannelId || null;
          const allSelected = state.selectedChannelId === null && !state.selectedChannelYtId;
          const idSelected = state.selectedChannelId !== null
            && String(state.selectedChannelId) === nodeId;
          const ytSelected = state.selectedChannelYtId && nodeYtId === state.selectedChannelYtId;
          node.classList.toggle(
            'is-active',
            (allSelected && !nodeId) || idSelected || ytSelected
          );
          node.setAttribute('aria-pressed', node.classList.contains('is-active') ? 'true' : 'false');
        });
        updateHeaderContext();
        updateVideoCounts();
        if (state.searchActive) {
          runSearch(state.searchQuery);
        } else {
          reloadCarousels();
        }
      });
      item.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          item.click();
        }
      });
    });
  }

  function prefetchChannelThumbnails(channels) {
    if (!Array.isArray(channels) || !channels.length) {
      return;
    }

    const baseUrl = window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL
      ? window.APP_CONFIG.API_BASE_URL.replace(/\/$/, '')
      : '';

    const queue = channels
      .filter(channel => channel.thumbnail_local_url && !state.prefetchedThumbnails.has(channel.id))
      .map(channel => ({
        id: channel.id,
        url: baseUrl ? `${baseUrl}${channel.thumbnail_local_url}` : channel.thumbnail_local_url
      }))
      .filter(item => item.url);

    if (!queue.length) {
      return;
    }

    let index = 0;
    let active = 0;
    const concurrency = 4;

    const loadNext = () => {
      while (active < concurrency && index < queue.length) {
        const item = queue[index++];
        state.prefetchedThumbnails.add(item.id);
        active += 1;

        const img = new Image();
        img.onload = () => {
          active -= 1;
          loadNext();
        };
        img.onerror = () => {
          active -= 1;
          loadNext();
        };
        img.src = item.url;
      }
    };

    loadNext();
  }

  function updateChannelCount(channels) {
    if (!ui.channelCount) {
      return;
    }

    const count = Array.isArray(channels) ? channels.length : 0;
    ui.channelCount.textContent = String(count);
  }

  async function updateVideoCounts() {
    if (!ui.videosCount && !ui.shortsCount) {
      return;
    }

    const response = await api.getVideoSummary(
      7,
      state.selectedChannelId,
      state.selectedChannelYtId
    );
    if (!response.ok || !response.data) {
      return;
    }

    const videos = typeof response.data.videos === 'number' ? response.data.videos : 0;
    const shorts = typeof response.data.shorts === 'number' ? response.data.shorts : 0;

    if (ui.videosCount) {
      ui.videosCount.textContent = String(videos);
    }
    if (ui.shortsCount) {
      ui.shortsCount.textContent = String(shorts);
    }
  }

  function updateLastUpdatedLabel(channels) {
    if (!ui.lastUpdatedLabel) {
      return;
    }

    const timestamps = (channels || [])
      .map(channel => channel.last_checked_at || channel.last_refreshed_at)
      .filter(Boolean)
      .map(value => new Date(value))
      .filter(date => !Number.isNaN(date.getTime()));

    if (state.settings && state.settings.last_schedule_run_at) {
      const scheduleDate = new Date(state.settings.last_schedule_run_at);
      if (!Number.isNaN(scheduleDate.getTime())) {
        timestamps.push(scheduleDate);
      }
    }

    if (!timestamps.length) {
      ui.lastUpdatedLabel.textContent = t('lastUpdatedNone');
      return;
    }

    timestamps.sort((a, b) => b.getTime() - a.getTime());
    const latest = timestamps[0];
    const relative = typeof window.timeAgo === 'function' ? window.timeAgo(latest.toISOString()) : '';
    ui.lastUpdatedLabel.textContent = relative
      ? t('lastUpdatedRelative', { relative })
      : t('lastUpdatedAbsolute', { date: latest.toLocaleString() });
  }

  function getLatestCheckedAt(channels) {
    const timestamps = (channels || [])
      .map(channel => channel.last_checked_at || channel.last_refreshed_at)
      .filter(Boolean)
      .map(value => new Date(value))
      .filter(date => !Number.isNaN(date.getTime()));

    if (state.settings && state.settings.last_schedule_run_at) {
      const scheduleDate = new Date(state.settings.last_schedule_run_at);
      if (!Number.isNaN(scheduleDate.getTime())) {
        timestamps.push(scheduleDate);
      }
    }

    if (!timestamps.length) {
      return null;
    }

    timestamps.sort((a, b) => b.getTime() - a.getTime());
    return timestamps[0];
  }

  async function syncChannelsState() {
    const channelsResponse = await api.getChannels();
    if (channelsResponse.ok) {
      state.channels = channelsResponse.data || [];
    }
    return state.channels;
  }

  async function syncVisibleStateAfterRefresh() {
    await syncChannelsState();
    renderChannelList(state.channels);
    updateChannelCount(state.channels);
    updateLastUpdatedLabel(state.channels);
    updateHeaderContext();
    await updateVideoCounts();

    if (state.searchActive) {
      await runSearch(state.searchQuery);
      state.initialContentReady = true;
      return;
    }

    await reloadCarousels();
    state.initialContentReady = true;
  }

  function startAutoRefresh(channelId = null, options = {}) {
    const {
      keepLoadingState = false,
      onComplete = null,
      onError = null
    } = options;

    if (state.autoRefreshPromise) {
      return state.autoRefreshPromise;
    }

    state.autoRefreshAttempted = true;
    state.autoRefreshKeepsLoadingState = keepLoadingState;
    showNotification(t('refreshInProgress'), 'info');
    setRefreshProgress(t('refreshProgressWaiting'));

    state.autoRefreshPromise = streamRefresh(channelId, {
      onProgress: async payload => {
        updateRefreshProgressFromEvent(payload);
        if (
          !keepLoadingState
          && state.initialContentReady
          && payload.type === 'channel_complete'
          && payload.channel_new_videos > 0
        ) {
          scheduleVisibleReload();
        }
      }
    })
      .then(async payload => {
        if (payload && payload.type === 'complete') {
          await syncChannelsState();
          if (keepLoadingState || !state.initialContentReady) {
            await syncVisibleStateAfterRefresh();
          }
        }
        if (typeof onComplete === 'function') {
          await onComplete(payload);
        }
        return payload;
      })
      .catch(async error => {
        if (typeof onError === 'function') {
          await onError(error);
        }
        return null;
      })
      .finally(() => {
        state.autoRefreshPromise = null;
        state.autoRefreshKeepsLoadingState = false;
      });

    return state.autoRefreshPromise;
  }

  async function loadApp() {
    if (!state.currentUser) {
      return;
    }

    state.initialContentReady = false;
    setLoading(true, 'latest-carousel');
    renderChannelListLoading();
    renderPrimaryLoadingStates();

    await syncChannelsState();

    if (
      state.currentUser.auth_provider === 'google'
      && state.channels.length === 0
      && !state.autoImportAttempted
    ) {
      state.autoImportAttempted = true;
      await importSubscriptions(false);
      await syncChannelsState();
    }

    renderChannelList(state.channels);
    updateChannelCount(state.channels);
    updateLastUpdatedLabel(state.channels);
    updateHeaderContext();
    await updateVideoCounts();
    prefetchChannelThumbnails(state.channels);

    const latestCheckedAt = getLatestCheckedAt(state.channels);
    const shouldAutoRefreshFromEmptyState = (
      state.currentUser.auth_provider === 'google'
      && state.channels.length > 0
      && !latestCheckedAt
    );
    const shouldAutoRefreshFromStaleState = latestCheckedAt
      ? Date.now() - latestCheckedAt.getTime() > AUTO_REFRESH_STALE_HOURS * 60 * 60 * 1000
      : false;

    if (!state.autoRefreshAttempted && shouldAutoRefreshFromEmptyState) {
      startAutoRefresh(null, { keepLoadingState: true });
      setLoading(false, 'latest-carousel');
      return;
    }

    clearCarousels();
    await renderInProgressCarousel();
    await renderMainCarousel();
    state.initialContentReady = true;

    deferredTask(async () => {
      if (ui.shortsSection) {
        ui.shortsSection.hidden = false;
      }
      await renderShortsCarousel();

      if (ui.olderSection) {
        ui.olderSection.hidden = false;
      }
      await renderOlderCarousel();

      if (typeof window.CategoryManager === 'function' && ui.categoryCarousels) {
        state.categoryManager = new window.CategoryManager(api, 'category-carousels');
        await state.categoryManager.init();
        if (ui.categoriesSection) {
          ui.categoriesSection.hidden = false;
        }
      }
    });

    setLoading(false, 'latest-carousel');

    if (!state.autoRefreshAttempted && shouldAutoRefreshFromStaleState) {
      startAutoRefresh(null);
    }
  }

  async function reloadCarousels() {
    clearCarousels(true);
    await renderInProgressCarousel();
    await renderMainCarousel();
    await renderShortsCarousel();
    await renderOlderCarousel();

    // Ocultar categorías automáticas cuando hay un canal seleccionado.
    // Solo se muestran cuando no hay canal activo (vista "All").
    if (ui.categoriesSection) {
      ui.categoriesSection.hidden = state.selectedChannelId !== null;
    }
  }

  let refreshVisibleTimer = null;
  function scheduleVisibleReload() {
    if (state.searchActive || !state.initialContentReady) {
      return;
    }
    if (refreshVisibleTimer) {
      window.clearTimeout(refreshVisibleTimer);
    }
    refreshVisibleTimer = window.setTimeout(async () => {
      refreshVisibleTimer = null;
      await reloadCarousels();
    }, 700);
  }

  function setupFilters() {
    const updateButtons = () => {
      if (ui.filterUnwatched) {
        ui.filterUnwatched.classList.toggle('is-active', state.filters.unwatched);
        ui.filterUnwatched.setAttribute('aria-pressed', state.filters.unwatched ? 'true' : 'false');
      }
      if (ui.filterMonth) {
        ui.filterMonth.classList.toggle('is-active', state.filters.month);
        ui.filterMonth.setAttribute('aria-pressed', state.filters.month ? 'true' : 'false');
      }
    };

    const applyFiltersNow = () => {
      renderChannelList(state.channels);
      if (state.searchActive) {
        runSearch(state.searchQuery);
      } else {
        reloadCarousels();
      }
    };

    if (ui.filterUnwatched) {
      ui.filterUnwatched.addEventListener('click', () => {
        const next = !state.filters.unwatched;
        state.filters.unwatched = next;
        if (next) {
          state.filters.month = false;
        }
        updateButtons();
        applyFiltersNow();
      });
    }

    if (ui.filterMonth) {
      ui.filterMonth.addEventListener('click', () => {
        const next = !state.filters.month;
        state.filters.month = next;
        if (next) {
          state.filters.unwatched = false;
        }
        updateButtons();
        applyFiltersNow();
      });
    }

    updateButtons();
  }

  function clearSearch() {
    state.searchActive = false;
    state.searchQuery = '';
    if (ui.searchInput) {
      ui.searchInput.value = '';
    }
    renderChannelList(state.channels);

    if (ui.videosLabel) {
      ui.videosLabel.textContent = t('videos');
    }
    if (ui.videosCount) {
      ui.videosCount.hidden = false;
    }


    reloadCarousels();
  }

  async function runSearch(query) {
    const trimmed = (query || '').trim();
    if (!trimmed) {
      clearSearch();
      return;
    }

    state.searchActive = true;
    state.searchQuery = trimmed;
    renderChannelList(state.channels);

    if (ui.videosLabel) {
      ui.videosLabel.textContent = t('searchResults', { query: trimmed });
    }
    if (ui.videosCount) {
      ui.videosCount.hidden = true;
    }

    if (ui.shortsSection) {
      ui.shortsSection.hidden = true;
    }
    if (ui.olderSection) {
      ui.olderSection.hidden = true;
    }

    clearCarousels();

    const carousel = new window.Carousel('latest-carousel', async (offset, limit) => {
      const filters = { limit, offset };
      if (state.selectedChannelId !== null) {
        filters.channel_id = state.selectedChannelId;
      }
      if (state.selectedChannelYtId) {
        filters.yt_channel_id = state.selectedChannelYtId;
      }

      const response = await api.searchVideos(trimmed, filters);
      if (!response.ok) {
        return { videos: [], has_more: false, next_offset: null };
      }
      return applyFilters(response.data);
    }, { hideTextForShorts: true });

    await carousel.init();
    state.carousels.push(carousel);
  }

  function setupSearch() {
    const handleSearch = () => {
      const query = ui.searchInput ? ui.searchInput.value : '';
      runSearch(query);
    };

    const debounced = typeof window.debounce === 'function'
      ? window.debounce(handleSearch, 300)
      : handleSearch;

    if (ui.searchInput) {
      ui.searchInput.addEventListener('input', debounced);
    }

  }

  function syncChannelSearchUI() {
    if (ui.channelSearchInput && ui.channelSearchInput.value !== state.channelFilterQuery) {
      ui.channelSearchInput.value = state.channelFilterQuery;
    }
    if (ui.channelSearchClear) {
      ui.channelSearchClear.hidden = !state.channelFilterQuery;
    }
  }

  function clearChannelSearch(options = {}) {
    const { focusInput = false } = options;
    state.channelFilterQuery = '';
    syncChannelSearchUI();
    renderChannelList(state.channels);
    if (focusInput && ui.channelSearchInput) {
      ui.channelSearchInput.focus();
    }
  }

  function setupChannelSidebarSearch() {
    if (!ui.channelSearchInput) {
      return;
    }

    const applySidebarSearch = query => {
      state.channelFilterQuery = typeof window.normalizeSidebarQuery === 'function'
        ? window.normalizeSidebarQuery(query)
        : String(query || '').trim().toLowerCase();
      syncChannelSearchUI();
      renderChannelList(state.channels);
    };

    ui.channelSearchInput.addEventListener('input', event => {
      applySidebarSearch(event.target.value);
    });

    ui.channelSearchInput.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        clearChannelSearch({ focusInput: true });
      }
    });

    if (ui.channelSearchClear) {
      ui.channelSearchClear.addEventListener('click', () => {
        clearChannelSearch({ focusInput: true });
      });
    }

    syncChannelSearchUI();
  }

  function setupMenu() {
    if (!ui.menuToggle || !ui.menuPanel) {
      return;
    }

    const setMenuOpen = isOpen => {
      ui.menuPanel.hidden = !isOpen;
      ui.menuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      if (isOpen) {
        const firstAction = ui.menuPanel.querySelector('button:not([hidden])');
        if (firstAction) {
          firstAction.focus();
        }
      }
    };
    state.setMenuOpen = setMenuOpen;

    ui.menuToggle.addEventListener('click', event => {
      event.stopPropagation();
      const isOpen = ui.menuPanel.hidden;
      setMenuOpen(isOpen);
    });

    document.addEventListener('click', event => {
      if (ui.menuPanel.hidden) {
        return;
      }
      if (ui.menuPanel.contains(event.target) || ui.menuToggle.contains(event.target)) {
        return;
      }
      setMenuOpen(false);
    });

    if (ui.menuFilters) {
      ui.menuFilters.addEventListener('click', () => {
        setMenuOpen(false);
        openFilterPanel();
      });
    }

    if (ui.menuCategoryGuide) {
      ui.menuCategoryGuide.addEventListener('click', () => {
        setMenuOpen(false);
        openGuide();
      });
    }

    if (ui.menuSettings) {
      ui.menuSettings.addEventListener('click', () => {
        setMenuOpen(false);
        openSettingsModal();
      });
    }

    if (ui.myAccountButton) {
      ui.myAccountButton.addEventListener('click', () => {
        setMenuOpen(false);
        if (window.ytcvAccountPanel) {
          window.ytcvAccountPanel.open('profile');
        }
      });
    }

    const updateMenuAuth = user => {
      if (ui.myAccountButton) {
        ui.myAccountButton.hidden = !user;
      }
      if (ui.logoutButton) {
        ui.logoutButton.hidden = !user;
      }
      if (ui.refreshButton) {
        ui.refreshButton.hidden = !user;
      }
      if (ui.menuSettings) {
        ui.menuSettings.hidden = !user;
      }
    };

    updateMenuAuth(state.currentUser);
    window.addEventListener('auth:changed', event => {
      const user = event.detail ? event.detail.user : null;
      updateMenuAuth(user);
    });
  }

  function setupLanguageMenu() {
    if (!ui.languageButtons || ui.languageButtons.length === 0) {
      return;
    }

    const current = window.ytcvI18n ? window.ytcvI18n.language : 'en';
    ui.languageButtons.forEach(button => {
      const lang = button.dataset.lang;
      button.classList.toggle('is-active', lang === current);
      button.addEventListener('click', () => {
        try {
          localStorage.setItem('ytcv_lang', lang);
        } catch (error) {
          // Ignore storage errors.
        }
        window.location.reload();
      });
    });
  }

  function setupFilterPanel() {
    if (!ui.filterPanel) {
      return;
    }

    const header = ui.filterPanel.querySelector('.filter-panel__header');
    const panel = ui.filterPanel;
    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let originX = 0;
    let originY = 0;

    const clamp = () => {
      const rect = panel.getBoundingClientRect();
      const maxX = window.innerWidth - rect.width;
      const maxY = window.innerHeight - rect.height;
      const nextX = Math.min(Math.max(rect.left, 8), Math.max(maxX, 8));
      const nextY = Math.min(Math.max(rect.top, 8), Math.max(maxY, 8));
      panel.style.left = `${nextX}px`;
      panel.style.top = `${nextY}px`;
    };

    const onMouseMove = event => {
      if (!isDragging) {
        return;
      }
      panel.style.left = `${originX + (event.clientX - startX)}px`;
      panel.style.top = `${originY + (event.clientY - startY)}px`;
    };

    const onMouseUp = () => {
      if (!isDragging) {
        return;
      }
      isDragging = false;
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      clamp();
    };

    if (header) {
      header.addEventListener('mousedown', event => {
        if (event.button !== 0) {
          return;
        }
        if (event.target && typeof event.target.closest === 'function' && event.target.closest('button')) {
          return;
        }
        isDragging = true;
        const rect = panel.getBoundingClientRect();
        startX = event.clientX;
        startY = event.clientY;
        originX = rect.left;
        originY = rect.top;
        panel.style.right = 'auto';
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      });
    }

    window.addEventListener('resize', clamp);

    if (ui.filterPanelClose) {
      ui.filterPanelClose.addEventListener('click', () => {
        panel.hidden = true;
        if (ui.menuFilters) {
          ui.menuFilters.focus();
        }
      });
    }

    if (ui.filterPanelClear) {
      ui.filterPanelClear.addEventListener('click', () => {
        state.filters.unwatched = false;
        state.filters.month = false;
        if (ui.filterUnwatched) {
          ui.filterUnwatched.classList.remove('is-active');
          ui.filterUnwatched.setAttribute('aria-pressed', 'false');
        }
        if (ui.filterMonth) {
          ui.filterMonth.classList.remove('is-active');
          ui.filterMonth.setAttribute('aria-pressed', 'false');
        }
        clearSearch();
      });
    }
  }

  function openFilterPanel() {
    if (!ui.filterPanel) {
      return;
    }

    ui.filterPanel.hidden = false;
    if (ui.searchInput) {
      ui.searchInput.focus();
    }
  }

  function setupKeyboardNavigation() {
    document.addEventListener('keydown', event => {
      const isArrow = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key);
      if (!isArrow) {
        return;
      }

      const active = document.activeElement;
      const isTypingTarget = active && (
        active.tagName === 'INPUT'
        || active.tagName === 'TEXTAREA'
        || active.tagName === 'SELECT'
        || active.isContentEditable
      );

      if (isTypingTarget) {
        return;
      }

      const directionMap = {
        ArrowLeft: 'left',
        ArrowRight: 'right',
        ArrowUp: 'up',
        ArrowDown: 'down'
      };

      const nextElement = getDirectionalCandidate(active, directionMap[event.key]);
      if (!nextElement) {
        return;
      }

      event.preventDefault();
      nextElement.focus();
      nextElement.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
        inline: 'nearest'
      });
    });
  }

  function setupRefresh() {
    if (!ui.refreshButton) {
      return;
    }

    ui.refreshButton.addEventListener('click', async () => {
      const targetChannelId = state.selectedChannelId !== null ? state.selectedChannelId : null;
      reportImportStatus(t('refreshInProgress'), 'info');
      setRefreshProgress(t('refreshProgressWaiting'));

      try {
        const result = await streamRefresh(targetChannelId, {
          onProgress: async payload => {
            updateRefreshProgressFromEvent(payload);
            if (payload.type === 'channel_complete' && payload.channel_new_videos > 0) {
              scheduleVisibleReload();
            }
          },
          onComplete: async payload => {
            reportImportStatus('', 'info');
            if (!payload) {
              return;
            }
            if (payload.type === 'blocked') {
              const helper = window.ytcvRefreshGovernance;
              if (payload.reason === 'refresh_in_progress') {
                showNotification(
                  helper ? helper.getBlockedToastMessage(t, payload) : t('refreshAlreadyRunning'),
                  'info'
                );
              } else {
                showNotification(
                  helper ? helper.getBlockedToastMessage(t, payload) : t('refreshCooldownActive', { minutes: 1 }),
                  'warning'
                );
              }
              return;
            }
            await syncVisibleStateAfterRefresh();
            showNotification(t('newVideosFound', { count: payload.new_videos || 0 }), 'success');
          },
          onError: async () => {
            reportImportStatus('', 'info');
          }
        });
        if (!result) {
          return;
        }
      } catch (error) {
        reportImportStatus('', 'info');
        showNotification(t('unableRefreshVideos'), 'error');
      }
    });
  }

  async function importSubscriptions(showToast) {
    if (!state.currentUser || state.currentUser.auth_provider !== 'google') {
      return false;
    }

    let pageToken = null;
    let processed = 0;
    let total = null;
    let newSubscriptions = 0;
    let newChannels = 0;

    reportImportStatus(t('importingSubscriptions'), 'info');

    while (true) {
      const response = await api.importSubscriptions({
        page_token: pageToken,
        max_results: 50
      });

      if (!response.ok) {
        if (showToast) {
          showNotification(t('unableImportSubscriptions'), 'error');
        }
        reportImportStatus('', 'info');
        return false;
      }

      const payload = response.data || {};
      processed += typeof payload.imported === 'number' ? payload.imported : 0;
      newSubscriptions += typeof payload.new_subscriptions === 'number' ? payload.new_subscriptions : 0;
      newChannels += typeof payload.new_channels === 'number' ? payload.new_channels : 0;
      if (typeof payload.total_results === 'number') {
        total = payload.total_results;
      }

      if (total) {
        reportImportStatus(t('importingSubscriptionsProgress', { processed, total }), 'info');
      } else {
        reportImportStatus(t('importingSubscriptionsProgressPartial', { processed }), 'info');
      }

      pageToken = payload.next_page_token || null;
      if (!pageToken) {
        break;
      }

      await sleep(800);
    }

    reportImportStatus('', 'info');

    return {
      ok: true,
      newSubscriptions,
      newChannels
    };
  }

  async function importSubscriptionsAndRefresh(showToast) {
    const importResult = await importSubscriptions(showToast);
    if (!importResult || !importResult.ok) {
      return false;
    }

    reportImportStatus(t('refreshInProgress'), 'info');
    setRefreshProgress(t('refreshProgressWaiting'));
    let videoCount = 0;
    try {
      const refreshPayload = await streamRefresh(null, {
        onProgress: async payload => {
          updateRefreshProgressFromEvent(payload);
          if (payload.type === 'channel_complete' && payload.channel_new_videos > 0) {
            scheduleVisibleReload();
          }
        }
      });
      videoCount = refreshPayload && refreshPayload.type === 'complete' && typeof refreshPayload.new_videos === 'number'
        ? refreshPayload.new_videos
        : 0;
    } catch (error) {
      reportImportStatus('', 'info');
      if (showToast) {
        showNotification(t('importFailed'), 'warning');
      }
      return true;
    }
    reportImportStatus('', 'info');

    if (showToast) {
      showNotification(
        t('importSummary', {
          subscriptions: importResult.newSubscriptions,
          channels: importResult.newChannels,
          videos: videoCount
        }),
        'success'
      );
      showNotification(t('allSubscriptionsUpToDate'), 'success');
    }

    // Auto-classify unclassified channels after import + refresh
    classifyUnclassifiedChannels(msg => setRefreshProgress(msg))
      .then(count => {
        setRefreshProgress('');
        if (count > 0) showNotification(t('classifyComplete', { count }), 'success');
      })
      .catch(() => setRefreshProgress(''));

    return true;
  }

  function updateImportVisibility(user) {
    if (!ui.importButton) {
      return;
    }

    const provider = user ? user.auth_provider : null;
    ui.importButton.hidden = !user || provider !== 'google';
  }

  function setupImportButton() {
    if (!ui.importButton) {
      return;
    }

    ui.importButton.addEventListener('click', async () => {
      if (!state.currentUser) {
        showNotification(t('signInBeforeImport'), 'warning');
        return;
      }

      ui.importButton.disabled = true;
      await importSubscriptionsAndRefresh(true);
      ui.importButton.disabled = false;
      await syncVisibleStateAfterRefresh();
    });

    updateImportVisibility(state.currentUser);
    window.addEventListener('auth:changed', event => {
      const user = event.detail ? event.detail.user : null;
      updateImportVisibility(user);
    });
  }

  // ── Shared classify function ──────────────────────────────────────────────

  async function classifyUnclassifiedChannels(progressCallback) {
    const report = progressCallback || (() => {});

    // Start the background task on the backend
    const startResp = await api.startClassifyTask();
    // Nothing to classify
    if (startResp.ok && startResp.data && startResp.data.active === false) {
      return 0;
    }
    // 409 means already running — continue to poll
    if (!startResp.ok && startResp.status !== 409) {
      throw new Error('Failed to start classify task');
    }

    // Poll until done
    return new Promise((resolve, reject) => {
      const poll = setInterval(async () => {
        try {
          const resp = await api.getClassifyStatus();
          if (!resp.ok) {
            clearInterval(poll);
            reject(new Error('Failed to get classify status'));
            return;
          }
          const s = resp.data;
          if (s.active) {
            report(t('classifyProgress', {
              cursor: s.cursor,
              total: s.total,
              classified: s.classified
            }));
          } else {
            clearInterval(poll);
            report('');
            // Refresh UI
            await syncChannelsState();
            renderChannelList(state.channels);
            if (state.categoryManager) {
              await state.categoryManager.init();
            }
            resolve(s.classified || 0);
          }
        } catch (err) {
          clearInterval(poll);
          reject(err);
        }
      }, 3000);
    });
  }

  async function resumeClassifyPollIfActive() {
    try {
      const resp = await api.getClassifyStatus();
      if (resp.ok && resp.data && resp.data.active) {
        classifyUnclassifiedChannels(msg => setRefreshProgress(msg))
          .then(count => {
            setRefreshProgress('');
            if (count > 0) showNotification(t('classifyComplete', { count }), 'success');
          })
          .catch(() => setRefreshProgress(''));
      }
    } catch (_) {
      // Ignore — status check is best-effort on load
    }
  }

  function setupClassifyButton() {
    if (!ui.classifyButton) return;

    ui.classifyButton.addEventListener('click', async () => {
      ui.classifyButton.disabled = true;
      const origText = ui.classifyButton.textContent;
      try {
        const classified = await classifyUnclassifiedChannels(msg => {
          setRefreshProgress(msg);
        });
        if (classified > 0) {
          showNotification(t('classifyComplete', { count: classified }), 'success');
        } else {
          showNotification(t('classifyNothingToDo'), 'info');
        }
      } catch (_) {
        showNotification(t('classifyError'), 'error');
      } finally {
        ui.classifyButton.disabled = false;
        setRefreshProgress('');
      }
    });

    // Show/hide based on auth
    const updateVisibility = user => {
      ui.classifyButton.hidden = !user;
    };
    updateVisibility(state.currentUser);
    window.addEventListener('auth:changed', event => {
      updateVisibility(event.detail ? event.detail.user : null);
    });
  }

  function setupReclassifyButton() {
    if (!ui.reclassifyBtn) {
      return;
    }

    ui.reclassifyBtn.addEventListener('click', async () => {
      ui.reclassifyBtn.disabled = true;
      try {
        let totalEvidenceChannels = 0;
        let totalVideosCreated = 0;
        let totalVideosUpdated = 0;
        let remaining = 999;

        // Step 1: Enrich unclassified channels with recent video evidence.
        ui.reclassifyBtn.textContent = 'Obteniendo evidencia de videos...';

        while (remaining > 0) {
          const enrichResponse = await api.enrichChannelVideoEvidence(null, 25, 12, true);
          if (!enrichResponse.ok) {
            break;
          }
          totalEvidenceChannels += enrichResponse.data.channels_processed || 0;
          totalVideosCreated += enrichResponse.data.videos_created || 0;
          totalVideosUpdated += enrichResponse.data.videos_updated || 0;
          remaining = enrichResponse.data.remaining_unclassified || 0;
          ui.reclassifyBtn.textContent = `Enriqueciendo... (${totalEvidenceChannels} canales)`;

          if (enrichResponse.data.channels_processed === 0) {
            break;
          }
        }

        if (totalEvidenceChannels > 0) {
          showNotification(
            `${totalEvidenceChannels} canales enriquecidos con evidencia de video (${totalVideosCreated} nuevos, ${totalVideosUpdated} actualizados)`,
            'success'
          );
        }

        // Step 2: Reclassify all channels
        ui.reclassifyBtn.textContent = t('reclassifying') || 'Reclasificando...';

        const response = await api.reclassifyAllChannels();
        if (response.ok) {
          const stats = response.data || {};
          const reclassified = stats.reclassified || 0;
          showNotification(`${reclassified} canales clasificados correctamente`, 'success');

          const channelsResponse = await api.getChannels();
          if (channelsResponse.ok) {
            state.channels = channelsResponse.data || [];
            renderChannelList(state.channels);
          }

          if (state.categoryManager) {
            await state.categoryManager.init();
          }
        } else {
          showNotification(t('reclassifyError') || 'Error al reclasificar canales', 'error');
        }
      } finally {
        ui.reclassifyBtn.disabled = false;
        ui.reclassifyBtn.textContent = t('reclassifyChannels') || 'Reclasificar Canales';
      }
    });
  }

  function setupDebug() {
    const isDev = ['localhost', '127.0.0.1'].includes(window.location.hostname);
    if (!isDev) {
      return;
    }

    window.appDebug = {
      getState: () => ({ ...state }),
      reloadVideos: () => reloadCarousels(),
      clearCache: () => clearCarousels(),
      getCarousels: () => state.carousels
    };
  }

  async function initCategorySelector() {
    if (typeof window.CategorySelector !== 'function') {
      return;
    }

    state.categorySelector = new window.CategorySelector(api, async (channelId, category) => {
      const channel = state.channels.find(ch => ch.id === channelId);
      if (channel) {
        if (category) {
          channel.category = { category: category };
        } else {
          channel.category = null;
        }
      }
      renderChannelList(state.channels);
      if (state.categoryManager) {
        await state.categoryManager.init();
      }
    });

    await state.categorySelector.loadCategories();
    state.categoriesLoaded = true;

    if (ui.reclassifyBtn) {
      ui.reclassifyBtn.hidden = false;
    }
  }

  async function bootstrapAuthenticated() {
    if (typeof window.initDevice === 'function') {
      state.currentDevice = await window.initDevice();
      if (window.ytcvAccountPanel && typeof window.getDeviceIdentifier === 'function') {
        window.ytcvAccountPanel.setCurrentDeviceIdentifier(window.getDeviceIdentifier());
      }
    }
    await initCategorySelector();
    await loadApp();
    resumeClassifyPollIfActive();
  }

  async function init() {
    if (typeof window.initTheme === 'function') {
      window.initTheme();
    }

    if (typeof window.initAuth === 'function') {
      state.currentUser = await window.initAuth();
    }

    // Check for auth_status URL param before showing login page
    const authStatus = window.ytcvLoginPage ? window.ytcvLoginPage.checkAuthStatusParam() : null;

    if (!state.currentUser) {
      if (window.ytcvLoginPage) {
        const wizardOptions = authStatus === 'needs_setup' ? { wizard: true } : {};
        window.ytcvLoginPage.show(wizardOptions);
      }
    } else {
      if (authStatus === 'needs_setup' && window.ytcvLoginPage) {
        window.ytcvLoginPage.show({ wizard: true });
      } else {
        await loadSettings();
      }
    }

    setupFilters();
    setupChannelSidebarSearch();
    setupSearch();
    setupMenu();
    setupFilterPanel();
    if (window.ytcvDesktopShell && typeof window.ytcvDesktopShell.initDesktopShell === 'function') {
      window.ytcvDesktopShell.initDesktopShell();
    }
    if (window.ytcvPhoneShell && typeof window.ytcvPhoneShell.initPhoneShell === 'function') {
      window.ytcvPhoneShell.initPhoneShell({
        openFilters: openFilterPanel,
        openMenu: () => {
          if (typeof state.setMenuOpen === 'function') {
            state.setMenuOpen(true);
          }
        }
      });
    }
    if (window.ytcvTvShell && typeof window.ytcvTvShell.initTvShell === 'function') {
      window.ytcvTvShell.initTvShell({
        focusChannels: () => {
          if (ui.channelSearchInput) {
            ui.channelSearchInput.focus();
            return;
          }
          if (ui.channelList) {
            const firstItem = ui.channelList.querySelector('.channel-item');
            if (firstItem) {
              firstItem.focus();
            }
          }
        },
        openFilters: openFilterPanel,
        triggerRefresh: () => {
          if (ui.refreshButton) {
            ui.refreshButton.click();
          }
        },
        openDisplaySetup: () => {
          if (ui.menuDisplayMode) {
            ui.menuDisplayMode.click();
          }
        }
      });
    }
    setupGuide();
    setupSettingsModal();
    setupConfirmModal();
    setupLanguageMenu();
    setupRefresh();
    setupImportButton();
    setupReclassifyButton();
    setupClassifyButton();
    setupKeyboardNavigation();
    setupDebug();
  }

  window.addEventListener('auth:changed', async event => {
    const user = event.detail ? event.detail.user : null;
    state.currentUser = user;

    if (user) {
      await loadSettings();
      await bootstrapAuthenticated();
    } else {
      state.channels = [];
      state.selectedChannelId = null;
      state.selectedChannelYtId = null;
      clearCarousels();
      updateHeaderContext();
    }
  });

  init();
});
