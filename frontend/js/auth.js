// Authentication management with httpOnly cookie sessions.

(() => {
  let currentUser = null;
  let cachedUsers = [];
  let listenersReady = false;
  let authMode = 'local';
  let googleLoginUrl = null;
  let localSignupEnabled = false;
  let pendingMfaChallenge = null;

  const userSelector = document.getElementById('user-selector');
  const googleLoginButton = document.getElementById('google-login-button');

  const ui = {
    userSelector,
    userSelectorWrapper: userSelector ? userSelector.closest('label') : null,
    currentUserLabel: document.getElementById('current-user'),
    currentUserAvatarShell: document.getElementById('current-user-avatar-shell'),
    currentUserAvatar: document.getElementById('current-user-avatar'),
    currentUserAvatarFallback: document.getElementById('current-user-avatar-fallback'),
    currentUserName: document.getElementById('current-user-name'),
    sessionInfo: document.querySelector('.session-info'),
    appRoot: document.getElementById('app'),
    accountActions: document.getElementById('menu-account-actions') || document.querySelector('.header-actions'),
    systemActions: document.getElementById('menu-system-actions'),
    logoutButton: document.getElementById('logout-button'),
    googleLoginButton,
    userSummary: document.querySelector('.user-summary'),
    newUserButton: null,
    switchUserButton: null,
    accountSwitchButton: null,
    pairingLoginButton: null,
    pairingApproveButton: null,
    fallbackLoginButton: null,
    passkeyLoginButton: null,
    managePasskeysButton: null,
    manageMfaButton: null,
    manageAdminButton: null,
    statusMessage: null,
    modal: null,
    accountModal: null,
    pairingLoginModal: null,
    pairingApproveModal: null,
    fallbackLoginModal: null,
    passkeyModal: null,
    mfaModal: null,
    adminModal: null,
    mfaChallengeModal: null
  };

  const mfaState = {
    status: null,
    setupSecret: null,
    otpauthUrl: null,
    recoveryCodes: []
  };

  const pairingState = {
    current: null,
    claimTimerId: null,
    countdownTimerId: null
  };

  const adminState = {
    metrics: null,
    runtimeState: null,
    passwordPolicy: null,
    users: null
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

  function isGoogleMode() {
    return authMode === 'google';
  }

  function passkeysSupported() {
    return Boolean(
      window.ytcvPasskeys
      && typeof window.ytcvPasskeys.isSupported === 'function'
      && window.ytcvPasskeys.isSupported()
    );
  }

  function isAdminUser() {
    return Boolean(currentUser && currentUser.is_admin);
  }

  function getKnownGoogleAccounts() {
    return Array.isArray(cachedUsers) ? cachedUsers : [];
  }

  function resolveLoginUrl(path) {
    if (!path) {
      return null;
    }

    try {
      return new URL(path, window.APP_CONFIG.API_BASE_URL).toString();
    } catch (error) {
      return path;
    }
  }

  function applyThemePreference(themePreference) {
    if (document.body && document.body.classList.contains('gestor-body')) {
      if (ui.appRoot) {
        ui.appRoot.setAttribute('data-theme', 'light');
      }
      document.documentElement.setAttribute('data-theme', 'light');
      return;
    }
    if (ui.appRoot) {
      ui.appRoot.setAttribute('data-theme', 'dark');
    }
    document.documentElement.setAttribute('data-theme', 'dark');
  }

  function setStatusMessage(message, type = 'info') {
    if (!ui.statusMessage) {
      return;
    }

    ui.statusMessage.textContent = message;
    if (!message) {
      ui.statusMessage.removeAttribute('role');
    } else {
      ui.statusMessage.setAttribute('role', type === 'error' ? 'alert' : 'status');
    }

    if (type === 'error') {
      ui.statusMessage.style.color = 'var(--error)';
      return;
    }

    if (type === 'success') {
      ui.statusMessage.style.color = 'var(--success)';
      return;
    }

    ui.statusMessage.style.color = '';
  }

  function syncCurrentUserAvatar(user) {
    if (!ui.currentUserAvatar || !ui.currentUserAvatarShell) {
      return;
    }

    const avatarUrl = user && user.google_avatar_url ? user.google_avatar_url : null;
    const fallbackLabel = ((user && (user.display_name || user.username || user.email)) || '?').trim().charAt(0) || '?';
    if (ui.currentUserAvatarFallback) {
      ui.currentUserAvatarFallback.textContent = fallbackLabel;
    }

    if (!avatarUrl) {
      ui.currentUserAvatarShell.hidden = true;
      ui.currentUserAvatarShell.classList.remove('is-loaded');
      ui.currentUserAvatar.removeAttribute('src');
      ui.currentUserAvatar.alt = '';
      return;
    }

    ui.currentUserAvatarShell.hidden = false;
    ui.currentUserAvatarShell.classList.remove('is-loaded');
    ui.currentUserAvatar.referrerPolicy = 'no-referrer';
    ui.currentUserAvatar.decoding = 'async';
    ui.currentUserAvatar.onload = () => {
      if (ui.currentUserAvatarShell) {
        ui.currentUserAvatarShell.classList.add('is-loaded');
      }
    };
    ui.currentUserAvatar.onerror = () => {
      if (ui.currentUserAvatarShell) {
        ui.currentUserAvatarShell.classList.remove('is-loaded');
      }
      ui.currentUserAvatar.removeAttribute('src');
    };
    ui.currentUserAvatar.src = avatarUrl;
    ui.currentUserAvatar.alt = user.display_name || user.username || 'User avatar';
  }

  async function maybeShowSecurityReminder(user) {
    if (!user || document.body.classList.contains('gestor-body')) {
      return;
    }
    if (!user.security_reminder_due) {
      return;
    }

    if (typeof window.showNotification === 'function') {
      window.showNotification(t('securityReminderMissingTotpOrPasskey'), 'info');
    } else {
      setStatusMessage(t('securityReminderMissingTotpOrPasskey'), 'info');
    }

    const api = getApiClient();
    if (api) {
      await api.acknowledgeSecurityReminder();
    }
    currentUser = { ...user, security_reminder_due: false };
  }

  function stopPairingClaimPolling() {
    if (pairingState.claimTimerId) {
      window.clearInterval(pairingState.claimTimerId);
      pairingState.claimTimerId = null;
    }
    if (pairingState.countdownTimerId) {
      window.clearInterval(pairingState.countdownTimerId);
      pairingState.countdownTimerId = null;
    }
  }

  function closePairingLoginModal() {
    stopPairingClaimPolling();
    pairingState.current = null;
    if (!ui.pairingLoginModal) {
      return;
    }
    ui.pairingLoginModal.hidden = true;
  }

  function closePairingApproveModal() {
    if (!ui.pairingApproveModal) {
      return;
    }
    ui.pairingApproveModal.hidden = true;
  }

  function closeFallbackLoginModal() {
    if (!ui.fallbackLoginModal) {
      return;
    }
    ui.fallbackLoginModal.hidden = true;
  }

  function closeAdminModal() {
    if (!ui.adminModal) {
      return;
    }
    ui.adminModal.hidden = true;
  }

  function closeMfaChallengeModal() {
    if (!ui.mfaChallengeModal) {
      return;
    }
    ui.mfaChallengeModal.hidden = true;
  }

  function buildMfaChallengeModal() {
    if (ui.mfaChallengeModal) {
      return ui.mfaChallengeModal;
    }

    const overlay = document.createElement('section');
    overlay.className = 'confirm-modal-overlay';
    overlay.id = 'mfa-challenge-modal';
    overlay.hidden = true;

    const modal = document.createElement('div');
    modal.className = 'confirm-modal account-switcher-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'mfa-challenge-title');

    const header = document.createElement('header');
    header.className = 'confirm-modal__header';

    const title = document.createElement('h2');
    title.id = 'mfa-challenge-title';
    title.className = 'heading-2';
    title.textContent = t('completeMfaChallenge');

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'confirm-modal__close';
    closeButton.setAttribute('aria-label', t('close'));
    closeButton.textContent = '✕';

    header.appendChild(title);
    header.appendChild(closeButton);

    const body = document.createElement('div');
    body.className = 'confirm-modal__body';

    const description = document.createElement('p');
    description.className = 'body';
    description.id = 'mfa-challenge-description';

    const label = document.createElement('label');
    label.className = 'field';

    const labelText = document.createElement('span');
    labelText.className = 'field__label';
    labelText.textContent = t('totpCodeLabel');

    const input = document.createElement('input');
    input.type = 'text';
    input.inputMode = 'numeric';
    input.autocomplete = 'one-time-code';
    input.className = 'field__input';
    input.id = 'mfa-challenge-code';
    input.placeholder = t('totpCodePlaceholder');

    label.appendChild(labelText);
    label.appendChild(input);

    const actions = document.createElement('div');
    actions.className = 'field__group';

    const verifyButton = document.createElement('button');
    verifyButton.type = 'button';
    verifyButton.className = 'button';
    verifyButton.id = 'mfa-challenge-verify-button';
    verifyButton.textContent = t('verifyTotpCode');

    const recoveryButton = document.createElement('button');
    recoveryButton.type = 'button';
    recoveryButton.className = 'button button--ghost';
    recoveryButton.id = 'mfa-challenge-recovery-button';
    recoveryButton.textContent = t('useRecoveryCode');

    actions.appendChild(verifyButton);
    actions.appendChild(recoveryButton);

    body.appendChild(description);
    body.appendChild(label);
    body.appendChild(actions);

    modal.appendChild(header);
    modal.appendChild(body);
    overlay.appendChild(modal);

    closeButton.addEventListener('click', closeMfaChallengeModal);
    overlay.addEventListener('click', event => {
      if (event.target === overlay) {
        closeMfaChallengeModal();
      }
    });
    verifyButton.addEventListener('click', async () => {
      await completeMfaChallenge('totp');
    });
    recoveryButton.addEventListener('click', async () => {
      await completeMfaChallenge('recovery_code');
    });

    ui.mfaChallengeModal = overlay;
    return overlay;
  }

  function renderMfaChallengeModal() {
    if (!ui.mfaChallengeModal || !pendingMfaChallenge) {
      return;
    }

    const description = ui.mfaChallengeModal.querySelector('#mfa-challenge-description');
    if (!description) {
      return;
    }

    const userLabel = pendingMfaChallenge.display_name || pendingMfaChallenge.email || '';
    description.textContent = userLabel
      ? t('mfaChallengeForUser', { user: userLabel })
      : t('mfaChallengeDescription');
  }

  function setPendingMfaChallenge(challenge) {
    currentUser = null;
    pendingMfaChallenge = challenge;
    closeAdminModal();
    const modal = buildMfaChallengeModal();
    if (!modal.parentNode) {
      document.body.appendChild(modal);
    }
    renderMfaChallengeModal();
    modal.hidden = false;
    setStatusMessage(t('mfaChallengeRequired'), 'info');
  }

  function applyAuthMode() {
    const selectorContainer = ui.userSelectorWrapper || ui.userSelector;
    const googleMode = isGoogleMode();

    if (selectorContainer) {
      selectorContainer.hidden = googleMode;
    }

    if (ui.newUserButton) {
      ui.newUserButton.hidden = googleMode || !localSignupEnabled || Boolean(currentUser);
    }

    if (ui.googleLoginButton) {
      ui.googleLoginButton.hidden = !googleMode || Boolean(currentUser);
    }

    if (ui.accountSwitchButton) {
      ui.accountSwitchButton.hidden = !googleMode;
    }

    if (ui.pairingLoginButton) {
      ui.pairingLoginButton.hidden = Boolean(currentUser);
    }

    if (ui.pairingApproveButton) {
      ui.pairingApproveButton.hidden = !currentUser;
    }

    if (ui.passkeyLoginButton) {
      ui.passkeyLoginButton.hidden = Boolean(currentUser) || !passkeysSupported();
    }

    if (ui.manageAdminButton) {
      ui.manageAdminButton.hidden = !isAdminUser();
    }

    updateSwitchUserLabel();
    updateLoginLink();
  }

  function updateLoginLink() {
    if (!ui.currentUserLabel) {
      return;
    }

    if (currentUser || !googleLoginUrl || !isGoogleMode()) {
      if (!currentUser) {
        ui.currentUserLabel.textContent = t('notSignedIn');
      }
      ui.currentUserLabel.removeAttribute('href');
      ui.currentUserLabel.classList.remove('session-info__link');
      return;
    }

    const resolved = resolveLoginUrl(googleLoginUrl);
    if (resolved) {
      ui.currentUserLabel.textContent = t('signInWithGoogle');
      ui.currentUserLabel.setAttribute('href', resolved);
      ui.currentUserLabel.classList.add('session-info__link');
    }
  }

  async function loadAuthProvider() {
    const api = getApiClient();
    if (!api) {
      return;
    }

    const response = await api.getAuthProvider();
    if (response.ok && response.data && response.data.auth_mode) {
      authMode = response.data.auth_mode;
      googleLoginUrl = response.data.google_login_url;
      localSignupEnabled = Boolean(response.data.local_signup_enabled);
      window.dispatchEvent(new CustomEvent('auth:provider-loaded', { detail: response.data }));
    }

    applyAuthMode();
  }

  function handleAuthErrorParam() {
    const params = new URLSearchParams(window.location.search);
    const errorCode = params.get('auth_error');
    if (!errorCode) {
      return;
    }

    if (isGoogleMode()) {
      setStatusMessage(t('googleSignInFailed'), 'error');
    }

    params.delete('auth_error');
    const newQuery = params.toString();
    const newUrl = newQuery ? `${window.location.pathname}?${newQuery}` : window.location.pathname;
    window.history.replaceState({}, document.title, newUrl);
  }

  function startGoogleLogin() {
    if (!isGoogleMode()) {
      return;
    }

    const loginPath = googleLoginUrl || '/api/auth/google';
    const resolved = resolveLoginUrl(loginPath);
    if (!resolved) {
      setStatusMessage(t('googleLoginUnavailable'), 'error');
      return;
    }

    window.location.href = resolved;
  }

  function ensureButtons() {
    if (!ui.accountActions) {
      return;
    }

    if (!ui.newUserButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'new-user-button';
      button.className = 'menu-item';
      button.addEventListener('click', () => {
        openCreateUserModal();
      });
      ui.newUserButton = button;
      ui.accountActions.appendChild(button);
    }

    if (!ui.switchUserButton) {
      const button = ui.logoutButton || document.createElement('button');
      button.type = 'button';
      if (!ui.logoutButton) {
        button.id = 'logout-button';
        button.className = 'menu-item';
        ui.accountActions.appendChild(button);
      }
      button.addEventListener('click', async () => {
        await logout();
      });
      ui.switchUserButton = button;
    }

    if (!ui.accountSwitchButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'switch-google-account-button';
      button.className = 'menu-item';
      button.hidden = !isGoogleMode();
      button.addEventListener('click', async () => {
        await openAccountSwitcherModal();
      });
      ui.accountSwitchButton = button;
      ui.accountActions.insertBefore(button, ui.switchUserButton || null);
    }

    if (!ui.pairingLoginButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'pairing-login-button';
      button.className = 'menu-item';
      button.hidden = Boolean(currentUser);
      button.addEventListener('click', async () => {
        await openPairingLoginModal();
      });
      ui.pairingLoginButton = button;
      ui.accountActions.insertBefore(button, ui.googleLoginButton || null);
    }

    if (!ui.pairingApproveButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'approve-pairing-button';
      button.className = 'menu-item';
      button.hidden = true;
      button.addEventListener('click', async () => {
        await openPairingApproveModal();
      });
      ui.pairingApproveButton = button;
      ui.accountActions.insertBefore(button, ui.switchUserButton || null);
    }

    if (!ui.fallbackLoginButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'fallback-login-button';
      button.className = 'menu-item';
      button.hidden = Boolean(currentUser);
      button.addEventListener('click', async () => {
        await openFallbackLoginModal();
      });
      ui.fallbackLoginButton = button;
      ui.accountActions.insertBefore(button, ui.googleLoginButton || null);
    }

    if (!ui.passkeyLoginButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'passkey-login-button';
      button.className = 'menu-item';
      button.hidden = !passkeysSupported();
      button.addEventListener('click', async () => {
        await signInWithPasskey();
      });
      ui.passkeyLoginButton = button;
      ui.accountActions.insertBefore(button, ui.googleLoginButton || null);
    }

    if (!ui.manageAdminButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'manage-admin-button';
      button.className = 'menu-item';
      button.hidden = true;
      button.addEventListener('click', async () => {
        if (window.location.pathname !== '/gestor' && window.location.pathname !== '/gestor/') {
          window.location.assign('/gestor');
          return;
        }
        await openAdminModal();
      });
      ui.manageAdminButton = button;
      if (ui.systemActions) {
        ui.systemActions.appendChild(button);
      } else {
        ui.accountActions.insertBefore(button, ui.switchUserButton || null);
      }
    }

    if (!ui.statusMessage && ui.userSummary) {
      const status = document.createElement('span');
      status.className = 'caption';
      status.id = 'auth-status';
      ui.statusMessage = status;
      ui.userSummary.appendChild(status);
    }

    if (ui.newUserButton) {
      ui.newUserButton.textContent = t('newUser');
    }
    if (ui.switchUserButton) {
      ui.switchUserButton.textContent = t('signOut');
    }
    if (ui.accountSwitchButton) {
      ui.accountSwitchButton.textContent = t('switchAccount');
    }
    if (ui.pairingLoginButton) {
      ui.pairingLoginButton.textContent = t('signInWithDeviceCode');
    }
    if (ui.pairingApproveButton) {
      ui.pairingApproveButton.textContent = t('approveDeviceCode');
    }
    if (ui.fallbackLoginButton) {
      ui.fallbackLoginButton.textContent = t('signInWithTotpOrRecovery');
    }
    if (ui.passkeyLoginButton) {
      ui.passkeyLoginButton.textContent = t('signInWithPasskey');
    }
    if (ui.manageAdminButton) {
      ui.manageAdminButton.textContent = t('adminPanel');
    }

    updateSwitchUserLabel();
  }

  function ensureGoogleLoginListener() {
    if (!ui.googleLoginButton || ui.googleLoginButton.dataset.listenerAttached === 'true') {
      return;
    }

    ui.googleLoginButton.addEventListener('click', () => {
      startGoogleLogin();
    });

    ui.googleLoginButton.dataset.listenerAttached = 'true';
  }

  function updateSwitchUserLabel() {
    if (!ui.switchUserButton) {
      return;
    }

    ui.switchUserButton.textContent = t('signOut');
    if (ui.accountSwitchButton) {
      ui.accountSwitchButton.textContent = t('switchAccount');
    }
  }

  function ensureUserSelectorListener() {
    if (!ui.userSelector || ui.userSelector.dataset.listenerAttached === 'true') {
      return;
    }

    ui.userSelector.addEventListener('change', async event => {
      const username = event.target.value;
      if (!username) {
        return;
      }

      await loginUser(username);
    });

    ui.userSelector.dataset.listenerAttached = 'true';
  }

  function setAuthenticated(user, options = {}) {
    const { broadcast = true } = options;
    currentUser = user;
    pendingMfaChallenge = null;
    closeMfaChallengeModal();
    closeAdminModal();
    closeFallbackLoginModal();
    closePairingLoginModal();
    closePairingApproveModal();
    if (ui.currentUserLabel) {
      const displayName = user.display_name || user.username;
      ui.currentUserLabel.textContent = t('signedInAsPrefix');
      if (ui.currentUserName) {
        ui.currentUserName.textContent = displayName;
      }
      if (ui.sessionInfo) {
        ui.sessionInfo.classList.remove('session-info--alert');
      }
    }
    syncCurrentUserAvatar(user);

    if (ui.userSelector) {
      ui.userSelector.value = user.username || '';
    }

    const selectorContainer = ui.userSelectorWrapper || ui.userSelector;
    if (selectorContainer) {
      selectorContainer.hidden = true;
    }

    if (ui.newUserButton) {
      ui.newUserButton.hidden = true;
    }

    if (ui.switchUserButton) {
      ui.switchUserButton.hidden = false;
    }

    if (ui.googleLoginButton) {
      ui.googleLoginButton.hidden = true;
    }

    if (ui.accountSwitchButton) {
      ui.accountSwitchButton.hidden = !isGoogleMode();
    }

    if (ui.pairingLoginButton) {
      ui.pairingLoginButton.hidden = true;
    }

    if (ui.pairingApproveButton) {
      ui.pairingApproveButton.hidden = false;
    }

    if (ui.fallbackLoginButton) {
      ui.fallbackLoginButton.hidden = true;
    }

    if (ui.passkeyLoginButton) {
      ui.passkeyLoginButton.hidden = true;
    }

    if (ui.manageAdminButton) {
      ui.manageAdminButton.hidden = !isAdminUser();
    }

    updateSwitchUserLabel();
    updateLoginLink();
    setStatusMessage('');
    applyThemePreference(user.theme_preference);
    if (isGoogleMode()) {
      loadSwitchableAccounts();
    }
    if (broadcast) {
      window.dispatchEvent(new CustomEvent('auth:changed', { detail: { user } }));
    }
    void maybeShowSecurityReminder(user);
  }

  function setUnauthenticated() {
    currentUser = null;
    closeAdminModal();
    closePairingApproveModal();
    if (ui.currentUserLabel) {
      ui.currentUserLabel.textContent = t('notSignedIn');
    }
    if (ui.currentUserName) {
      ui.currentUserName.textContent = '';
    }
    syncCurrentUserAvatar(null);
    if (ui.sessionInfo) {
      ui.sessionInfo.classList.add('session-info--alert');
    }

    if (ui.userSelector) {
      ui.userSelector.value = '';
    }

    const selectorContainer = ui.userSelectorWrapper || ui.userSelector;
    const googleMode = isGoogleMode();
    if (selectorContainer) {
      selectorContainer.hidden = googleMode;
    }

    if (ui.newUserButton) {
      ui.newUserButton.hidden = googleMode;
    }

    if (ui.switchUserButton) {
      ui.switchUserButton.hidden = true;
    }

    if (ui.googleLoginButton) {
      ui.googleLoginButton.hidden = !googleMode;
    }

    if (ui.accountSwitchButton) {
      ui.accountSwitchButton.hidden = !googleMode || getKnownGoogleAccounts().length === 0;
    }

    if (ui.pairingLoginButton) {
      ui.pairingLoginButton.hidden = false;
    }

    if (ui.pairingApproveButton) {
      ui.pairingApproveButton.hidden = true;
    }

    if (ui.fallbackLoginButton) {
      ui.fallbackLoginButton.hidden = false;
    }

    if (ui.passkeyLoginButton) {
      ui.passkeyLoginButton.hidden = !passkeysSupported();
    }

    if (ui.manageAdminButton) {
      ui.manageAdminButton.hidden = true;
    }

    if (pendingMfaChallenge) {
      setStatusMessage(t('mfaChallengeRequired'), 'error');
    } else if (passkeysSupported()) {
      setStatusMessage(googleMode ? t('statusSignInGoogleOrPasskeyOrCode') : t('statusSelectUserPasskeyOrCode'));
    } else {
      setStatusMessage(googleMode ? t('statusSignInGoogleOrCode') : t('statusSelectUserOrCode'));
    }
    updateLoginLink();
    window.dispatchEvent(new CustomEvent('auth:changed', { detail: { user: null } }));
  }

  function renderUserOptions(users) {
    if (!ui.userSelector) {
      return;
    }

    while (ui.userSelector.firstChild) {
      ui.userSelector.removeChild(ui.userSelector.firstChild);
    }

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = users.length ? t('selectUser') : t('noUsersYet');
    ui.userSelector.appendChild(placeholder);

    users.forEach(user => {
      const option = document.createElement('option');
      option.value = user.username;
      option.textContent = user.display_name || user.username;
      ui.userSelector.appendChild(option);
    });
  }

  async function loadUsers() {
    if (isGoogleMode()) {
      return;
    }

    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return;
    }

    const response = await api.getUsers();
    if (!response.ok) {
      setStatusMessage(t('unableToLoadUsers'), 'error');
      return;
    }

    cachedUsers = response.data || [];
    renderUserOptions(cachedUsers);
  }

  async function loadSwitchableAccounts() {
    if (!isGoogleMode()) {
      return [];
    }

    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return [];
    }

    const response = await api.getSwitchableAccounts();
    if (!response.ok) {
      setStatusMessage(t('unableToLoadAccounts'), 'error');
      return [];
    }

    cachedUsers = response.data && Array.isArray(response.data.accounts)
      ? response.data.accounts
      : [];

    if (ui.accountSwitchButton) {
      ui.accountSwitchButton.hidden = cachedUsers.length === 0 && !currentUser;
    }

    return cachedUsers;
  }

  function buildAccountSwitcherModal() {
    if (ui.accountModal) {
      return ui.accountModal;
    }

    const overlay = document.createElement('section');
    overlay.className = 'confirm-modal-overlay account-switcher-overlay';
    overlay.id = 'account-switcher-modal';
    overlay.hidden = true;

    const modal = document.createElement('div');
    modal.className = 'confirm-modal account-switcher-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'account-switcher-title');

    const header = document.createElement('header');
    header.className = 'confirm-modal__header';

    const title = document.createElement('h2');
    title.id = 'account-switcher-title';
    title.className = 'heading-2';
    title.textContent = t('accountSwitcherTitle');

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'confirm-modal__close';
    closeButton.setAttribute('aria-label', t('close'));
    closeButton.textContent = '✕';

    header.appendChild(title);
    header.appendChild(closeButton);

    const body = document.createElement('div');
    body.className = 'confirm-modal__body';

    const description = document.createElement('p');
    description.className = 'body';
    description.textContent = t('accountSwitcherDescription');

    const list = document.createElement('div');
    list.className = 'field';
    list.id = 'account-switcher-list';

    body.appendChild(description);
    body.appendChild(list);

    const footer = document.createElement('footer');
    footer.className = 'confirm-modal__footer account-switcher-modal__footer';

    const newLoginButton = document.createElement('button');
    newLoginButton.type = 'button';
    newLoginButton.className = 'button account-switcher-modal__primary-action';
    newLoginButton.textContent = t('addGoogleAccount');

    footer.appendChild(newLoginButton);

    modal.appendChild(header);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    closeButton.addEventListener('click', closeAccountSwitcherModal);
    overlay.addEventListener('click', event => {
      if (event.target === overlay) {
        closeAccountSwitcherModal();
      }
    });
    newLoginButton.addEventListener('click', () => {
      closeAccountSwitcherModal();
      startGoogleLogin();
    });

    ui.accountModal = overlay;
    return overlay;
  }

  function closeAccountSwitcherModal() {
    if (!ui.accountModal) {
      return;
    }
    ui.accountModal.hidden = true;
  }

  function renderPairingLoginModal() {
    if (!ui.pairingLoginModal) {
      return;
    }

    const codeNode = ui.pairingLoginModal.querySelector('#pairing-login-code');
    const statusNode = ui.pairingLoginModal.querySelector('#pairing-login-status');
    const retryButton = ui.pairingLoginModal.querySelector('#pairing-login-retry-button');
    if (!codeNode || !statusNode || !retryButton) {
      return;
    }

    if (!pairingState.current) {
      codeNode.textContent = '---- ----';
      statusNode.textContent = t('pairingCodeStarting');
      retryButton.disabled = true;
      return;
    }

    codeNode.textContent = pairingState.current.pairing_code || '---- ----';
    retryButton.disabled = false;
    statusNode.textContent = pairingState.current.status === 'approved'
      ? t('pairingCodeApproved')
      : t('pairingCodeWaiting');
  }

  function buildPairingLoginModal() {
    if (ui.pairingLoginModal) {
      return ui.pairingLoginModal;
    }

    const overlay = document.createElement('section');
    overlay.className = 'confirm-modal-overlay';
    overlay.id = 'pairing-login-modal';
    overlay.hidden = true;

    const modal = document.createElement('div');
    modal.className = 'confirm-modal account-switcher-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'pairing-login-title');

    const header = document.createElement('header');
    header.className = 'confirm-modal__header';

    const title = document.createElement('h2');
    title.id = 'pairing-login-title';
    title.className = 'heading-2';
    title.textContent = t('pairingLoginTitle');

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'confirm-modal__close';
    closeButton.setAttribute('aria-label', t('close'));
    closeButton.textContent = '✕';

    header.appendChild(title);
    header.appendChild(closeButton);

    const body = document.createElement('div');
    body.className = 'confirm-modal__body';

    const description = document.createElement('p');
    description.className = 'body';
    description.textContent = t('pairingLoginDescription');

    const code = document.createElement('div');
    code.className = 'field__group';
    code.id = 'pairing-login-code';

    const status = document.createElement('p');
    status.className = 'caption';
    status.id = 'pairing-login-status';

    body.appendChild(description);
    body.appendChild(code);
    body.appendChild(status);

    const footer = document.createElement('footer');
    footer.className = 'confirm-modal__footer account-switcher-modal__footer';

    const retryButton = document.createElement('button');
    retryButton.type = 'button';
    retryButton.className = 'button';
    retryButton.id = 'pairing-login-retry-button';
    retryButton.textContent = t('generateNewDeviceCode');

    footer.appendChild(retryButton);
    modal.appendChild(header);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    closeButton.addEventListener('click', closePairingLoginModal);
    overlay.addEventListener('click', event => {
      if (event.target === overlay) {
        closePairingLoginModal();
      }
    });
    retryButton.addEventListener('click', async () => {
      await startPairingLogin();
    });

    ui.pairingLoginModal = overlay;
    return overlay;
  }

  function buildPairingApproveModal() {
    if (ui.pairingApproveModal) {
      return ui.pairingApproveModal;
    }

    const overlay = document.createElement('section');
    overlay.className = 'confirm-modal-overlay';
    overlay.id = 'pairing-approve-modal';
    overlay.hidden = true;

    const modal = document.createElement('div');
    modal.className = 'confirm-modal account-switcher-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'pairing-approve-title');

    const header = document.createElement('header');
    header.className = 'confirm-modal__header';

    const title = document.createElement('h2');
    title.id = 'pairing-approve-title';
    title.className = 'heading-2';
    title.textContent = t('pairingApproveTitle');

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'confirm-modal__close';
    closeButton.setAttribute('aria-label', t('close'));
    closeButton.textContent = '✕';

    header.appendChild(title);
    header.appendChild(closeButton);

    const body = document.createElement('div');
    body.className = 'confirm-modal__body';

    const description = document.createElement('p');
    description.className = 'body';
    description.textContent = t('pairingApproveDescription');

    const field = document.createElement('div');
    field.className = 'field';

    const label = document.createElement('span');
    label.className = 'field__label';
    label.textContent = t('pairingCodeLabel');

    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;justify-content:center;gap:0.5rem;';

    const inputStyle = 'text-transform:uppercase;letter-spacing:0.2em;font-family:monospace;text-align:center;font-size:1.25rem;width:6rem;';

    const inputL = document.createElement('input');
    inputL.type = 'text';
    inputL.className = 'field__input';
    inputL.id = 'pairing-approve-code-l';
    inputL.autocomplete = 'off';
    inputL.autocapitalize = 'characters';
    inputL.maxLength = 4;
    inputL.placeholder = 'XXXX';
    inputL.style.cssText = inputStyle;

    const sep = document.createElement('span');
    sep.textContent = '–';
    sep.style.cssText = 'font-size:1.5rem;font-weight:bold;user-select:none;';

    const inputR = document.createElement('input');
    inputR.type = 'text';
    inputR.className = 'field__input';
    inputR.id = 'pairing-approve-code-r';
    inputR.autocomplete = 'off';
    inputR.autocapitalize = 'characters';
    inputR.maxLength = 4;
    inputR.placeholder = 'XXXX';
    inputR.style.cssText = inputStyle;

    // Auto-uppercase + auto-jump to right input after 4 chars
    inputL.addEventListener('input', () => {
      inputL.value = inputL.value.replace(/[^A-Z0-9]/gi, '').toUpperCase().slice(0, 4);
      if (inputL.value.length === 4) inputR.focus();
    });
    inputR.addEventListener('input', () => {
      inputR.value = inputR.value.replace(/[^A-Z0-9]/gi, '').toUpperCase().slice(0, 4);
    });
    // Backspace on empty right input jumps back to left
    inputR.addEventListener('keydown', e => {
      if (e.key === 'Backspace' && inputR.value === '') {
        e.preventDefault();
        inputL.focus();
      }
      if (e.key === 'Enter') approvePairingFromModal();
    });
    inputL.addEventListener('keydown', e => {
      if (e.key === 'Enter') approvePairingFromModal();
    });
    // Handle paste of full code (e.g. "XXXX-XXXX") on either input
    function handlePaste(e) {
      e.preventDefault();
      const text = (e.clipboardData || window.clipboardData).getData('text');
      const clean = text.replace(/[^A-Z0-9]/gi, '').toUpperCase().slice(0, 8);
      inputL.value = clean.slice(0, 4);
      inputR.value = clean.slice(4, 8);
      if (inputR.value.length > 0) inputR.focus(); else inputL.focus();
    }
    inputL.addEventListener('paste', handlePaste);
    inputR.addEventListener('paste', handlePaste);

    row.appendChild(inputL);
    row.appendChild(sep);
    row.appendChild(inputR);
    field.appendChild(label);
    field.appendChild(row);
    body.appendChild(description);
    body.appendChild(field);

    const footer = document.createElement('footer');
    footer.className = 'confirm-modal__footer account-switcher-modal__footer';

    const approveButton = document.createElement('button');
    approveButton.type = 'button';
    approveButton.className = 'button account-switcher-modal__primary-action';
    approveButton.id = 'pairing-approve-button';
    approveButton.textContent = t('approveDeviceCode');

    footer.appendChild(approveButton);
    modal.appendChild(header);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    closeButton.addEventListener('click', closePairingApproveModal);
    overlay.addEventListener('click', event => {
      if (event.target === overlay) {
        closePairingApproveModal();
      }
    });
    approveButton.addEventListener('click', async () => {
      await approvePairingFromModal();
    });

    ui.pairingApproveModal = overlay;
    return overlay;
  }

  async function claimPairingLogin() {
    const api = getApiClient();
    if (!api || !pairingState.current || !pairingState.current.public_id) {
      return false;
    }

    const response = await api.claimPairing(pairingState.current.public_id);

    // Expired or already used — stop polling
    if (response.status === 410 || response.status === 409) {
      stopPairingClaimPolling();
      setStatusMessage(t('unableClaimDeviceCode'), 'error');
      return false;
    }

    // Network error or other failure — keep polling silently
    if (!response.ok) {
      return false;
    }

    // Claim succeeded — user authenticated
    if (response.data && response.data.authenticated) {
      stopPairingClaimPolling();
      closePairingLoginModal();
      setAuthenticated(response.data);
      setStatusMessage(t('deviceCodeSignInSuccess'), 'success');
      return true;
    }

    // Still pending — update modal state
    pairingState.current = response.data;
    renderPairingLoginModal();
    return false;
  }

  async function startPairingLogin() {
    const api = getApiClient();
    if (!api || !ui.pairingLoginModal) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    stopPairingClaimPolling();
    pairingState.current = null;
    renderPairingLoginModal();
    setStatusMessage(t('pairingCodeStarting'));

    const response = await api.startPairing();
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableStartDeviceCode'), 'error');
      return false;
    }

    pairingState.current = response.data;
    renderPairingLoginModal();
    pairingState.claimTimerId = window.setInterval(() => {
      claimPairingLogin();
    }, 3000);

    // Countdown display
    const expiresAt = response.data.expires_at;
    const expiresMs = expiresAt ? new Date(expiresAt).getTime() : Date.now() + 600000;
    const statusNode = ui.pairingLoginModal
      ? ui.pairingLoginModal.querySelector('#pairing-login-status')
      : null;
    const retryButton = ui.pairingLoginModal
      ? ui.pairingLoginModal.querySelector('#pairing-login-retry-button')
      : null;
    pairingState.countdownTimerId = window.setInterval(() => {
      const remaining = Math.max(0, Math.round((expiresMs - Date.now()) / 1000));
      if (statusNode) {
        if (remaining > 0) {
          const mins = Math.floor(remaining / 60);
          const secs = remaining % 60;
          statusNode.textContent = t('pairingCodeWaiting') + ' (' + mins + ':' + String(secs).padStart(2, '0') + ')';
        } else {
          statusNode.textContent = t('unableClaimDeviceCode');
        }
      }
      if (remaining === 0) {
        stopPairingClaimPolling();
        if (retryButton) retryButton.disabled = false;
      }
    }, 1000);

    setStatusMessage(t('pairingCodeWaiting'));
    return true;
  }

  async function openPairingLoginModal() {
    if (currentUser) {
      return;
    }

    const modal = buildPairingLoginModal();
    if (!modal.parentNode) {
      document.body.appendChild(modal);
    }
    modal.hidden = false;
    await startPairingLogin();
  }

  async function openPairingApproveModal() {
    if (!currentUser) {
      return;
    }

    const modal = buildPairingApproveModal();
    if (!modal.parentNode) {
      document.body.appendChild(modal);
    }
    const inputL = modal.querySelector('#pairing-approve-code-l');
    const inputR = modal.querySelector('#pairing-approve-code-r');
    if (inputL) inputL.value = '';
    if (inputR) inputR.value = '';
    modal.hidden = false;
    if (inputL) inputL.focus();
  }

  async function approvePairingFromModal() {
    const api = getApiClient();
    if (!api || !ui.pairingApproveModal) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    const inputL = ui.pairingApproveModal.querySelector('#pairing-approve-code-l');
    const inputR = ui.pairingApproveModal.querySelector('#pairing-approve-code-r');
    const left = inputL ? inputL.value.trim().toUpperCase() : '';
    const right = inputR ? inputR.value.trim().toUpperCase() : '';
    const code = left && right ? left + '-' + right : left + right;
    if (!code || code.replace(/-/g, '').length < 8) {
      setStatusMessage(t('pairingCodeRequired'), 'error');
      return false;
    }

    setStatusMessage(t('approvingDeviceCode'));
    const response = await api.approvePairing(code);
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableApproveDeviceCode'), 'error');
      return false;
    }

    closePairingApproveModal();
    setStatusMessage(t('deviceCodeApprovedSuccess'), 'success');
    return true;
  }

  function buildFallbackLoginModal() {
    if (ui.fallbackLoginModal) {
      return ui.fallbackLoginModal;
    }

    const overlay = document.createElement('section');
    overlay.className = 'confirm-modal-overlay';
    overlay.id = 'fallback-login-modal';
    overlay.hidden = true;

    const modal = document.createElement('div');
    modal.className = 'confirm-modal account-switcher-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'fallback-login-title');

    const header = document.createElement('header');
    header.className = 'confirm-modal__header';

    const title = document.createElement('h2');
    title.id = 'fallback-login-title';
    title.className = 'heading-2';
    title.textContent = t('fallbackLoginTitle');

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'confirm-modal__close';
    closeButton.setAttribute('aria-label', t('close'));
    closeButton.textContent = '✕';

    header.appendChild(title);
    header.appendChild(closeButton);

    const body = document.createElement('div');
    body.className = 'confirm-modal__body';

    const description = document.createElement('p');
    description.className = 'body';
    description.textContent = t('fallbackLoginDescription');

    const identifierField = document.createElement('label');
    identifierField.className = 'field';

    const identifierLabel = document.createElement('span');
    identifierLabel.className = 'field__label';
    identifierLabel.textContent = t('fallbackIdentifierLabel');

    const identifierInput = document.createElement('input');
    identifierInput.type = 'text';
    identifierInput.className = 'field__input';
    identifierInput.id = 'fallback-login-identifier';
    identifierInput.placeholder = t('fallbackIdentifierPlaceholder');
    identifierInput.autocomplete = 'username';

    identifierField.appendChild(identifierLabel);
    identifierField.appendChild(identifierInput);

    const codeField = document.createElement('label');
    codeField.className = 'field';

    const codeLabel = document.createElement('span');
    codeLabel.className = 'field__label';
    codeLabel.textContent = t('fallbackLoginCodeLabel');

    const codeInput = document.createElement('input');
    codeInput.type = 'text';
    codeInput.className = 'field__input';
    codeInput.id = 'fallback-login-code';
    codeInput.placeholder = t('fallbackLoginCodePlaceholder');
    codeInput.autocomplete = 'one-time-code';

    codeField.appendChild(codeLabel);
    codeField.appendChild(codeInput);

    body.appendChild(description);
    body.appendChild(identifierField);
    body.appendChild(codeField);

    const footer = document.createElement('footer');
    footer.className = 'confirm-modal__footer account-switcher-modal__footer';

    const totpButton = document.createElement('button');
    totpButton.type = 'button';
    totpButton.className = 'button account-switcher-modal__primary-action';
    totpButton.id = 'fallback-login-totp-button';
    totpButton.textContent = t('signInWithTotp');

    const recoveryButton = document.createElement('button');
    recoveryButton.type = 'button';
    recoveryButton.className = 'button button--ghost';
    recoveryButton.id = 'fallback-login-recovery-button';
    recoveryButton.textContent = t('signInWithRecoveryCode');

    footer.appendChild(totpButton);
    footer.appendChild(recoveryButton);

    modal.appendChild(header);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    closeButton.addEventListener('click', closeFallbackLoginModal);
    overlay.addEventListener('click', event => {
      if (event.target === overlay) {
        closeFallbackLoginModal();
      }
    });
    totpButton.addEventListener('click', async () => {
      await completeFallbackLogin('totp');
    });
    recoveryButton.addEventListener('click', async () => {
      await completeFallbackLogin('recovery_code');
    });

    ui.fallbackLoginModal = overlay;
    return overlay;
  }

  async function openFallbackLoginModal() {
    if (currentUser) {
      return;
    }

    const modal = buildFallbackLoginModal();
    if (!modal.parentNode) {
      document.body.appendChild(modal);
    }

    const identifierInput = modal.querySelector('#fallback-login-identifier');
    const codeInput = modal.querySelector('#fallback-login-code');
    if (identifierInput) {
      identifierInput.value = '';
    }
    if (codeInput) {
      codeInput.value = '';
    }

    modal.hidden = false;
    if (identifierInput) {
      identifierInput.focus();
    }
  }

  async function completeFallbackLogin(method) {
    const api = getApiClient();
    if (!api || !ui.fallbackLoginModal) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    const identifierInput = ui.fallbackLoginModal.querySelector('#fallback-login-identifier');
    const codeInput = ui.fallbackLoginModal.querySelector('#fallback-login-code');
    const identifier = identifierInput && identifierInput.value ? identifierInput.value.trim() : '';
    const code = codeInput && codeInput.value ? codeInput.value.trim() : '';

    if (!identifier) {
      setStatusMessage(t('fallbackIdentifierRequired'), 'error');
      return false;
    }
    if (!code) {
      setStatusMessage(t('fallbackLoginCodeRequired'), 'error');
      return false;
    }

    setStatusMessage(method === 'recovery_code' ? t('signingInWithRecoveryCode') : t('signingInWithTotp'));
    const response = await api.fallbackLogin(identifier, code, method);
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableFallbackLogin'), 'error');
      return false;
    }

    closeFallbackLoginModal();
    setAuthenticated(response.data);
    setStatusMessage(t('fallbackLoginSuccess'), 'success');
    return true;
  }

  async function loadPasskeys() {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return [];
    }

    const response = await api.getPasskeys();
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableLoadPasskeys'), 'error');
      return [];
    }

    return Array.isArray(response.data.passkeys) ? response.data.passkeys : [];
  }

  function buildPasskeyModal() {
    if (ui.passkeyModal) {
      return ui.passkeyModal;
    }

    const overlay = document.createElement('section');
    overlay.className = 'confirm-modal-overlay';
    overlay.id = 'passkey-modal';
    overlay.hidden = true;

    const modal = document.createElement('div');
    modal.className = 'confirm-modal account-switcher-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'passkey-modal-title');

    const header = document.createElement('header');
    header.className = 'confirm-modal__header';

    const title = document.createElement('h2');
    title.id = 'passkey-modal-title';
    title.className = 'heading-2';
    title.textContent = t('managePasskeys');

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'confirm-modal__close';
    closeButton.setAttribute('aria-label', t('close'));
    closeButton.textContent = '✕';

    header.appendChild(title);
    header.appendChild(closeButton);

    const body = document.createElement('div');
    body.className = 'confirm-modal__body';

    const description = document.createElement('p');
    description.className = 'body';
    description.textContent = t('passkeyModalDescription');

    const labelField = document.createElement('label');
    labelField.className = 'field';

    const labelText = document.createElement('span');
    labelText.className = 'field__label';
    labelText.textContent = t('passkeyLabelField');

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'field__input';
    input.id = 'passkey-label-input';
    input.placeholder = t('passkeyLabelPlaceholder');

    labelField.appendChild(labelText);
    labelField.appendChild(input);

    const list = document.createElement('div');
    list.className = 'field';
    list.id = 'passkey-list';

    body.appendChild(description);
    body.appendChild(labelField);
    body.appendChild(list);

    const footer = document.createElement('footer');
    footer.className = 'confirm-modal__footer account-switcher-modal__footer';

    const registerButton = document.createElement('button');
    registerButton.type = 'button';
    registerButton.className = 'button account-switcher-modal__primary-action';
    registerButton.id = 'passkey-register-button';
    registerButton.textContent = t('registerPasskey');

    footer.appendChild(registerButton);
    modal.appendChild(header);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    closeButton.addEventListener('click', closePasskeyModal);
    overlay.addEventListener('click', event => {
      if (event.target === overlay) {
        closePasskeyModal();
      }
    });
    registerButton.addEventListener('click', async () => {
      await registerPasskeyFromModal();
    });

    ui.passkeyModal = overlay;
    return overlay;
  }

  function closePasskeyModal() {
    if (!ui.passkeyModal) {
      return;
    }
    ui.passkeyModal.hidden = true;
  }

  async function loadMfaStatus() {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return null;
    }

    const response = await api.getMfaStatus();
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableLoadMfaStatus'), 'error');
      return null;
    }

    mfaState.status = response.data;
    return response.data;
  }

  async function loadAdminObservability() {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return null;
    }

    const response = await api.getAdminSqliteObservability();
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableLoadAdminObservability'), 'error');
      return null;
    }

    adminState.metrics = response.data;
    return response.data;
  }

  async function loadAdminRuntimeState() {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return null;
    }

    const response = await api.getAdminRuntimeState();
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableLoadAdminRuntimeState'), 'error');
      return null;
    }

    adminState.runtimeState = response.data;
    return response.data;
  }

  async function loadAdminPasswordPolicy() {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return null;
    }

    const response = await api.getAdminPasswordPolicy();
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableLoadAdminPasswordPolicy'), 'error');
      return null;
    }

    adminState.passwordPolicy = response.data;
    return response.data;
  }

  async function loadAdminUsers(query = '') {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return null;
    }
    if (typeof api.getAdminUsers !== 'function') {
      adminState.users = { users: [] };
      return adminState.users;
    }

    const response = await api.getAdminUsers(query);
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableLoadAdminUsers'), 'error');
      return null;
    }

    adminState.users = response.data;
    return response.data;
  }

  function buildAdminModal() {
    if (ui.adminModal) {
      return ui.adminModal;
    }

    const overlay = document.createElement('section');
    overlay.className = 'confirm-modal-overlay';
    overlay.id = 'admin-observability-modal';
    overlay.hidden = true;

    const modal = document.createElement('div');
    modal.className = 'confirm-modal account-switcher-modal admin-observability-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'admin-observability-title');

    const header = document.createElement('header');
    header.className = 'confirm-modal__header';

    const title = document.createElement('h2');
    title.id = 'admin-observability-title';
    title.className = 'heading-2';
    title.textContent = t('adminObservability');

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'confirm-modal__close';
    closeButton.setAttribute('aria-label', t('close'));
    closeButton.textContent = '✕';

    header.appendChild(title);
    header.appendChild(closeButton);

    const body = document.createElement('div');
    body.className = 'confirm-modal__body admin-observability-modal__body';

    const description = document.createElement('p');
    description.className = 'body';
    description.textContent = t('adminObservabilityDescription');

    const controls = document.createElement('div');
    controls.className = 'field__group admin-observability-modal__controls';

    const toggleButton = document.createElement('button');
    toggleButton.type = 'button';
    toggleButton.className = 'button';
    toggleButton.id = 'admin-observability-toggle';

    const refreshButton = document.createElement('button');
    refreshButton.type = 'button';
    refreshButton.className = 'button button--ghost';
    refreshButton.id = 'admin-observability-refresh';
    refreshButton.textContent = t('refreshAdminObservability');

    controls.appendChild(toggleButton);
    controls.appendChild(refreshButton);

    const metrics = document.createElement('dl');
    metrics.className = 'admin-observability-metrics';
    metrics.id = 'admin-observability-metrics';

    const recent = document.createElement('div');
    recent.className = 'field admin-observability-recent';
    recent.id = 'admin-observability-recent';

    const runtime = document.createElement('div');
    runtime.className = 'field admin-runtime-state';
    runtime.id = 'admin-runtime-state';

    const security = document.createElement('div');
    security.className = 'field admin-security-settings';
    security.id = 'admin-security-settings';

    const userManagement = document.createElement('div');
    userManagement.className = 'field admin-user-management';
    userManagement.id = 'admin-user-management';

    body.appendChild(description);
    body.appendChild(controls);
    body.appendChild(metrics);
    body.appendChild(recent);
    body.appendChild(runtime);
    body.appendChild(security);
    body.appendChild(userManagement);

    modal.appendChild(header);
    modal.appendChild(body);
    overlay.appendChild(modal);

    closeButton.addEventListener('click', closeAdminModal);
    overlay.addEventListener('click', event => {
      if (event.target === overlay) {
        closeAdminModal();
      }
    });
    refreshButton.addEventListener('click', async () => {
      await refreshAdminModal();
    });
    toggleButton.addEventListener('click', async () => {
      await toggleAdminObservability(toggleButton);
    });

    ui.adminModal = overlay;
    return overlay;
  }

  function renderAdminObservability() {
    if (!ui.adminModal || !adminState.metrics) {
      return;
    }

    const metricsNode = ui.adminModal.querySelector('#admin-observability-metrics');
    const recentNode = ui.adminModal.querySelector('#admin-observability-recent');
    const runtimeNode = ui.adminModal.querySelector('#admin-runtime-state');
    const securityNode = ui.adminModal.querySelector('#admin-security-settings');
    const userManagementNode = ui.adminModal.querySelector('#admin-user-management');
    const toggleButton = ui.adminModal.querySelector('#admin-observability-toggle');
    if (!metricsNode || !recentNode || !runtimeNode || !securityNode || !userManagementNode || !toggleButton) {
      return;
    }

    toggleButton.textContent = adminState.metrics.enabled
      ? t('disableAdminObservability')
      : t('enableAdminObservability');

    metricsNode.innerHTML = '';
    recentNode.innerHTML = '';

    const entries = [
      ['adminMetricsEnabled', adminState.metrics.enabled ? t('yes') : t('no')],
      ['adminMetricsThreshold', String(adminState.metrics.slow_write_threshold_ms ?? '--')],
      ['adminMetricsWriteCount', String(adminState.metrics.write_count ?? 0)],
      ['adminMetricsWriteAvg', String(adminState.metrics.write_time_ms_avg ?? 0)],
      ['adminMetricsWriteMax', String(adminState.metrics.write_time_ms_max ?? 0)],
      ['adminMetricsSlowWrites', String(adminState.metrics.slow_write_count ?? 0)],
      ['adminMetricsLockErrors', String(adminState.metrics.lock_error_count ?? 0)],
      ['adminMetricsActiveRefreshes', String((adminState.metrics.active_manual_refreshes || []).length)]
    ];

    entries.forEach(([labelKey, value]) => {
      const wrapper = document.createElement('div');
      wrapper.className = 'admin-observability-metrics__item';

      const term = document.createElement('dt');
      term.className = 'caption admin-observability-metrics__label';
      term.textContent = t(labelKey);

      const description = document.createElement('dd');
      description.className = 'body admin-observability-metrics__value';
      description.textContent = value;

      wrapper.appendChild(term);
      wrapper.appendChild(description);
      metricsNode.appendChild(wrapper);
    });

    const recentLabel = document.createElement('span');
    recentLabel.className = 'field__label';
    recentLabel.textContent = t('adminRecentWrites');
    recentNode.appendChild(recentLabel);

    const recentWrites = Array.isArray(adminState.metrics.recent_writes)
      ? adminState.metrics.recent_writes
      : [];
    if (!recentWrites.length) {
      const empty = document.createElement('p');
      empty.className = 'caption';
      empty.textContent = t('adminNoRecentWrites');
      recentNode.appendChild(empty);
    } else {
      const list = document.createElement('div');
      list.className = 'admin-observability-recent__list';
      recentWrites.slice(0, 8).forEach(entry => {
        const row = document.createElement('div');
        row.className = 'field__group';
        row.textContent = `${entry.statement || 'WRITE'} · ${entry.duration_ms || 0}ms`;
        list.appendChild(row);
      });
      recentNode.appendChild(list);
    }

    runtimeNode.innerHTML = '';
    const runtimeLabel = document.createElement('span');
    runtimeLabel.className = 'field__label';
    runtimeLabel.textContent = t('adminRuntimeState');
    runtimeNode.appendChild(runtimeLabel);

    const runtimeUsers = adminState.runtimeState && Array.isArray(adminState.runtimeState.users)
      ? adminState.runtimeState.users
      : [];
    if (!runtimeUsers.length) {
      const empty = document.createElement('p');
      empty.className = 'caption';
      empty.textContent = t('adminNoRuntimeUsers');
      runtimeNode.appendChild(empty);
    } else {
      const runtimeList = document.createElement('div');
      runtimeList.className = 'admin-runtime-state__list';
      runtimeUsers.forEach(user => {
        const userCard = document.createElement('article');
        userCard.className = 'admin-runtime-state__card';

        const heading = document.createElement('h3');
        heading.className = 'heading-3';
        heading.textContent = user.display_name || user.username || user.email || `#${user.id}`;

        const summary = document.createElement('p');
        summary.className = 'caption';
        summary.textContent = t('adminRuntimeUserSummary', {
          devices: user.device_count || 0,
          session: user.has_active_session ? t('yes') : t('no')
        });

        userCard.appendChild(heading);
        userCard.appendChild(summary);

        const devices = Array.isArray(user.devices) ? user.devices : [];
        if (devices.length) {
          const deviceList = document.createElement('div');
          deviceList.className = 'admin-runtime-state__devices';
          devices.forEach(device => {
            const item = document.createElement('div');
            item.className = 'field__group';
            const mode = device.frontend_mode || '--';
            item.textContent = `${device.device_type} · ${mode} · ${device.device_identifier}`;
            deviceList.appendChild(item);
          });
          userCard.appendChild(deviceList);
        }

        runtimeList.appendChild(userCard);
      });
      runtimeNode.appendChild(runtimeList);
    }

    securityNode.innerHTML = '';
    const securityLabel = document.createElement('span');
    securityLabel.className = 'field__label';
    securityLabel.textContent = t('adminSecuritySettings');
    securityNode.appendChild(securityLabel);

    const securityDescription = document.createElement('p');
    securityDescription.className = 'caption';
    securityDescription.textContent = t('adminPasswordPolicyDescription');
    securityNode.appendChild(securityDescription);

    const policySelect = document.createElement('select');
    policySelect.className = 'field__input';
    policySelect.id = 'admin-password-policy-select';

    const options = adminState.passwordPolicy && Array.isArray(adminState.passwordPolicy.options)
      ? adminState.passwordPolicy.options
      : [];
    options.forEach(option => {
      const node = document.createElement('option');
      node.value = option.value;
      node.textContent = option.label || option.value;
      node.selected = option.value === adminState.passwordPolicy.password_policy;
      policySelect.appendChild(node);
    });

    const policySaveButton = document.createElement('button');
    policySaveButton.type = 'button';
    policySaveButton.className = 'button button--ghost';
    policySaveButton.id = 'admin-password-policy-save';
    policySaveButton.textContent = t('saveSecuritySettings');
    policySaveButton.addEventListener('click', async () => {
      await updateAdminPasswordPolicy(policySelect.value, policySaveButton);
    });

    const securityControls = document.createElement('div');
    securityControls.className = 'field__group';
    securityControls.appendChild(policySelect);
    securityControls.appendChild(policySaveButton);
    securityNode.appendChild(securityControls);

    userManagementNode.innerHTML = '';
    const userLabel = document.createElement('span');
    userLabel.className = 'field__label';
    userLabel.textContent = t('adminUserManagement');
    userManagementNode.appendChild(userLabel);

    const userDescription = document.createElement('p');
    userDescription.className = 'caption';
    userDescription.textContent = t('adminUserManagementDescription');
    userManagementNode.appendChild(userDescription);

    const searchWrap = document.createElement('div');
    searchWrap.className = 'field__group';

    const searchInput = document.createElement('input');
    searchInput.className = 'field__input';
    searchInput.id = 'admin-user-search';
    searchInput.placeholder = t('adminUserSearchPlaceholder');

    const searchButton = document.createElement('button');
    searchButton.type = 'button';
    searchButton.className = 'button button--ghost';
    searchButton.textContent = t('search');
    searchButton.addEventListener('click', async () => {
      await refreshAdminUsers(searchInput.value || '');
    });

    searchWrap.appendChild(searchInput);
    searchWrap.appendChild(searchButton);
    userManagementNode.appendChild(searchWrap);

    const adminUsers = adminState.users && Array.isArray(adminState.users.users)
      ? adminState.users.users
      : [];
    if (!adminUsers.length) {
      const empty = document.createElement('p');
      empty.className = 'caption';
      empty.textContent = t('adminNoUsers');
      userManagementNode.appendChild(empty);
      return;
    }

    const list = document.createElement('div');
    list.className = 'admin-runtime-state__list';

    adminUsers.forEach(user => {
      const card = document.createElement('article');
      card.className = 'admin-runtime-state__card';

      const heading = document.createElement('h3');
      heading.className = 'heading-3';
      heading.textContent = user.display_name || user.username || user.email || `#${user.id}`;

      const summary = document.createElement('p');
      summary.className = 'caption';
      summary.textContent = t('adminUserSummary', {
        username: user.username || '—',
        status: user.is_active ? t('yes') : t('no'),
        admin: user.is_admin ? t('yes') : t('no')
      });

      const meta = document.createElement('p');
      meta.className = 'caption';
      meta.textContent = [
        user.email || '—',
        user.auth_provider || '—',
        user.has_password ? t('adminHasPassword') : t('adminNoPassword'),
        user.must_change_password ? t('adminMustChangePassword') : ''
      ].filter(Boolean).join(' · ');

      const actionRow = document.createElement('div');
      actionRow.className = 'field__group';

      const toggleUserButton = document.createElement('button');
      toggleUserButton.type = 'button';
      toggleUserButton.className = 'button button--ghost';
      toggleUserButton.textContent = user.is_active ? t('adminDisableUser') : t('adminEnableUser');
      toggleUserButton.addEventListener('click', async () => {
        await toggleAdminUser(user, toggleUserButton);
      });

      const tempPasswordInput = document.createElement('input');
      tempPasswordInput.className = 'field__input';
      tempPasswordInput.type = 'text';
      tempPasswordInput.placeholder = t('adminTemporaryPasswordPlaceholder');

      const resetButton = document.createElement('button');
      resetButton.type = 'button';
      resetButton.className = 'button';
      resetButton.textContent = t('adminResetPassword');
      resetButton.addEventListener('click', async () => {
        await resetAdminManagedPassword(user, tempPasswordInput.value || '', resetButton);
      });

      actionRow.appendChild(toggleUserButton);
      actionRow.appendChild(tempPasswordInput);
      actionRow.appendChild(resetButton);

      card.appendChild(heading);
      card.appendChild(summary);
      card.appendChild(meta);
      card.appendChild(actionRow);
      list.appendChild(card);
    });

    userManagementNode.appendChild(list);
  }

  async function refreshAdminUsers(query = '') {
    const users = await loadAdminUsers(query);
    if (!users) {
      return false;
    }
    renderAdminObservability();
    return true;
  }

  async function toggleAdminUser(user, button = null) {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    if (button) {
      button.disabled = true;
    }

    const response = user.is_active
      ? await api.disableAdminUser(user.id)
      : await api.enableAdminUser(user.id);

    if (button) {
      button.disabled = false;
    }

    if (!response.ok || !response.data) {
      setStatusMessage(response.error || t('unableUpdateAdminUser'), 'error');
      return false;
    }

    await refreshAdminUsers();
    setStatusMessage(t('adminUserUpdated'), 'success');
    return true;
  }

  async function resetAdminManagedPassword(user, temporaryPassword, button = null) {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }
    if (!temporaryPassword.trim()) {
      setStatusMessage(t('adminTemporaryPasswordRequired'), 'error');
      return false;
    }

    if (button) {
      button.disabled = true;
    }

    const response = await api.resetAdminUserPassword(user.id, temporaryPassword.trim());

    if (button) {
      button.disabled = false;
    }

    if (!response.ok || !response.data) {
      setStatusMessage(response.error || t('unableResetAdminPassword'), 'error');
      return false;
    }

    await refreshAdminUsers();
    setStatusMessage(t('adminPasswordResetSuccess'), 'success');
    return true;
  }

  async function refreshAdminModal() {
    const [metrics, runtimeState, passwordPolicy, users] = await Promise.all([
      loadAdminObservability(),
      loadAdminRuntimeState(),
      loadAdminPasswordPolicy(),
      loadAdminUsers()
    ]);
    if (!metrics || !runtimeState || !passwordPolicy || !users) {
      return false;
    }
    renderAdminObservability();
    setStatusMessage(t('adminObservabilityRefreshed'), 'success');
    return true;
  }

  async function toggleAdminObservability(button = null) {
    const api = getApiClient();
    if (!api || !adminState.metrics) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    if (button) {
      button.disabled = true;
    }

    const response = await api.updateAdminSqliteObservability(!adminState.metrics.enabled);

    if (button) {
      button.disabled = false;
    }

    if (!response.ok || !response.data) {
      setStatusMessage(t('unableToggleAdminObservability'), 'error');
      return false;
    }

    adminState.metrics = response.data;
    renderAdminObservability();
    setStatusMessage(t('adminObservabilityUpdated'), 'success');
    return true;
  }

  async function updateAdminPasswordPolicy(passwordPolicy, button = null) {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    if (button) {
      button.disabled = true;
    }

    const response = await api.updateAdminPasswordPolicy(passwordPolicy);

    if (button) {
      button.disabled = false;
    }

    if (!response.ok || !response.data) {
      setStatusMessage(response.error || t('unableSaveAdminPasswordPolicy'), 'error');
      return false;
    }

    adminState.passwordPolicy = response.data;
    renderAdminObservability();
    setStatusMessage(t('adminPasswordPolicyUpdated'), 'success');
    return true;
  }

  async function openAdminModal() {
    if (!isAdminUser()) {
      return;
    }

    const modal = buildAdminModal();
    if (!modal.parentNode) {
      document.body.appendChild(modal);
    }

    const [metrics, runtimeState, passwordPolicy, users] = await Promise.all([
      loadAdminObservability(),
      loadAdminRuntimeState(),
      loadAdminPasswordPolicy(),
      loadAdminUsers()
    ]);
    if (!metrics || !runtimeState || !passwordPolicy || !users) {
      return;
    }

    renderAdminObservability();
    modal.hidden = false;
  }

  function buildMfaModal() {
    if (ui.mfaModal) {
      return ui.mfaModal;
    }

    const overlay = document.createElement('section');
    overlay.className = 'confirm-modal-overlay';
    overlay.id = 'mfa-modal';
    overlay.hidden = true;

    const modal = document.createElement('div');
    modal.className = 'confirm-modal account-switcher-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'mfa-modal-title');

    const header = document.createElement('header');
    header.className = 'confirm-modal__header';

    const title = document.createElement('h2');
    title.id = 'mfa-modal-title';
    title.className = 'heading-2';
    title.textContent = t('manageMfa');

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'confirm-modal__close';
    closeButton.setAttribute('aria-label', t('close'));
    closeButton.textContent = '✕';

    header.appendChild(title);
    header.appendChild(closeButton);

    const body = document.createElement('div');
    body.className = 'confirm-modal__body';

    const description = document.createElement('p');
    description.className = 'body';
    description.textContent = t('mfaModalDescription');

    const status = document.createElement('div');
    status.className = 'field';
    status.id = 'mfa-status-panel';

    const setup = document.createElement('div');
    setup.className = 'field';
    setup.id = 'mfa-setup-panel';

    const recovery = document.createElement('div');
    recovery.className = 'field';
    recovery.id = 'mfa-recovery-panel';

    body.appendChild(description);
    body.appendChild(status);
    body.appendChild(setup);
    body.appendChild(recovery);

    modal.appendChild(header);
    modal.appendChild(body);
    overlay.appendChild(modal);

    closeButton.addEventListener('click', closeMfaModal);
    overlay.addEventListener('click', event => {
      if (event.target === overlay) {
        closeMfaModal();
      }
    });

    ui.mfaModal = overlay;
    return overlay;
  }

  function closeMfaModal() {
    if (!ui.mfaModal) {
      return;
    }
    ui.mfaModal.hidden = true;
  }

  function renderRecoveryCodes(container) {
    if (!mfaState.recoveryCodes.length) {
      return;
    }

    const label = document.createElement('span');
    label.className = 'field__label';
    label.textContent = t('recoveryCodesHeading');
    container.appendChild(label);

    const list = document.createElement('div');
    list.className = 'field';
    list.id = 'mfa-recovery-codes';
    mfaState.recoveryCodes.forEach(code => {
      const item = document.createElement('div');
      item.className = 'field__group';
      item.textContent = code;
      list.appendChild(item);
    });
    container.appendChild(list);
  }

  function renderMfaModal() {
    if (!ui.mfaModal || !mfaState.status) {
      return;
    }

    const statusPanel = ui.mfaModal.querySelector('#mfa-status-panel');
    const setupPanel = ui.mfaModal.querySelector('#mfa-setup-panel');
    const recoveryPanel = ui.mfaModal.querySelector('#mfa-recovery-panel');
    if (!statusPanel || !setupPanel || !recoveryPanel) {
      return;
    }

    statusPanel.innerHTML = '';
    setupPanel.innerHTML = '';
    recoveryPanel.innerHTML = '';

    const statusLabel = document.createElement('span');
    statusLabel.className = 'field__label';
    statusLabel.textContent = t('mfaStatusHeading');
    statusPanel.appendChild(statusLabel);

    const enabled = document.createElement('p');
    enabled.className = 'body';
    enabled.textContent = mfaState.status.totp_enabled ? t('mfaEnabledYes') : t('mfaEnabledNo');
    statusPanel.appendChild(enabled);

    const pending = document.createElement('p');
    pending.className = 'caption';
    pending.textContent = mfaState.status.totp_pending ? t('mfaPendingYes') : t('mfaPendingNo');
    statusPanel.appendChild(pending);

    const remaining = document.createElement('p');
    remaining.className = 'caption';
    remaining.textContent = t('recoveryCodesRemaining', { count: mfaState.status.recovery_codes_remaining || 0 });
    statusPanel.appendChild(remaining);

    if (!mfaState.status.totp_enabled) {
      const startButton = document.createElement('button');
      startButton.type = 'button';
      startButton.className = 'button';
      startButton.id = 'mfa-start-setup-button';
      startButton.textContent = t('startTotpSetup');
      startButton.addEventListener('click', async () => {
        await startTotpSetup();
      });
      setupPanel.appendChild(startButton);

      if (mfaState.setupSecret) {
        const secretLabel = document.createElement('span');
        secretLabel.className = 'field__label';
        secretLabel.textContent = t('totpSecretLabel');
        setupPanel.appendChild(secretLabel);

        const secretValue = document.createElement('div');
        secretValue.className = 'field__group';
        secretValue.id = 'mfa-setup-secret';
        secretValue.textContent = mfaState.setupSecret;
        setupPanel.appendChild(secretValue);

        if (mfaState.otpauthUrl) {
          const hint = document.createElement('p');
          hint.className = 'caption';
          hint.textContent = t('totpAppHint');
          setupPanel.appendChild(hint);
        }

        const codeLabel = document.createElement('label');
        codeLabel.className = 'field';

        const codeText = document.createElement('span');
        codeText.className = 'field__label';
        codeText.textContent = t('totpCodeLabel');

        const codeInput = document.createElement('input');
        codeInput.type = 'text';
        codeInput.inputMode = 'numeric';
        codeInput.autocomplete = 'one-time-code';
        codeInput.className = 'field__input';
        codeInput.id = 'mfa-confirm-code';
        codeInput.placeholder = t('totpCodePlaceholder');

        codeLabel.appendChild(codeText);
        codeLabel.appendChild(codeInput);
        setupPanel.appendChild(codeLabel);

        const confirmButton = document.createElement('button');
        confirmButton.type = 'button';
        confirmButton.className = 'button account-switcher-modal__primary-action';
        confirmButton.id = 'mfa-confirm-button';
        confirmButton.textContent = t('confirmTotpSetup');
        confirmButton.addEventListener('click', async () => {
          await confirmTotpSetup();
        });
        setupPanel.appendChild(confirmButton);
      }
    } else {
      const regenLabel = document.createElement('label');
      regenLabel.className = 'field';

      const regenText = document.createElement('span');
      regenText.className = 'field__label';
      regenText.textContent = t('totpCodeLabel');

      const regenInput = document.createElement('input');
      regenInput.type = 'text';
      regenInput.inputMode = 'numeric';
      regenInput.autocomplete = 'one-time-code';
      regenInput.className = 'field__input';
      regenInput.id = 'mfa-regenerate-code';
      regenInput.placeholder = t('totpCodePlaceholder');

      regenLabel.appendChild(regenText);
      regenLabel.appendChild(regenInput);
      recoveryPanel.appendChild(regenLabel);

      const regenerateButton = document.createElement('button');
      regenerateButton.type = 'button';
      regenerateButton.className = 'button account-switcher-modal__primary-action';
      regenerateButton.id = 'mfa-regenerate-button';
      regenerateButton.textContent = t('regenerateRecoveryCodes');
      regenerateButton.addEventListener('click', async () => {
        await regenerateRecoveryCodesFromModal();
      });
      recoveryPanel.appendChild(regenerateButton);
    }

    renderRecoveryCodes(recoveryPanel);
  }

  async function openMfaModal() {
    if (!currentUser) {
      return;
    }

    const modal = buildMfaModal();
    if (!modal.parentNode) {
      document.body.appendChild(modal);
    }

    mfaState.setupSecret = null;
    mfaState.otpauthUrl = null;
    mfaState.recoveryCodes = [];
    const status = await loadMfaStatus();
    if (!status) {
      return;
    }
    renderMfaModal();
    modal.hidden = false;
  }

  async function startTotpSetup() {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    setStatusMessage(t('startingTotpSetup'));
    const response = await api.setupTotp();
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableStartTotpSetup'), 'error');
      return false;
    }

    mfaState.setupSecret = response.data.secret || null;
    mfaState.otpauthUrl = response.data.otpauth_url || null;
    if (!mfaState.status) {
      mfaState.status = {};
    }
    mfaState.status.totp_pending = true;
    renderMfaModal();
    setStatusMessage(t('totpSetupStarted'), 'success');
    return true;
  }

  async function confirmTotpSetup() {
    const api = getApiClient();
    if (!api || !ui.mfaModal) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    const input = ui.mfaModal.querySelector('#mfa-confirm-code');
    const code = input && input.value ? input.value.trim() : '';
    if (!code) {
      setStatusMessage(t('totpCodeRequired'), 'error');
      return false;
    }

    setStatusMessage(t('confirmingTotpSetup'));
    const response = await api.confirmTotp(code);
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableConfirmTotpSetup'), 'error');
      return false;
    }

    mfaState.setupSecret = null;
    mfaState.otpauthUrl = null;
    mfaState.recoveryCodes = Array.isArray(response.data.recovery_codes) ? response.data.recovery_codes : [];
    await loadMfaStatus();
    renderMfaModal();
    setStatusMessage(t('totpEnabledSuccess'), 'success');
    return true;
  }

  async function regenerateRecoveryCodesFromModal() {
    const api = getApiClient();
    if (!api || !ui.mfaModal) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    const input = ui.mfaModal.querySelector('#mfa-regenerate-code');
    const code = input && input.value ? input.value.trim() : '';
    if (!code) {
      setStatusMessage(t('totpCodeRequired'), 'error');
      return false;
    }

    setStatusMessage(t('regeneratingRecoveryCodes'));
    const response = await api.regenerateRecoveryCodes(code);
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableRegenerateRecoveryCodes'), 'error');
      return false;
    }

    mfaState.recoveryCodes = Array.isArray(response.data.recovery_codes) ? response.data.recovery_codes : [];
    await loadMfaStatus();
    renderMfaModal();
    setStatusMessage(t('recoveryCodesRegenerated'), 'success');
    return true;
  }

  function renderPasskeyList(passkeys) {
    if (!ui.passkeyModal) {
      return;
    }

    const list = ui.passkeyModal.querySelector('#passkey-list');
    if (!list) {
      return;
    }

    list.innerHTML = '';
    if (!passkeys.length) {
      const empty = document.createElement('p');
      empty.className = 'caption';
      empty.textContent = t('noPasskeysYet');
      list.appendChild(empty);
      return;
    }

    passkeys.forEach(passkey => {
      const row = document.createElement('div');
      row.className = 'field__group';

      const label = document.createElement('span');
      label.className = 'body';
      label.textContent = passkey.label || t('unnamedPasskey');

      const removeButton = document.createElement('button');
      removeButton.type = 'button';
      removeButton.className = 'button button--ghost';
      removeButton.textContent = t('deletePasskey');
      removeButton.addEventListener('click', async () => {
        await deletePasskey(passkey.id, removeButton);
      });

      row.appendChild(label);
      row.appendChild(removeButton);
      list.appendChild(row);
    });
  }

  async function openPasskeyModal() {
    if (!passkeysSupported() || !currentUser) {
      return;
    }

    const modal = buildPasskeyModal();
    if (!modal.parentNode) {
      document.body.appendChild(modal);
    }

    const passkeys = await loadPasskeys();
    renderPasskeyList(passkeys);
    modal.hidden = false;
  }

  async function refreshPasskeyModalList() {
    if (!ui.passkeyModal || ui.passkeyModal.hidden) {
      return;
    }
    const passkeys = await loadPasskeys();
    renderPasskeyList(passkeys);
  }

  async function registerPasskeyFromModal() {
    if (!window.ytcvPasskeys || !passkeysSupported()) {
      setStatusMessage(t('passkeyNotSupported'), 'error');
      return false;
    }

    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    const input = ui.passkeyModal ? ui.passkeyModal.querySelector('#passkey-label-input') : null;
    const label = input && input.value ? input.value.trim() : '';
    setStatusMessage(t('registeringPasskey'));

    try {
      await window.ytcvPasskeys.registerPasskey(api, label);
      if (input) {
        input.value = '';
      }
      await refreshPasskeyModalList();
      setStatusMessage(t('passkeyRegistered'), 'success');
      return true;
    } catch (error) {
      setStatusMessage(error && error.message ? error.message : t('unableRegisterPasskey'), 'error');
      return false;
    }
  }

  async function deletePasskey(passkeyId, button = null) {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    if (button) {
      button.disabled = true;
    }

    const response = await api.deletePasskey(passkeyId);

    if (button) {
      button.disabled = false;
    }

    if (!response.ok) {
      setStatusMessage(t('unableDeletePasskey'), 'error');
      return false;
    }

    await refreshPasskeyModalList();
    setStatusMessage(t('passkeyDeleted'), 'success');
    return true;
  }

  async function signInWithPasskey() {
    if (!window.ytcvPasskeys || !passkeysSupported()) {
      setStatusMessage(t('passkeyNotSupported'), 'error');
      return false;
    }

    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    setStatusMessage(t('signingInWithPasskey'));

    try {
      const response = await window.ytcvPasskeys.authenticateWithPasskey(api);
      if (!response.ok || !response.data) {
        setStatusMessage(t('unableSignInWithPasskey'), 'error');
        return false;
      }
      setAuthenticated(response.data);
      setStatusMessage(t('passkeySignInSuccess'), 'success');
      return true;
    } catch (error) {
      setStatusMessage(error && error.message ? error.message : t('unableSignInWithPasskey'), 'error');
      return false;
    }
  }

  function renderAccountSwitcherList(accounts) {
    if (!ui.accountModal) {
      return;
    }

    const list = ui.accountModal.querySelector('#account-switcher-list');
    if (!list) {
      return;
    }

    list.innerHTML = '';

    if (!accounts.length) {
      const empty = document.createElement('p');
      empty.className = 'caption';
      empty.textContent = t('noGoogleAccountsYet');
      list.appendChild(empty);
      return;
    }

    accounts.forEach(account => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'menu-item';
      button.dataset.userId = String(account.id);
      button.disabled = Boolean(account.is_current);
      const label = account.display_name || account.username || account.email || `#${account.id}`;
      const detail = account.email && account.email !== label ? ` (${account.email})` : '';
      button.textContent = account.is_current
        ? `${label}${detail} · ${t('currentAccountLabel')}`
        : `${label}${detail}`;

      button.addEventListener('click', async () => {
        await switchGoogleAccount(account.id, button);
      });

      list.appendChild(button);
    });
  }

  async function openAccountSwitcherModal() {
    if (!isGoogleMode()) {
      return;
    }

    const modal = buildAccountSwitcherModal();
    if (!modal.parentNode) {
      document.body.appendChild(modal);
    }

    const accounts = await loadSwitchableAccounts();
    renderAccountSwitcherList(accounts);
    modal.hidden = false;
  }

  async function switchGoogleAccount(userId, button = null) {
    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    if (button) {
      button.disabled = true;
    }

    const response = await api.switchAccount(userId);

    if (button) {
      button.disabled = false;
    }

    if (!response.ok || !response.data) {
      setStatusMessage(t('unableSwitchAccount'), 'error');
      return false;
    }

    closeAccountSwitcherModal();
    if (response.data.mfa_required) {
      setPendingMfaChallenge(response.data);
      return true;
    }
    setAuthenticated(response.data);
    return true;
  }

  function validateUsername(raw) {
    const cleaned = (raw || '').trim();
    if (!cleaned) {
      return { ok: false, message: t('usernameRequired') };
    }

    if (!/^[a-z0-9]+$/i.test(cleaned)) {
      return { ok: false, message: t('usernameInvalid') };
    }

    return { ok: true, value: cleaned };
  }

  function buildCreateUserModal() {
    if (ui.modal) {
      return ui.modal;
    }

    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'new-user-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');

    const content = document.createElement('div');
    content.className = 'modal__content';

    const title = document.createElement('h2');
    title.className = 'heading-2';
    title.textContent = t('createUserTitle');

    const description = document.createElement('p');
    description.className = 'body';
    description.textContent = t('createUserDescription');

    const form = document.createElement('form');
    form.className = 'field';

    const label = document.createElement('label');
    label.className = 'field';

    const labelText = document.createElement('span');
    labelText.className = 'field__label';
    labelText.textContent = t('usernameLabel');

    const input = document.createElement('input');
    input.className = 'field__input';
    input.type = 'text';
    input.name = 'username';
    input.autocomplete = 'username';
    input.autocapitalize = 'none';
    input.spellcheck = false;

    const errorText = document.createElement('span');
    errorText.className = 'caption';
    errorText.style.color = 'var(--error)';
    errorText.id = 'new-user-error';

    label.appendChild(labelText);
    label.appendChild(input);
    label.appendChild(errorText);

    const actions = document.createElement('div');
    actions.className = 'field__group';

    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.className = 'button button--ghost';
    cancelButton.textContent = t('cancel');

    const submitButton = document.createElement('button');
    submitButton.type = 'submit';
    submitButton.className = 'button';
    submitButton.textContent = t('createAndSignIn');

    actions.appendChild(cancelButton);
    actions.appendChild(submitButton);

    form.appendChild(label);
    form.appendChild(actions);

    content.appendChild(title);
    content.appendChild(description);
    content.appendChild(form);

    modal.appendChild(content);

    modal.addEventListener('click', event => {
      if (event.target === modal) {
        closeCreateUserModal();
      }
    });

    cancelButton.addEventListener('click', () => {
      closeCreateUserModal();
    });

    form.addEventListener('submit', async event => {
      event.preventDefault();
      errorText.textContent = '';

      const validation = validateUsername(input.value);
      if (!validation.ok) {
        errorText.textContent = validation.message;
        input.focus();
        return;
      }

      submitButton.disabled = true;
      cancelButton.disabled = true;
      const result = await loginUser(validation.value);
      submitButton.disabled = false;
      cancelButton.disabled = false;

      if (result) {
        closeCreateUserModal();
      } else {
        errorText.textContent = t('unableCreateUser');
      }
    });

    ui.modal = modal;
    return modal;
  }

  function openCreateUserModal() {
    const modal = buildCreateUserModal();
    document.body.appendChild(modal);
    const input = modal.querySelector('input[name="username"]');
    if (input) {
      input.value = '';
      input.focus();
    }
  }

  function closeCreateUserModal() {
    if (!ui.modal) {
      return;
    }

    if (ui.modal.parentNode) {
      ui.modal.parentNode.removeChild(ui.modal);
    }
  }

  async function loginUser(username) {
    if (isGoogleMode()) {
      startGoogleLogin();
      return false;
    }

    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    setStatusMessage(t('signingIn'));
    const response = await api.login(username);
    if (!response.ok) {
      setStatusMessage(t('signInFailed'), 'error');
      return false;
    }

    if (response.data && response.data.mfa_required) {
      setPendingMfaChallenge(response.data);
      return true;
    }

    const user = response.data || { username };
    setAuthenticated(user);
    await loadUsers();
    return true;
  }

  async function completeMfaChallenge(method) {
    const api = getApiClient();
    if (!api || !pendingMfaChallenge || !ui.mfaChallengeModal) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      return false;
    }

    const input = ui.mfaChallengeModal.querySelector('#mfa-challenge-code');
    const code = input && input.value ? input.value.trim() : '';
    if (!code) {
      setStatusMessage(t('totpCodeRequired'), 'error');
      return false;
    }

    setStatusMessage(method === 'recovery_code' ? t('verifyingRecoveryCode') : t('verifyingTotpCode'));
    const response = await api.verifyMfaChallenge(code, method);
    if (!response.ok || !response.data) {
      setStatusMessage(t('unableVerifyMfaChallenge'), 'error');
      return false;
    }

    setAuthenticated(response.data);
    setStatusMessage(t('mfaChallengeCompleted'), 'success');
    return true;
  }

  async function initAuth() {
    await (window.ytcvI18nReady || Promise.resolve());
    await loadAuthProvider();
    handleAuthErrorParam();

    ensureButtons();
    ensureUserSelectorListener();
    ensureGoogleLoginListener();
    applyAuthMode();

    if (!listenersReady) {
      window.addEventListener('auth-required', () => {
        handleAuthRequired();
      });
      listenersReady = true;
    }

    const api = getApiClient();
    if (!api) {
      setStatusMessage(t('apiClientNotReady'), 'error');
      setUnauthenticated();
      return null;
    }

    const response = await api.getCurrentUser();
    if (response.ok && response.data && response.data.authenticated) {
      if (isGoogleMode()) {
        await loadSwitchableAccounts();
      }
      setAuthenticated(response.data);
      return response.data;
    }

    if (response.ok && response.data && response.data.mfa_required) {
      setPendingMfaChallenge(response.data);
      return null;
    }

    if (response.ok && response.data && response.data.password_change_required) {
      window.dispatchEvent(new CustomEvent('login-page:password-change-required', { detail: response.data }));
      return null;
    }

    if (!response.ok) {
    setStatusMessage(t('unableVerifySession'), 'error');
    }

    setUnauthenticated();
    if (isGoogleMode()) {
      await loadSwitchableAccounts();
    } else {
      await loadUsers();
    }
    return null;
  }

  function getCurrentUser() {
    return currentUser;
  }

  function isAuthenticated() {
    return Boolean(currentUser);
  }

  async function performLogout(reloadPage) {
    const api = getApiClient();
    if (api) {
      await api.logout();
    }

    pendingMfaChallenge = null;
    closeMfaChallengeModal();
    setUnauthenticated();
    if (isGoogleMode()) {
      await loadSwitchableAccounts();
    } else {
      await loadUsers();
    }

    if (reloadPage) {
      window.location.reload();
    }
  }

  async function logout() {
    await performLogout(true);
  }

  async function switchUser() {
    if (isGoogleMode()) {
      await openAccountSwitcherModal();
      return;
    }
    await performLogout(false);
  }

  function handleAuthRequired() {
    setUnauthenticated();
    if (!isGoogleMode()) {
      loadUsers();
      return;
    }
    loadSwitchableAccounts();
  }

  function setAuthStatus(message, type = 'info') {
    setStatusMessage(message, type);
  }

  window.initAuth = initAuth;
  window.getCurrentUser = getCurrentUser;
  window.isAuthenticated = isAuthenticated;
  window.logout = logout;
  window.switchUser = switchUser;
  window.setAuthStatus = setAuthStatus;
  window.signInWithPasskey = signInWithPasskey;
  window.notifyAuthenticated = setAuthenticated;
})();
