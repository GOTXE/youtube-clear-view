// Authentication management with httpOnly cookie sessions.

(() => {
  let currentUser = null;
  let cachedUsers = [];
  let listenersReady = false;

  const userSelector = document.getElementById('user-selector');

  const ui = {
    userSelector,
    userSelectorWrapper: userSelector ? userSelector.closest('label') : null,
    currentUserLabel: document.getElementById('current-user'),
    appRoot: document.getElementById('app'),
    headerActions: document.querySelector('.header-actions'),
    userSummary: document.querySelector('.user-summary'),
    newUserButton: null,
    switchUserButton: null,
    statusMessage: null,
    modal: null
  };

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

  function applyThemePreference(themePreference) {
    const theme = themePreference === 'dark' ? 'dark' : 'light';
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

  function ensureButtons() {
    if (!ui.headerActions) {
      return;
    }

    if (!ui.newUserButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'new-user-button';
      button.className = 'button button--ghost';
      button.textContent = 'New user';
      button.addEventListener('click', () => {
        openCreateUserModal();
      });
      ui.newUserButton = button;
      ui.headerActions.insertBefore(button, ui.userSummary || null);
    }

    if (!ui.switchUserButton) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'switch-user-button';
      button.className = 'button button--ghost';
      button.textContent = 'Switch user';
      button.addEventListener('click', async () => {
        await switchUser();
      });
      ui.switchUserButton = button;
      ui.headerActions.insertBefore(button, ui.userSummary || null);
    }

    if (!ui.statusMessage && ui.userSummary) {
      const status = document.createElement('span');
      status.className = 'caption';
      status.id = 'auth-status';
      ui.statusMessage = status;
      ui.userSummary.appendChild(status);
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
      ui.currentUserLabel.textContent = `Signed in as ${displayName}`;
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

    setStatusMessage('');
    applyThemePreference(user.theme_preference);
    window.dispatchEvent(new CustomEvent('auth:changed', { detail: { user } }));
  }

  function setUnauthenticated() {
    currentUser = null;
    if (ui.currentUserLabel) {
      ui.currentUserLabel.textContent = 'Not signed in';
    }

    if (ui.userSelector) {
      ui.userSelector.value = '';
    }

    const selectorContainer = ui.userSelectorWrapper || ui.userSelector;
    if (selectorContainer) {
      selectorContainer.hidden = false;
    }

    if (ui.newUserButton) {
      ui.newUserButton.hidden = false;
    }

    if (ui.switchUserButton) {
      ui.switchUserButton.hidden = true;
    }

    setStatusMessage('Select a user to continue.');
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
    placeholder.textContent = users.length ? 'Select user' : 'No users yet';
    ui.userSelector.appendChild(placeholder);

    users.forEach(user => {
      const option = document.createElement('option');
      option.value = user.username;
      option.textContent = user.display_name || user.username;
      ui.userSelector.appendChild(option);
    });
  }

  async function loadUsers() {
    const api = getApiClient();
    if (!api) {
      setStatusMessage('API client not ready.', 'error');
      return;
    }

    const response = await api.getUsers();
    if (!response.ok) {
      setStatusMessage('Unable to load users.', 'error');
      return;
    }

    cachedUsers = response.data || [];
    renderUserOptions(cachedUsers);
  }

  function validateUsername(raw) {
    const cleaned = (raw || '').trim();
    if (!cleaned) {
      return { ok: false, message: 'Username is required.' };
    }

    if (!/^[a-z0-9]+$/i.test(cleaned)) {
      return { ok: false, message: 'Use only letters and numbers.' };
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
    title.textContent = 'Create user';

    const description = document.createElement('p');
    description.className = 'body';
    description.textContent = 'Choose a username to start your session.';

    const form = document.createElement('form');
    form.className = 'field';

    const label = document.createElement('label');
    label.className = 'field';

    const labelText = document.createElement('span');
    labelText.className = 'field__label';
    labelText.textContent = 'Username';

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
    cancelButton.textContent = 'Cancel';

    const submitButton = document.createElement('button');
    submitButton.type = 'submit';
    submitButton.className = 'button';
    submitButton.textContent = 'Create and sign in';

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
        errorText.textContent = 'Unable to create user.';
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
    const api = getApiClient();
    if (!api) {
      setStatusMessage('API client not ready.', 'error');
      return false;
    }

    setStatusMessage('Signing in...');
    const response = await api.login(username);
    if (!response.ok) {
      setStatusMessage('Sign-in failed.', 'error');
      return false;
    }

    const user = response.data || { username };
    setAuthenticated(user);
    await loadUsers();
    return true;
  }

  async function initAuth() {
    ensureButtons();
    ensureUserSelectorListener();

    if (!listenersReady) {
      window.addEventListener('auth-required', () => {
        handleAuthRequired();
      });
      listenersReady = true;
    }

    const api = getApiClient();
    if (!api) {
      setStatusMessage('API client not ready.', 'error');
      setUnauthenticated();
      return null;
    }

    const response = await api.getCurrentUser();
    if (response.ok && response.data) {
      setAuthenticated(response.data);
      return response.data;
    }

    if (response.status !== 401) {
      setStatusMessage('Unable to verify session.', 'error');
    }

    setUnauthenticated();
    await loadUsers();
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
    await loadUsers();

    if (reloadPage) {
      window.location.reload();
    }
  }

  async function logout() {
    await performLogout(true);
  }

  async function switchUser() {
    await performLogout(false);
  }

  function handleAuthRequired() {
    setUnauthenticated();
    loadUsers();
  }

  window.initAuth = initAuth;
  window.getCurrentUser = getCurrentUser;
  window.isAuthenticated = isAuthenticated;
  window.logout = logout;
  window.switchUser = switchUser;
})();
