// Main application orchestrator for YouTube Clear View.

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
    themes: [],
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
    latestCarousel: document.getElementById('latest-carousel'),
    latestTitle: document.getElementById('latest-title'),
    themeCarousels: document.getElementById('theme-carousels'),
    themesSection: document.getElementById('themes-container'),
    refreshButton: document.getElementById('refresh-videos'),
    seedButton: document.getElementById('seed-data-button'),
    importButton: document.getElementById('import-subscriptions-button'),
    searchInput: document.getElementById('search-input'),
    searchButton: document.getElementById('search-button'),
    themeSelector: document.getElementById('theme-selector'),
    filterUnwatched: document.getElementById('filter-unwatched'),
    filterWeek: document.getElementById('filter-week'),
    filterMonth: document.getElementById('filter-month')
  };

  let clearSearchButton = null;

  function isLocalhost() {
    return ['localhost', '127.0.0.1'].includes(window.location.hostname);
  }

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

  function applyFilters(payload) {
    if (!payload || !Array.isArray(payload.videos)) {
      return payload;
    }

    const filtered = payload.videos.filter(item => {
      if (state.filters.unwatched && item.watched) {
        return false;
      }

      const published = item.video && item.video.published_at ? new Date(item.video.published_at) : null;
      if (published && !Number.isNaN(published.getTime())) {
        const days = (Date.now() - published.getTime()) / (1000 * 60 * 60 * 24);
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
    if (ui.themeCarousels) {
      ui.themeCarousels.innerHTML = '';
    }
  }

  async function renderMainCarousel() {
    if (!ui.latestCarousel) {
      return;
    }

    const carousel = new window.Carousel('latest-carousel', async (offset, limit) => {
      const response = await api.getLatestVideos(limit, offset);
      if (!response.ok) {
        return { videos: [], has_more: false, next_offset: null };
      }
      return applyFilters(response.data);
    });

    await carousel.init();
    state.carousels.push(carousel);
  }

  async function renderThemeCarousels(themes) {
    if (!ui.themeCarousels) {
      return;
    }

    ui.themeCarousels.innerHTML = '';

    for (const theme of themes) {
      const wrapper = document.createElement('div');
      wrapper.className = 'carousel-shell';

      const header = document.createElement('div');
      header.className = 'section-header';

      const title = document.createElement('h3');
      title.className = 'heading-3';
      title.textContent = theme.name;

      const safeColor = theme.color && theme.color.startsWith('var(') ? theme.color : null;
      if (safeColor) {
        title.style.color = safeColor;
      }

      header.appendChild(title);
      wrapper.appendChild(header);

      const carouselId = `theme-carousel-${theme.id}`;
      const carouselContainer = document.createElement('div');
      carouselContainer.id = carouselId;
      wrapper.appendChild(carouselContainer);
      ui.themeCarousels.appendChild(wrapper);

      const carousel = new window.Carousel(carouselId, async (offset, limit) => {
        const response = await api.getVideosByTheme(theme.id, limit, offset);
        if (!response.ok) {
          return { videos: [], has_more: false, next_offset: null };
        }
        return applyFilters(response.data);
      }, { theme: theme.color });

      await carousel.init();
      state.carousels.push(carousel);
    }
  }

  function updateThemeSelector(themes) {
    if (!ui.themeSelector) {
      return;
    }

    ui.themeSelector.innerHTML = '';
    const allOption = document.createElement('option');
    allOption.value = '';
    allOption.textContent = 'All themes';
    ui.themeSelector.appendChild(allOption);

    themes.forEach(theme => {
      const option = document.createElement('option');
      option.value = theme.id;
      option.textContent = theme.name;
      ui.themeSelector.appendChild(option);
    });
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

    const themesResponse = await api.getThemes();
    if (themesResponse.ok) {
      state.themes = themesResponse.data || [];
    }

    updateThemeSelector(state.themes);

    clearCarousels();
    await renderMainCarousel();
    await renderThemeCarousels(state.themes);

    if (ui.themesSection) {
      ui.themesSection.hidden = false;
    }

    setLoading(false, 'latest-carousel');
  }

  async function reloadCarousels() {
    clearCarousels();
    await renderMainCarousel();
    await renderThemeCarousels(state.themes);
  }

  function setupFilters() {
    const handleFilters = () => {
      state.filters.unwatched = Boolean(ui.filterUnwatched && ui.filterUnwatched.checked);
      state.filters.week = Boolean(ui.filterWeek && ui.filterWeek.checked);
      state.filters.month = Boolean(ui.filterMonth && ui.filterMonth.checked);

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

  function ensureClearSearchButton() {
    if (clearSearchButton || !ui.searchButton) {
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

    ui.searchButton.parentNode.appendChild(clearSearchButton);
  }

  function clearSearch() {
    state.searchActive = false;
    state.searchQuery = '';
    if (ui.searchInput) {
      ui.searchInput.value = '';
    }

    if (ui.latestTitle) {
      ui.latestTitle.textContent = 'Latest Videos';
    }

    if (ui.themesSection) {
      ui.themesSection.hidden = false;
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

    if (ui.latestTitle) {
      ui.latestTitle.textContent = `Search results for "${trimmed}"`;
    }

    if (ui.themesSection) {
      ui.themesSection.hidden = true;
    }

    if (clearSearchButton) {
      clearSearchButton.hidden = false;
    }

    clearCarousels();

    const themeId = ui.themeSelector && ui.themeSelector.value ? ui.themeSelector.value : null;
    const carousel = new window.Carousel('latest-carousel', async (offset, limit) => {
      const filters = { limit, offset };
      if (themeId) {
        filters.theme_id = themeId;
      }

      const response = await api.searchVideos(trimmed, filters);
      if (!response.ok) {
        return { videos: [], has_more: false, next_offset: null };
      }
      return applyFilters(response.data);
    });

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

    if (ui.searchButton) {
      ui.searchButton.addEventListener('click', handleSearch);
    }

    if (ui.themeSelector) {
      ui.themeSelector.addEventListener('change', () => {
        if (state.searchActive) {
          runSearch(state.searchQuery);
        }
      });
    }
  }

  function setupRefresh() {
    if (!ui.refreshButton) {
      return;
    }

    ui.refreshButton.addEventListener('click', async () => {
      const response = await api.refreshChannels();
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

  function setupSeedButton() {
    if (!ui.seedButton) {
      return;
    }

    if (!isLocalhost()) {
      ui.seedButton.hidden = true;
      return;
    }

    ui.seedButton.hidden = false;
    ui.seedButton.addEventListener('click', async () => {
      if (!state.currentUser) {
        showNotification('Sign in before seeding data.', 'warning');
        return;
      }

      ui.seedButton.disabled = true;
      const response = await api.post('/api/dev/seed');
      ui.seedButton.disabled = false;

      if (!response.ok) {
        showNotification('Unable to seed data.', 'error');
        return;
      }

      showNotification('Seed data loaded.', 'success');
      await loadApp();
    });
  }

  async function importSubscriptionsAndRefresh(showToast) {
    if (!state.currentUser || state.currentUser.auth_provider !== 'google') {
      return false;
    }

    const importResponse = await api.importSubscriptions();
    if (!importResponse.ok) {
      if (showToast) {
        showNotification('Unable to import subscriptions.', 'error');
      }
      return false;
    }

    const importPayload = importResponse.data || {};
    const subscriptionCount = typeof importPayload.new_subscriptions === 'number'
      ? importPayload.new_subscriptions
      : 0;

    const refreshResponse = await api.refreshChannels();
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
      showNotification(`Imported ${subscriptionCount} subscriptions and ${videoCount} videos.`, 'success');
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
    setupSearch();
    setupRefresh();
    setupSeedButton();
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
