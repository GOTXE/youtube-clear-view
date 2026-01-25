// Main application orchestrator for YT Clear View.

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('app');
  if (!root) {
    return;
  }

  if (typeof window.APP_CONFIG === 'undefined') {
    const message = document.createElement('p');
    message.className = 'body';
    message.textContent = 'Missing APP_CONFIG.';
    root.appendChild(message);
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
    filters: {
      unwatched: false,
      week: false,
      month: false
    },
    carousels: [],
    searchActive: false,
    searchQuery: '',
    autoImportAttempted: false
  };

  const ui = {
    headerPanel: document.querySelector('.header-panel'),
    headerToggle: document.getElementById('header-toggle'),
    topPanels: document.querySelector('.top-panels'),
    filtersSection: document.querySelector('.filters'),
    filtersToggle: document.getElementById('filters-toggle'),
    latestCarousel: document.getElementById('latest-carousel'),
    latestTitle: document.getElementById('latest-title'),
    shortsCarousel: document.getElementById('shorts-carousel'),
    olderCarousel: document.getElementById('older-carousel'),
    shortsSection: document.getElementById('shorts-section'),
    olderSection: document.getElementById('older-section'),
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
    searchButton: null,
    filterUnwatched: document.getElementById('filter-unwatched'),
    filterWeek: document.getElementById('filter-week'),
    filterMonth: document.getElementById('filter-month')
  };

  let clearSearchButton = null;

  function showNotification(message, type = 'info') {
    if (typeof window.showNotification === 'function') {
      window.showNotification(message, type);
      return;
    }

    // Fallback for environments without toast utilities.
    alert(message);
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
        if (state.filters.week && days > 7) {
          return false;
        }
        if (!state.filters.week && state.filters.month && days > 30) {
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
      <div class="channel-item__thumb">ALL</div>
      <span class="channel-item__name">All</span>
    `;
    ui.channelList.appendChild(allItem);

    const sorted = [...(channels || [])].sort((a, b) => {
      const nameA = (a.title || '').toLowerCase();
      const nameB = (b.title || '').toLowerCase();
      return nameA.localeCompare(nameB);
    });

    const channelMatchesFilters = channel => {
      const weekFilter = state.filters.week;
      const monthFilter = state.filters.month;
      const unwatchedFilter = state.filters.unwatched;

      const recent7 = Number(channel.recent_total_7 || 0);
      const recent7Unwatched = Number(channel.recent_unwatched_7 || 0);
      const recent30 = Number(channel.recent_total_30 || 0);
      const recent30Unwatched = Number(channel.recent_unwatched_30 || 0);
      const totalUnwatched = Number(channel.unwatched_total || 0);

      if (weekFilter) {
        return unwatchedFilter ? recent7Unwatched > 0 : recent7 > 0;
      }
      if (monthFilter) {
        return unwatchedFilter ? recent30Unwatched > 0 : recent30 > 0;
      }
      if (unwatchedFilter) {
        return totalUnwatched > 0;
      }
      return true;
    };

    if (!sorted.length) {
      const empty = document.createElement('p');
      empty.className = 'caption';
      empty.textContent = 'No subscriptions yet.';
      ui.channelList.appendChild(empty);
    }

    const filtered = sorted.length ? sorted.filter(channelMatchesFilters) : [];

    if (sorted.length && !filtered.length) {
      const empty = document.createElement('p');
      empty.className = 'caption';
      empty.textContent = 'No channels match the current filters.';
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
      if (!channel.thumbnail_url) {
        return buildPlaceholder(channel);
      }

      const thumb = document.createElement('div');
      thumb.className = 'channel-item__thumb';

      const img = document.createElement('img');
      img.className = 'channel-item__thumb-image';
      img.src = channel.thumbnail_url;
      img.alt = channel.title || 'Channel thumbnail';
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
      name.textContent = channel.title || channel.yt_channel_id || 'Unknown';
      item.appendChild(name);

      const status = document.createElement('span');
      status.className = 'channel-item__status';
      if (Number(channel.recent_total_7 || 0) > 0) {
        status.classList.add('is-active');
      }
      status.setAttribute('aria-hidden', 'true');
      item.appendChild(status);

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
      ui.lastUpdatedLabel.textContent = 'Last updated: not yet.';
      return;
    }

    timestamps.sort((a, b) => b.getTime() - a.getTime());
    const latest = timestamps[0];
    const relative = typeof window.timeAgo === 'function' ? window.timeAgo(latest.toISOString()) : '';
    ui.lastUpdatedLabel.textContent = relative
      ? `Last updated ${relative}.`
      : `Last updated ${latest.toLocaleString()}.`;
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

    clearCarousels();
    await renderMainCarousel();
    await renderShortsCarousel();
    await renderOlderCarousel();
    if (ui.shortsSection) {
      ui.shortsSection.hidden = false;
    }
    if (ui.olderSection) {
      ui.olderSection.hidden = false;
    }
    if (ui.shortsSection) {
      ui.shortsSection.hidden = false;
    }
    if (ui.olderSection) {
      ui.olderSection.hidden = false;
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
  }

  function setupFilters() {
    const handleFilters = () => {
      state.filters.unwatched = Boolean(ui.filterUnwatched && ui.filterUnwatched.checked);
      state.filters.week = Boolean(ui.filterWeek && ui.filterWeek.checked);
      state.filters.month = Boolean(ui.filterMonth && ui.filterMonth.checked);

      renderChannelList(state.channels);
      if (state.searchActive) {
        runSearch(state.searchQuery);
      } else {
        reloadCarousels();
      }
    };

    if (ui.filterUnwatched) {
      ui.filterUnwatched.addEventListener('change', handleFilters);
    }
    if (ui.filterWeek) {
      ui.filterWeek.addEventListener('change', handleFilters);
    }
    if (ui.filterMonth) {
      ui.filterMonth.addEventListener('change', handleFilters);
    }
  }

  function setupFilterToggle() {
    if (!ui.filtersSection || !ui.filtersToggle) {
      return;
    }

    ui.filtersToggle.addEventListener('click', () => {
      const isCollapsed = ui.filtersSection.classList.toggle('filters--collapsed');
      ui.filtersToggle.textContent = isCollapsed ? 'Filters' : 'Hide';
      ui.filtersToggle.setAttribute('aria-pressed', isCollapsed ? 'true' : 'false');
      updateTopPanelsCollapse();
    });
  }

  function setupHeaderToggle() {
    if (!ui.headerPanel || !ui.headerToggle) {
      return;
    }

    ui.headerToggle.addEventListener('click', () => {
      const isCollapsed = ui.headerPanel.classList.toggle('header-panel--collapsed');
      ui.headerToggle.textContent = isCollapsed ? 'Menu' : 'Hide';
      ui.headerToggle.setAttribute('aria-pressed', isCollapsed ? 'true' : 'false');
      updateTopPanelsCollapse();
    });
  }

  function updateTopPanelsCollapse() {
    if (!ui.topPanels || !ui.headerPanel || !ui.filtersSection) {
      return;
    }
    const bothCollapsed = ui.headerPanel.classList.contains('header-panel--collapsed')
      && ui.filtersSection.classList.contains('filters--collapsed');
    ui.topPanels.classList.toggle('top-panels--collapsed', bothCollapsed);
  }

  function ensureClearSearchButton() {
    if (clearSearchButton) {
      return;
    }

    clearSearchButton = document.createElement('button');
    clearSearchButton.type = 'button';
    clearSearchButton.className = 'button button--ghost';
    clearSearchButton.textContent = 'Clear';
    clearSearchButton.hidden = true;
    clearSearchButton.addEventListener('click', () => {
      clearSearch();
    });

    const searchGroup = ui.searchInput ? ui.searchInput.closest('.field__group') : null;
    if (searchGroup) {
      searchGroup.appendChild(clearSearchButton);
    }
  }

  function clearSearch() {
    state.searchActive = false;
    state.searchQuery = '';
    if (ui.searchInput) {
      ui.searchInput.value = '';
    }

    if (ui.videosLabel) {
      ui.videosLabel.textContent = 'Videos';
    }
    if (ui.videosCount) {
      ui.videosCount.hidden = false;
    }


    if (clearSearchButton) {
      clearSearchButton.hidden = true;
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

    if (ui.videosLabel) {
      ui.videosLabel.textContent = `Search results for "${trimmed}"`;
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

    if (clearSearchButton) {
      clearSearchButton.hidden = false;
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
    ensureClearSearchButton();

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

  function setupRefresh() {
    if (!ui.refreshButton) {
      return;
    }

    ui.refreshButton.addEventListener('click', async () => {
      const targetChannelId = state.selectedChannelId !== null ? state.selectedChannelId : null;
      const response = await api.refreshChannels(targetChannelId);
      if (!response.ok) {
        showNotification('Unable to refresh videos.', 'error');
        return;
      }

      const count = response.data && typeof response.data.new_videos === 'number'
        ? response.data.new_videos
        : 0;
      showNotification(`${count} new videos found.`, 'success');
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

    reportImportStatus('Importing subscriptions...', 'info');

    while (true) {
      const response = await api.importSubscriptions({
        page_token: pageToken,
        max_results: 50
      });

      if (!response.ok) {
        if (showToast) {
          showNotification('Unable to import subscriptions.', 'error');
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
        reportImportStatus(`Importing subscriptions (${processed}/${total})...`, 'info');
      } else {
        reportImportStatus(`Importing subscriptions (${processed})...`, 'info');
      }

      pageToken = payload.next_page_token || null;
      if (!pageToken) {
        break;
      }

      await sleep(800);
    }

    reportImportStatus('Refreshing videos...', 'info');
    const refreshResponse = await api.refreshChannels();
    reportImportStatus('', 'info');

    if (!refreshResponse.ok) {
      if (showToast) {
        showNotification('Subscriptions imported. Refresh videos failed.', 'warning');
      }
      return true;
    }

    const refreshPayload = refreshResponse.data || {};
    const videoCount = typeof refreshPayload.new_videos === 'number'
      ? refreshPayload.new_videos
      : 0;

    if (showToast) {
      showNotification(
        `Imported ${newSubscriptions} subscriptions, ${newChannels} channels, ${videoCount} videos.`,
        'success'
      );
      showNotification('All subscriptions are up to date.', 'success');
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
        showNotification('Sign in before importing subscriptions.', 'warning');
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

  async function bootstrapAuthenticated() {
    if (typeof window.initDevice === 'function') {
      state.currentDevice = await window.initDevice();
    }
    await loadApp();
  }

  async function init() {
    if (typeof window.initTheme === 'function') {
      window.initTheme();
    }

    if (typeof window.initAuth === 'function') {
      state.currentUser = await window.initAuth();
    }

    setupFilters();
    setupFilterToggle();
    setupHeaderToggle();
    setupSearch();
    setupRefresh();
    setupImportButton();
    setupDebug();

    if (state.currentUser) {
      await bootstrapAuthenticated();
    }
  }

  window.addEventListener('auth:changed', async event => {
    const user = event.detail ? event.detail.user : null;
    state.currentUser = user;

    if (user) {
      await bootstrapAuthenticated();
    } else {
      clearCarousels();
    }
  });

  init();
});
