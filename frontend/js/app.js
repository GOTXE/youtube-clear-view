// Main application orchestrator for YT Clear View.

document.addEventListener('DOMContentLoaded', async () => {
  const root = document.getElementById('app');
  if (!root) {
    return;
  }

  if (window.ytcvI18nReady) {
    await window.ytcvI18nReady;
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
    autoImportAttempted: false,
    categoryManager: null,
    categorySelector: null,
    categoriesLoaded: false,
    settings: null,
    presets: null
  };

  const ui = {
    appSubtitle: document.getElementById('app-subtitle'),
    appSubtitleSecondary: document.getElementById('app-subtitle-secondary'),
    subscriptionsTitle: document.getElementById('subscriptions-title'),
    filtersTitle: document.getElementById('filters-title'),
    filtersSearchLabel: document.getElementById('filters-search-label'),
    channelSidebar: document.querySelector('.channel-sidebar'),
    themeToggle: document.getElementById('theme-toggle'),
    menuToggle: document.getElementById('menu-toggle'),
    menuPanel: document.getElementById('menu-panel'),
    menuFilters: document.getElementById('menu-filters'),
    menuCategoryGuide: document.getElementById('menu-category-guide'),
    menuSettings: document.getElementById('menu-settings'),
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
    latestCarousel: document.getElementById('latest-carousel'),
    latestTitle: document.getElementById('latest-title'),
    shortsCarousel: document.getElementById('shorts-carousel'),
    olderCarousel: document.getElementById('older-carousel'),
    shortsSection: document.getElementById('shorts-section'),
    olderSection: document.getElementById('older-section'),
    olderTitle: document.getElementById('older-title'),
    refreshButton: document.getElementById('refresh-videos'),
    importButton: document.getElementById('import-subscriptions-button'),
    lastUpdatedLabel: document.getElementById('last-updated'),
    channelList: document.getElementById('channel-list'),
    channelCount: document.getElementById('channel-count'),
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
    reclassifyBtn: document.getElementById('reclassify-btn')
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
    if (ui.searchInput) {
      ui.searchInput.placeholder = t('searchPlaceholder');
      ui.searchInput.setAttribute('aria-label', t('searchAriaLabel'));
    }
    if (ui.refreshButton) {
      ui.refreshButton.textContent = t('refresh');
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
    if (ui.menuCategoryGuide) {
      ui.menuCategoryGuide.textContent = t('categoryGuideLabel');
    }
    if (ui.menuSettings) {
      ui.menuSettings.textContent = t('autoUpdatesLabel');
    }
    if (ui.importButton) {
      ui.importButton.textContent = t('importSubscriptions');
    }
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
    if (ui.settingsCancel) {
      ui.settingsCancel.textContent = t('cancel');
    }
    if (ui.settingsSave) {
      ui.settingsSave.textContent = t('save');
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

  applyLocalizedCopy();
  markI18nReady();

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

    const changed = nextPreset !== state.settings.preset
      || JSON.stringify(schedule) !== JSON.stringify(state.settings.schedule_hours || []);

    if (!changed) {
      closeSettingsModal();
      return;
    }

    if (!confirm(t('settingsConfirm1'))) {
      return;
    }
    if (!confirm(t('settingsConfirm2'))) {
      return;
    }

    const payload = {
      preset: nextPreset,
      schedule_hours: schedule,
      timezone: getTimezone(),
      start_backfill: nextPreset !== state.settings.preset
    };

    const response = await api.updateSettings(payload);
    if (!response.ok) {
      showNotification(response.error || t('settingsSaveFailed'), 'error');
      return;
    }
    await loadSettings();
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

  function setLoading(show, containerId) {
    if (typeof window.loadingSpinner === 'function') {
      window.loadingSpinner(show, containerId);
    }
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

  function clearCarousels() {
    state.carousels.forEach(carousel => carousel.destroy());
    state.carousels = [];

    if (ui.latestCarousel) {
      ui.latestCarousel.innerHTML = '';
    }
    if (ui.shortsCarousel) {
      ui.shortsCarousel.innerHTML = '';
    }
    if (ui.olderCarousel) {
      ui.olderCarousel.innerHTML = '';
    }
    if (ui.themeCarousels) {
      ui.themeCarousels.innerHTML = '';
    }
    if (state.categoryManager) {
      state.categoryManager.destroy();
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
    });

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
    }, { showTitle: false, showDescription: false });

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
    }, { hideTextForShorts: true });

    await carousel.init();
    state.carousels.push(carousel);
  }

  function renderChannelList(channels) {
    if (!ui.channelList) {
      return;
    }

    ui.channelList.innerHTML = '';

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
      const searchText = (state.searchQuery || '').trim().toLowerCase();
      if (searchText) {
        const name = (channel.title || channel.yt_channel_id || '').toLowerCase();
        if (!name.includes(searchText)) {
          return false;
        }
      }

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

    const filtered = sorted.length ? sorted.filter(channelMatchesFilters) : [];

    if (sorted.length && !filtered.length) {
      const empty = document.createElement('p');
      empty.className = 'caption';
      empty.textContent = t('noChannelsMatch');
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

      if (typeof window.createCategoryBadge === 'function' && state.categorySelector) {
        const categoryData = channel.category && channel.category.category
          ? channel.category.category
          : null;
        const badge = window.createCategoryBadge(categoryData, () => {
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
        });
        updateVideoCounts();
        if (state.searchActive) {
          runSearch(state.searchQuery);
        } else {
          reloadCarousels();
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
      .map(channel => channel.last_refreshed_at)
      .filter(Boolean)
      .map(value => new Date(value))
      .filter(date => !Number.isNaN(date.getTime()));

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

  async function loadApp() {
    if (!state.currentUser) {
      return;
    }

    setLoading(true, 'latest-carousel');

    const channelsResponse = await api.getChannels();
    if (channelsResponse.ok) {
      state.channels = channelsResponse.data || [];
    }

    if (
      state.currentUser.auth_provider === 'google'
      && state.channels.length === 0
      && !state.autoImportAttempted
    ) {
      state.autoImportAttempted = true;
      await importSubscriptionsAndRefresh(false);
      const refreshedChannels = await api.getChannels();
      if (refreshedChannels.ok) {
        state.channels = refreshedChannels.data || [];
      }
    }

    renderChannelList(state.channels);
    updateChannelCount(state.channels);
    updateLastUpdatedLabel(state.channels);
    await updateVideoCounts();
    prefetchChannelThumbnails(state.channels);

    clearCarousels();
    await renderMainCarousel();
    await renderShortsCarousel();
    await renderOlderCarousel();

    if (typeof window.CategoryManager === 'function' && ui.categoryCarousels) {
      state.categoryManager = new window.CategoryManager(api, 'category-carousels');
      await state.categoryManager.init();
      if (ui.categoriesSection) {
        ui.categoriesSection.hidden = false;
      }
    }

    if (ui.shortsSection) {
      ui.shortsSection.hidden = false;
    }
    if (ui.olderSection) {
      ui.olderSection.hidden = false;
    }

    setLoading(false, 'latest-carousel');
  }

  async function reloadCarousels() {
    clearCarousels();
    await renderMainCarousel();
    await renderShortsCarousel();
    await renderOlderCarousel();

    if (typeof window.CategoryManager === 'function' && ui.categoryCarousels) {
      state.categoryManager = new window.CategoryManager(api, 'category-carousels');
      await state.categoryManager.init();
    }
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

  function setupMenu() {
    if (!ui.menuToggle || !ui.menuPanel) {
      return;
    }

    const setMenuOpen = isOpen => {
      ui.menuPanel.hidden = !isOpen;
      ui.menuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    };

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

    const updateMenuAuth = user => {
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

  function setupRefresh() {
    if (!ui.refreshButton) {
      return;
    }

    ui.refreshButton.addEventListener('click', async () => {
      const targetChannelId = state.selectedChannelId !== null ? state.selectedChannelId : null;
      const response = await api.refreshChannels(targetChannelId);
      if (!response.ok) {
        showNotification(t('unableRefreshVideos'), 'error');
        return;
      }

      const count = response.data && typeof response.data.new_videos === 'number'
        ? response.data.new_videos
        : 0;
      showNotification(t('newVideosFound', { count }), 'success');
      await loadApp();
    });
  }

  async function importSubscriptionsAndRefresh(showToast) {
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

    reportImportStatus(t('refreshInProgress'), 'info');
    const refreshResponse = await api.refreshChannels();
    reportImportStatus('', 'info');

    if (!refreshResponse.ok) {
      if (showToast) {
        showNotification(t('importFailed'), 'warning');
      }
      return true;
    }

    const refreshPayload = refreshResponse.data || {};
    const videoCount = typeof refreshPayload.new_videos === 'number'
      ? refreshPayload.new_videos
      : 0;

    if (showToast) {
      showNotification(
        t('importSummary', {
          subscriptions: newSubscriptions,
          channels: newChannels,
          videos: videoCount
        }),
        'success'
      );
      showNotification(t('allSubscriptionsUpToDate'), 'success');
    }

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
      await loadApp();
    });

    updateImportVisibility(state.currentUser);
    window.addEventListener('auth:changed', event => {
      const user = event.detail ? event.detail.user : null;
      updateImportVisibility(user);
    });
  }

  function setupReclassifyButton() {
    if (!ui.reclassifyBtn) {
      return;
    }

    ui.reclassifyBtn.addEventListener('click', async () => {
      ui.reclassifyBtn.disabled = true;

      // Step 1: Enrich channels with topic_ids from YouTube API
      ui.reclassifyBtn.textContent = 'Obteniendo datos de YouTube...';
      let totalEnriched = 0;
      let remaining = 999;

      while (remaining > 0) {
        const enrichResponse = await api.enrichChannels(null, 50);
        if (!enrichResponse.ok) {
          break;
        }
        totalEnriched += enrichResponse.data.enriched || 0;
        remaining = enrichResponse.data.remaining || 0;
        ui.reclassifyBtn.textContent = `Enriqueciendo... (${totalEnriched} canales)`;

        if (enrichResponse.data.enriched === 0) {
          break;
        }
      }

      if (totalEnriched > 0) {
        showNotification(`${totalEnriched} canales enriquecidos con datos de YouTube`, 'success');
      }

      // Step 2: Reclassify all channels
      ui.reclassifyBtn.textContent = t('reclassifying') || 'Reclasificando...';

      const response = await api.reclassifyAllChannels();
      if (response.ok) {
        const stats = response.data || {};
        const classified = stats.classified || 0;
        showNotification(`${classified} canales clasificados correctamente`, 'success');

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

      ui.reclassifyBtn.disabled = false;
      ui.reclassifyBtn.textContent = t('reclassifyChannels') || 'Reclasificar Canales';
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
    }
    await initCategorySelector();
    await loadApp();
  }

  async function init() {
    if (typeof window.initTheme === 'function') {
      window.initTheme();
    }

    if (typeof window.initAuth === 'function') {
      state.currentUser = await window.initAuth();
    }
    if (state.currentUser) {
      await loadSettings();
    }

    setupFilters();
    setupSearch();
    setupMenu();
    setupFilterPanel();
    setupGuide();
    setupSettingsModal();
    setupLanguageMenu();
    setupRefresh();
    setupImportButton();
    setupReclassifyButton();
    setupDebug();

    if (state.currentUser) {
      await bootstrapAuthenticated();
    }
  }

  window.addEventListener('auth:changed', async event => {
    const user = event.detail ? event.detail.user : null;
    state.currentUser = user;

    if (user) {
      await loadSettings();
      await bootstrapAuthenticated();
    } else {
      clearCarousels();
    }
  });

  init();
});
