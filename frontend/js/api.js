// API client for backend communication.

class APIClient {
  constructor(baseURL, timeout) {
    this.baseURL = baseURL || '';
    this.timeout = timeout || 30000;
    this.maxRetries = 3;
  }

  async request(endpoint, method = 'GET', body = null, headers = {}, attempt = 0) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);
    const url = `${this.baseURL}${endpoint}`;
    const start = performance.now();
    const logEvent = typeof window.logApiEvent === 'function' ? window.logApiEvent : null;

    const options = {
      method,
      credentials: 'include',
      signal: controller.signal,
      headers: {
        ...headers
      }
    };

    if (body !== null) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }

    if (logEvent) {
      logEvent(`→ ${method} ${endpoint}`, 'info');
    }

    try {
      const response = await fetch(url, options);
      clearTimeout(timer);

      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent('auth-required'));
      }

      if (response.status === 429 && attempt < this.maxRetries) {
        const delay = 500 * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
        return this.request(endpoint, method, body, headers, attempt + 1);
      }

      let data = null;
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        data = await response.json();
      }

      if (!response.ok) {
        if (logEvent) {
          const duration = Math.round(performance.now() - start);
          logEvent(`← ${method} ${endpoint} ${response.status} (${duration}ms)`, 'error');
        }
        return {
          ok: false,
          status: response.status,
          error: data && data.error ? data.error : 'Request failed',
          tracking_id: data && data.tracking_id ? data.tracking_id : null
        };
      }

      if (logEvent) {
        const duration = Math.round(performance.now() - start);
        logEvent(`← ${method} ${endpoint} ${response.status} (${duration}ms)`, 'success');
      }
      return { ok: true, status: response.status, data };
    } catch (error) {
      clearTimeout(timer);
      const isDev = ['localhost', '127.0.0.1'].includes(window.location.hostname);
      if (isDev) {
        console.error('API request failed', error);
      }
      if (logEvent) {
        const duration = Math.round(performance.now() - start);
        logEvent(`× ${method} ${endpoint} network error (${duration}ms)`, 'error');
      }
      return { ok: false, status: 0, error: 'Network error', tracking_id: null };
    }
  }

  async get(endpoint, params = {}) {
    const query = new URLSearchParams(params).toString();
    const url = query ? `${endpoint}?${query}` : endpoint;
    return this.request(url, 'GET');
  }

  async post(endpoint, body = {}) {
    return this.request(endpoint, 'POST', body);
  }

  async put(endpoint, body = {}) {
    return this.request(endpoint, 'PUT', body);
  }

  async delete(endpoint) {
    return this.request(endpoint, 'DELETE');
  }

  // Auth endpoints
  login(username) {
    return this.post('/api/auth/login', { username });
  }

  logout() {
    return this.post('/api/auth/logout');
  }

  getAuthProvider() {
    return this.get('/api/auth/provider');
  }

  getUsers() {
    return this.get('/api/auth/users');
  }

  getCurrentUser() {
    return this.get('/api/auth/current');
  }

  updateProfile(data) {
    return this.put('/api/auth/profile', data);
  }

  getVideoSummary(days = 7) {
    return this.get('/api/videos/summary', { days });
  }

  // Channel endpoints
  getChannels() {
    return this.get('/api/channels');
  }

  subscribe(youtubeChannelId) {
    return this.post('/api/channels/subscribe', { youtube_channel_id: youtubeChannelId });
  }

  unsubscribe(channelId) {
    return this.delete(`/api/channels/${channelId}/unsubscribe`);
  }

  refreshChannels(channelId) {
    return this.post('/api/channels/refresh', channelId ? { channel_id: channelId } : {});
  }

  importSubscriptions(options = {}) {
    return this.post('/api/channels/import', options);
  }

  getChannelVideos(channelId, limit = 20, offset = 0) {
    return this.get(`/api/channels/${channelId}/videos`, { limit, offset });
  }

  // Video endpoints
  getLatestVideos(limit = 50, offset = 0, options = {}) {
    const params = { limit, offset, ...options };
    return this.get('/api/videos/latest', params);
  }

  getVideosByTheme(themeId, limit = 50, offset = 0, options = {}) {
    const params = { limit, offset, ...options };
    return this.get(`/api/videos/by-theme/${themeId}`, params);
  }

  markAsWatched(videoId, deviceId) {
    return this.post(`/api/videos/${videoId}/watch`, deviceId ? { device_id: deviceId } : {});
  }

  markAsUnwatched(videoId) {
    return this.delete(`/api/videos/${videoId}/unwatch`);
  }

  searchVideos(query, filters = {}) {
    const params = { q: query, ...filters };
    return this.get('/api/videos/search', params);
  }

  // Theme endpoints
  getThemes() {
    return this.get('/api/themes');
  }

  createTheme(name, color) {
    return this.post('/api/themes', { name, color });
  }

  updateTheme(themeId, name, color) {
    return this.put(`/api/themes/${themeId}`, { name, color });
  }

  deleteTheme(themeId) {
    return this.delete(`/api/themes/${themeId}`);
  }

  async addChannelsToTheme(themeId, channelIds) {
    const ids = Array.isArray(channelIds) ? channelIds : [channelIds];
    const results = [];
    for (const channelId of ids) {
      results.push(await this.post(`/api/themes/${themeId}/channels`, { channel_id: channelId }));
    }
    return results;
  }

  removeChannelFromTheme(themeId, channelId) {
    return this.delete(`/api/themes/${themeId}/channels/${channelId}`);
  }

  // Device endpoints
  registerDevice(deviceIdentifier, userAgent) {
    return this.post('/api/devices/register', {
      device_identifier: deviceIdentifier,
      user_agent: userAgent
    });
  }

  getDevices() {
    return this.get('/api/devices');
  }

  setDeviceType(deviceId, deviceType) {
    return this.put(`/api/devices/${deviceId}/type`, { device_type: deviceType });
  }

  deleteDevice(deviceId) {
    return this.delete(`/api/devices/${deviceId}`);
  }

  detectDevice(userAgent, screenWidth, screenHeight) {
    return this.post('/api/devices/detect', {
      user_agent: userAgent,
      screen_width: screenWidth,
      screen_height: screenHeight
    });
  }
}

window.APIClient = APIClient;
