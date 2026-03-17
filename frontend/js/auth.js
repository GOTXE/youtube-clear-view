// Authentication management with httpOnly cookie sessions.

(() => {
  let currentUser = null;
  let cachedUsers = [];
  let listenersReady = false;
  let authMode = 'local';
  let googleLoginUrl = null;

  const userSelector = document.getElementById('user-selector');
  const googleLoginButton = document.getElementById('google-login-button');

  const ui = {
    userSelector,
    userSelectorWrapper: userSelector ? userSelector.closest('label') : null,
    currentUserLabel: document.getElementById('current-user'),
    currentUserName: document.getElementById('current-user-name'),
    sessionInfo: document.querySelector('.session-info'),
    appRoot: document.getElementById('app'),
    headerActions: document.querySelector('.header-actions'),
    logoutButton: document.getElementById('logout-button'),
    googleLoginButton,
    userSummary: document.querySelector('.user-summary'),
    newUserButton: null,
    switchUserButton: null,
    accountSwitchButton: null,
    passkeyLoginButton: null,
    managePasskeysButton: null,
    statusMessage: null,
    modal: null,
    accountModal: null,
    passkeyModal: null
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
    const theme = themePreference === 'light' ? 'light' : 'dark';
    if (ui.appRoot) {
      ui.appRoot.setAttribute('data-theme', theme);
    }
    document.documentElement.setAttribute('data-theme', theme);
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

  function applyAuthMode() {
    const selectorContainer = ui.userSelectorWrapper || ui.userSelector;
    const googleMode = isGoogleMode();

    if (selectorContainer) {
      selectorContainer.hidden = googleMode;
    }

    if (ui.newUserButton) {
      ui.newUserButton.hidden = googleMode || Boolean(currentUser);
    }

    if (ui.googleLoginButton) {
      ui.googleLoginButton.hidden = !googleMode || Boolean(currentUser);
    }

    if (ui.accountSwitchButton) {
      ui.accountSwitchButton.hidden = !googleMode;
    }

    if (ui.passkeyLoginButton) {
      ui.passkeyLoginButton.hidden = Boolean(currentUser) || !passkeysSupported();
    }

    if (ui.managePasskeysButton) {
      ui.managePasskeysButton.hidden = !currentUser || !passkeysSupported();
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
    if (!ui.headerActions) {
      return;
    }

    if (!ui.newUserButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'new-user-button';
      button.className = 'menu-item';
      button.textContent = t('newUser');
      button.addEventListener('click', () => {
        openCreateUserModal();
      });
      ui.newUserButton = button;
      ui.headerActions.insertBefore(button, ui.userSummary || null);
    }

    if (!ui.switchUserButton) {
      const button = ui.logoutButton || document.createElement('button');
      button.type = 'button';
      if (!ui.logoutButton) {
        button.id = 'logout-button';
        button.className = 'menu-item';
        ui.headerActions.insertBefore(button, ui.userSummary || null);
      }
      button.textContent = t('signOut');
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
      button.textContent = t('switchAccount');
      button.hidden = !isGoogleMode();
      button.addEventListener('click', async () => {
        await openAccountSwitcherModal();
      });
      ui.accountSwitchButton = button;
      ui.headerActions.insertBefore(button, ui.switchUserButton || ui.userSummary || null);
    }

    if (!ui.passkeyLoginButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'passkey-login-button';
      button.className = 'menu-item';
      button.textContent = t('signInWithPasskey');
      button.hidden = !passkeysSupported();
      button.addEventListener('click', async () => {
        await signInWithPasskey();
      });
      ui.passkeyLoginButton = button;
      ui.headerActions.insertBefore(button, ui.googleLoginButton || ui.userSummary || null);
    }

    if (!ui.managePasskeysButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'manage-passkeys-button';
      button.className = 'menu-item';
      button.textContent = t('managePasskeys');
      button.hidden = true;
      button.addEventListener('click', async () => {
        await openPasskeyModal();
      });
      ui.managePasskeysButton = button;
      ui.headerActions.insertBefore(button, ui.switchUserButton || ui.userSummary || null);
    }

    if (!ui.statusMessage && ui.userSummary) {
      const status = document.createElement('span');
      status.className = 'caption';
      status.id = 'auth-status';
      ui.statusMessage = status;
      ui.userSummary.appendChild(status);
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

  function setAuthenticated(user) {
    currentUser = user;
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

    if (ui.passkeyLoginButton) {
      ui.passkeyLoginButton.hidden = true;
    }

    if (ui.managePasskeysButton) {
      ui.managePasskeysButton.hidden = !passkeysSupported();
    }

    updateSwitchUserLabel();
    updateLoginLink();
    setStatusMessage('');
    applyThemePreference(user.theme_preference);
    if (isGoogleMode()) {
      loadSwitchableAccounts();
    }
    window.dispatchEvent(new CustomEvent('auth:changed', { detail: { user } }));
  }

  function setUnauthenticated() {
    currentUser = null;
    if (ui.currentUserLabel) {
      ui.currentUserLabel.textContent = t('notSignedIn');
    }
    if (ui.currentUserName) {
      ui.currentUserName.textContent = '';
    }
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

    if (ui.passkeyLoginButton) {
      ui.passkeyLoginButton.hidden = !passkeysSupported();
    }

    if (ui.managePasskeysButton) {
      ui.managePasskeysButton.hidden = true;
    }

    if (passkeysSupported()) {
      setStatusMessage(googleMode ? t('statusSignInGoogleOrPasskey') : t('statusSelectUserOrPasskey'));
    } else {
      setStatusMessage(googleMode ? t('statusSignInGoogle') : t('statusSelectUser'));
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

    const user = response.data || { username };
    setAuthenticated(user);
    await loadUsers();
    return true;
  }

  async function initAuth() {
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
})();
