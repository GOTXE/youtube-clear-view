// API client for backend communication.

class APIClient {
  constructor(baseURL, timeout) {
    this.baseURL = baseURL || '';
    this.timeout = timeout || 30000;
    this.maxRetries = 3;
    this._csrfToken = null;
  }

  setCsrfToken(token) {
    this._csrfToken = token || null;
  }

  async request(endpoint, method = 'GET', body = null, headers = {}, attempt = 0) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);
    const url = `${this.baseURL}${endpoint}`;
    const mergedHeaders = { ...headers };
    // Attach CSRF token to state-changing requests
    if (this._csrfToken && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
      mergedHeaders['X-CSRF-Token'] = this._csrfToken;
    }
    const options = {
      method,
      credentials: 'include',
      signal: controller.signal,
      headers: mergedHeaders
    };

    if (body !== null) {
      mergedHeaders['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
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
        return {
          ok: false,
          status: response.status,
          error: data && data.error ? data.error : 'Request failed',
          tracking_id: data && data.tracking_id ? data.tracking_id : null
        };
      }

      return { ok: true, status: response.status, data };
    } catch (error) {
      clearTimeout(timer);
      const isDev = ['localhost', '127.0.0.1'].includes(window.location.hostname);
      if (isDev) {
        console.error('API request failed', error);
      }
      return { ok: false, status: 0, error: 'Network error', tracking_id: null };
    }
  }

  async get(endpoint, params = {}) {
    const safeParams = Object.entries(params).reduce((acc, [key, value]) => {
      if (value !== undefined && value !== null) {
        acc[key] = value;
      }
      return acc;
    }, {});
    const query = new URLSearchParams(safeParams).toString();
    const url = query ? `${endpoint}?${query}` : endpoint;
    return this.request(url, 'GET');
  }

  async post(endpoint, body = {}) {
    return this.request(endpoint, 'POST', body);
  }

  async put(endpoint, body = {}) {
    return this.request(endpoint, 'PUT', body);
  }

  async delete(endpoint, body = null) {
    return this.request(endpoint, 'DELETE', body);
  }

  // Auth endpoints
  login(username, password) {
    const body = password ? { username, password } : { username };
    return this.post('/api/auth/login', body);
  }

  register(username, password) {
    return this.post('/api/auth/register', { username, password });
  }

  completeSetup(username, password) {
    return this.post('/api/auth/google/complete-setup', { username, password });
  }

  changePassword(currentPassword, newPassword) {
    return this.post('/api/auth/profile/password', { current_password: currentPassword, new_password: newPassword });
  }

  googleLinkUrl() {
    return this.get('/api/auth/google/link');
  }

  fallbackLogin(identifier, code, method) {
    return this.post('/api/auth/fallback-login', { identifier, code, method });
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

  getSwitchableAccounts() {
    return this.get('/api/auth/accounts');
  }

  switchAccount(userId) {
    return this.post('/api/auth/switch', { user_id: userId });
  }

  startPairing(deviceIdentifier = null) {
    const payload = {};
    if (deviceIdentifier) {
      payload.device_identifier = deviceIdentifier;
    }
    return this.post('/api/auth/pairing/start', payload);
  }

  approvePairing(code) {
    return this.post('/api/auth/pairing/approve', { code });
  }

  claimPairing(publicId) {
    return this.post('/api/auth/pairing/claim', { public_id: publicId });
  }

  getPasskeys() {
    return this.get('/api/auth/passkeys');
  }

  getPasskeyRegistrationOptions(label = '') {
    return this.post('/api/auth/passkeys/register/options', { label });
  }

  verifyPasskeyRegistration(payload) {
    return this.post('/api/auth/passkeys/register/verify', payload);
  }

  deletePasskey(passkeyId) {
    return this.delete(`/api/auth/passkeys/${passkeyId}`);
  }

  getPasskeyAuthenticationOptions() {
    return this.post('/api/auth/passkeys/authenticate/options');
  }

  verifyPasskeyAuthentication(payload) {
    return this.post('/api/auth/passkeys/authenticate/verify', payload);
  }

  getMfaStatus() {
    return this.get('/api/auth/mfa/status');
  }

  disableTotp(code, password) {
    const body = code ? { code } : { password };
    return this.delete('/api/auth/totp', body);
  }

  unlinkGoogle() {
    return this.post('/api/auth/google/unlink');
  }

  setupTotp() {
    return this.post('/api/auth/totp/setup');
  }

  confirmTotp(code) {
    return this.post('/api/auth/totp/confirm', { code });
  }

  regenerateRecoveryCodes(code) {
    return this.post('/api/auth/recovery-codes/regenerate', { code });
  }

  verifyMfaChallenge(code, method) {
    return this.post('/api/auth/mfa/verify', { code, method });
  }

  getAdminSqliteObservability() {
    return this.get('/api/admin/observability/sqlite');
  }

  updateAdminSqliteObservability(enabled) {
    return this.put('/api/admin/observability/sqlite', { enabled });
  }

  getAdminRuntimeState() {
    return this.get('/api/admin/runtime-state');
  }

  getAdminPasswordPolicy() {
    return this.get('/api/admin/security/password-policy');
  }

  updateAdminPasswordPolicy(passwordPolicy) {
    return this.put('/api/admin/security/password-policy', { password_policy: passwordPolicy });
  }

  updateProfile(data) {
    return this.put('/api/auth/profile', data);
  }

  getVideoSummary(days = 7, channelId = null, channelYtId = null) {
    const params = { days };
    if (channelId !== null && channelId !== undefined) {
      params.channel_id = channelId;
    }
    if (channelYtId) {
      params.yt_channel_id = channelYtId;
    }
    return this.get('/api/videos/summary', params);
  }

  // Channel endpoints
  getChannels() {
    return this.get('/api/channels');
  }

  subscribe(ytChannelId) {
    return this.post('/api/channels/subscribe', { yt_channel_id: ytChannelId });
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

  saveProgress(videoId, positionSeconds, durationSeconds) {
    return this.put(`/api/videos/${videoId}/progress`, {
      position_seconds: positionSeconds,
      duration_seconds: durationSeconds
    });
  }

  clearProgress(videoId) {
    return this.delete(`/api/videos/${videoId}/progress`);
  }

  getInProgressVideos(limit = 20, offset = 0) {
    return this.get('/api/videos/in-progress', { limit, offset });
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

  updateDevicePreferences(deviceId, preferences) {
    return this.put(`/api/devices/${deviceId}/preferences`, preferences);
  }

  deleteDevice(deviceId) {
    return this.delete(`/api/devices/${deviceId}`);
  }

  updateDeviceName(deviceId, displayName) {
    return this.put(`/api/devices/${deviceId}/name`, { display_name: displayName });
  }

  detectDevice(userAgent, screenWidth, screenHeight) {
    return this.post('/api/devices/detect', {
      user_agent: userAgent,
      screen_width: screenWidth,
      screen_height: screenHeight
    });
  }

  // Category endpoints
  getCategories() {
    return this.get('/api/categories');
  }

  getCategoryDetails(categoryId) {
    return this.get(`/api/categories/${categoryId}`);
  }

  getCategoryChannels(categoryId, limit = 20, offset = 0) {
    return this.get(`/api/categories/${categoryId}/channels`, { limit, offset });
  }

  getCategoryVideos(categoryId, limit = 20, offset = 0) {
    return this.get(`/api/categories/${categoryId}/videos`, { limit, offset });
  }

  getChannelCategory(channelId) {
    return this.get(`/api/channels/${channelId}/category`);
  }

  setChannelCategory(channelId, categoryName) {
    return this.put(`/api/channels/${channelId}/category`, { category_name: categoryName });
  }

  resetChannelCategory(channelId) {
    return this.delete(`/api/channels/${channelId}/category`);
  }

  reclassifyAllChannels() {
    return this.post('/api/categories/reclassify-all');
  }

  getClassifierStatus() {
    return this.get('/api/categories/status');
  }

  // Rating endpoints
  rateChannel(channelId, rating) {
    return this.put(`/api/channels/${channelId}/rating`, { rating });
  }

  removeChannelRating(channelId) {
    return this.delete(`/api/channels/${channelId}/rating`);
  }

  // Channel enrichment (fetch topic_ids from YouTube API)
  enrichChannels(channelId = null, limit = 50) {
    const payload = { limit };
    if (channelId) {
      payload.channel_id = channelId;
    }
    return this.post('/api/channels/enrich', payload);
  }

  enrichChannelVideoEvidence(channelId = null, limit = 25, maxResults = 12, onlyUnclassified = true) {
    const payload = { limit, max_results: maxResults, only_unclassified: onlyUnclassified };
    if (channelId) {
      payload.channel_id = channelId;
    }
    return this.post('/api/channels/enrich-video-evidence', payload);
  }

  // Background classification task
  startClassifyTask() {
    return this.post('/api/channels/classify');
  }

  getClassifyStatus() {
    return this.get('/api/channels/classify/status');
  }

  // Settings endpoints
  getSettings() {
    return this.get('/api/settings');
  }

  updateSettings(data) {
    return this.put('/api/settings', data);
  }
}

window.APIClient = APIClient;
