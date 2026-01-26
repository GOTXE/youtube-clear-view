// Application configuration
// All API connections use HTTPS via reverse proxy
const APP_CONFIG = {
  // Backend API URL (via reverse proxy, HTTPS only)
  API_BASE_URL: 'https://api.example.com/api',

  // API version
  API_VERSION: 'v1',

  // Request timeout (ms)
  REQUEST_TIMEOUT: 30000,

  // YT configuration
  YT_BASE_URL: 'https://www.youtube.com',

  // Pagination configuration (for infinite carousel)
  DEFAULT_PAGE_SIZE: 20,
  VIDEOS_PER_LOAD: 20,  // Videos loaded per infinite scroll trigger
  INITIAL_LOAD_COUNT: 50,  // Initial video load count

  // UI configuration
  NOTIFICATION_DURATION: 3000,

  // Theme configuration
  DEFAULT_THEME: 'light',  // 'light' or 'dark'

  // Device type constants
  DEVICE_TYPES: {
    TV: 'tv',
    TABLET: 'tablet',
    MOBILE: 'mobile',
    DESKTOP: 'desktop'
  },

  // Breakpoints for responsive detection (px)
  BREAKPOINTS: {
    MOBILE_MAX: 767,
    TABLET_MIN: 768,
    TABLET_MAX: 1919,
    TV_MIN: 1920
  }
};

// Export configuration
window.APP_CONFIG = APP_CONFIG;
