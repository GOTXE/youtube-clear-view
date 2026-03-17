// Login page overlay — blocks access until authenticated.
// Handles: login, register, Google OAuth, passkey, device pairing, setup wizard.

(() => {
  const t = (key, vars) => (
    window.ytcvI18n && typeof window.ytcvI18n.t === 'function'
      ? window.ytcvI18n.t(key, vars)
      : key
  );

  function getApi() {
    if (window.appApiClient) return window.appApiClient;
    if (window.APIClient && window.APP_CONFIG) {
      window.appApiClient = new window.APIClient(
        window.APP_CONFIG.API_BASE_URL,
        window.APP_CONFIG.REQUEST_TIMEOUT
      );
      return window.appApiClient;
    }
    return null;
  }

  // ── State ─────────────────────────────────────────────────────────────────

  let overlay = null;
  let currentView = 'login'; // 'login' | 'register' | 'wizard'
  let authProviderData = null;
  let visible = false;

  // ── Helpers ───────────────────────────────────────────────────────────────

  function el(id) { return document.getElementById(id); }

  function setError(containerId, message) {
    const container = el(containerId);
    if (!container) return;
    container.textContent = message || '';
    container.hidden = !message;
  }

  function setSubmitting(buttonId, labelId, loadingKey, isSubmitting) {
    const btn = el(buttonId);
    const lbl = el(labelId);
    if (!btn) return;
    btn.disabled = isSubmitting;
    if (lbl) lbl.textContent = isSubmitting ? t(loadingKey) : t(labelId === 'login-submit-label' ? 'loginSubmit' : labelId === 'register-submit-label' ? 'registerSubmit' : 'setupWizardSave');
  }

  function resolveOAuthUrl(path) {
    if (!path) return null;
    try {
      return new URL(path, window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL).toString();
    } catch (_) {
      return path;
    }
  }

  function notifyAuthSuccess(user) {
    // Prefer auth.js's setAuthenticated so it updates its internal state + UI
    if (typeof window.notifyAuthenticated === 'function') {
      window.notifyAuthenticated(user);
    } else {
      window.dispatchEvent(new CustomEvent('auth:changed', { detail: { user } }));
    }
  }

  // ── Show / Hide ───────────────────────────────────────────────────────────

  function show(options = {}) {
    if (!overlay) build();
    visible = true;
    overlay.hidden = false;
    document.body.classList.add('login-page-open');

    if (options.wizard) {
      showView('wizard', options);
    } else {
      showView('login');
    }
    applyI18n();
    applyAuthProviderButtons();
  }

  function hide() {
    if (!overlay) return;
    visible = false;
    overlay.hidden = true;
    document.body.classList.remove('login-page-open');
    clearErrors();
  }

  function isVisible() { return visible; }

  // ── View switching ────────────────────────────────────────────────────────

  function showView(view, options = {}) {
    currentView = view;
    const views = ['login', 'register', 'wizard'];
    views.forEach(v => {
      const panel = el(`lp-${v}`);
      if (panel) panel.hidden = v !== view;
    });

    if (view === 'wizard' && options.username) {
      const input = el('lp-wizard-username');
      if (input) input.value = options.username;
    }

    clearErrors();
  }

  function clearErrors() {
    ['lp-login-error', 'lp-register-error', 'lp-wizard-error'].forEach(id => {
      const node = el(id);
      if (node) { node.textContent = ''; node.hidden = true; }
    });
  }

  // ── Build DOM ─────────────────────────────────────────────────────────────

  function build() {
    overlay = document.createElement('section');
    overlay.id = 'login-page';
    overlay.className = 'login-page-overlay';
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-labelledby', 'lp-title');
    overlay.hidden = true;

    overlay.innerHTML = `
      <div class="login-page__card">
        <div class="login-page__brand">
          <h1 class="heading-1 login-page__app-name">YT Clear View</h1>
        </div>

        <!-- LOGIN PANEL -->
        <div id="lp-login" class="login-page__panel">
          <h2 id="lp-title" class="heading-2 login-page__title" data-i18n="loginPageTitle">Sign in</h2>
          <form id="lp-login-form" class="login-page__form" novalidate>
            <label class="field">
              <span class="field__label" data-i18n="loginUsername">Username</span>
              <input id="lp-login-username" class="field__input" type="text" autocomplete="username" autocapitalize="none" required>
            </label>
            <label class="field">
              <span class="field__label" data-i18n="loginPassword">Password</span>
              <input id="lp-login-password" class="field__input" type="password" autocomplete="current-password" required>
            </label>
            <p id="lp-login-error" class="login-page__error body" role="alert" hidden></p>
            <button id="lp-login-submit" class="button login-page__submit" type="submit">
              <span id="login-submit-label" data-i18n="loginSubmit">Sign in</span>
            </button>
          </form>
          <div class="login-page__divider" id="lp-divider" hidden>
            <span data-i18n="loginOrDivider">or</span>
          </div>
          <div class="login-page__alt-actions" id="lp-alt-actions">
            <button id="lp-google-button" class="button button--ghost login-page__google-btn" type="button" hidden data-i18n="loginWithGoogle">Continue with Google</button>
            <button id="lp-passkey-button" class="button button--ghost" type="button" hidden data-i18n="loginWithPasskey">Sign in with passkey</button>
            <button id="lp-device-button" class="button button--ghost" type="button" hidden data-i18n="loginWithDevice">Approve with device</button>
          </div>
          <p class="login-page__switch caption">
            <span data-i18n="loginNoAccount">No account yet?</span>
            <button id="lp-go-register" class="login-page__link" type="button" data-i18n="loginRegisterLink">Create one</button>
          </p>
        </div>

        <!-- REGISTER PANEL -->
        <div id="lp-register" class="login-page__panel" hidden>
          <h2 class="heading-2 login-page__title" data-i18n="registerTitle">Create account</h2>
          <form id="lp-register-form" class="login-page__form" novalidate>
            <label class="field">
              <span class="field__label" data-i18n="registerUsername">Username</span>
              <input id="lp-register-username" class="field__input" type="text" autocomplete="username" autocapitalize="none" required>
            </label>
            <label class="field">
              <span class="field__label" data-i18n="registerPassword">Password</span>
              <input id="lp-register-password" class="field__input" type="password" autocomplete="new-password" required>
            </label>
            <label class="field">
              <span class="field__label" data-i18n="registerConfirmPassword">Confirm password</span>
              <input id="lp-register-confirm" class="field__input" type="password" autocomplete="new-password" required>
            </label>
            <p id="lp-register-error" class="login-page__error body" role="alert" hidden></p>
            <button id="lp-register-submit" class="button login-page__submit" type="submit">
              <span id="register-submit-label" data-i18n="registerSubmit">Create account</span>
            </button>
          </form>
          <p class="login-page__switch caption">
            <span data-i18n="registerHaveAccount">Already have an account?</span>
            <button id="lp-go-login" class="login-page__link" type="button" data-i18n="registerLoginLink">Sign in</button>
          </p>
        </div>

        <!-- SETUP WIZARD PANEL -->
        <div id="lp-wizard" class="login-page__panel" hidden>
          <h2 class="heading-2 login-page__title" data-i18n="setupWizardTitle">Welcome! Set up your account</h2>
          <p class="body login-page__subtitle" data-i18n="setupWizardSubtitle">You signed in with Google. Customize your local identity.</p>
          <form id="lp-wizard-form" class="login-page__form" novalidate>
            <label class="field">
              <span class="field__label" data-i18n="setupWizardUsernameLabel">Choose a username</span>
              <input id="lp-wizard-username" class="field__input" type="text" autocomplete="username" autocapitalize="none" required>
              <span class="field__hint caption" data-i18n="setupWizardUsernameHint">This is how you sign in locally.</span>
            </label>
            <label class="field">
              <span class="field__label" data-i18n="setupWizardPasswordLabel">Set a password (optional)</span>
              <input id="lp-wizard-password" class="field__input" type="password" autocomplete="new-password">
              <span class="field__hint caption" data-i18n="setupWizardPasswordHint">Lets you sign in without Google on local networks.</span>
            </label>
            <p id="lp-wizard-error" class="login-page__error body" role="alert" hidden></p>
            <button id="lp-wizard-submit" class="button login-page__submit" type="submit">
              <span id="wizard-submit-label" data-i18n="setupWizardSave">Save and continue</span>
            </button>
            <button id="lp-wizard-skip" class="button button--ghost" type="button" data-i18n="setupWizardSkipPassword">Skip — use Google only</button>
          </form>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
    attachEvents();
  }

  // ── i18n apply ────────────────────────────────────────────────────────────

  function applyI18n() {
    if (!overlay) return;
    overlay.querySelectorAll('[data-i18n]').forEach(node => {
      const key = node.getAttribute('data-i18n');
      const translated = t(key);
      if (translated && translated !== key) {
        node.textContent = translated;
      }
    });
  }

  // ── Auth provider buttons ─────────────────────────────────────────────────

  async function loadAuthProvider() {
    const api = getApi();
    if (!api) return;
    try {
      const resp = await api.getAuthProvider();
      if (resp.ok && resp.data) {
        authProviderData = resp.data;
      }
    } catch (_) { /* ignore */ }
    applyAuthProviderButtons();
  }

  function applyAuthProviderButtons() {
    const googleBtn = el('lp-google-button');
    const passkeyBtn = el('lp-passkey-button');
    const divider = el('lp-divider');

    const hasGoogle = authProviderData && authProviderData.google_login_url;
    const hasPasskeys = Boolean(
      window.ytcvPasskeys
      && typeof window.ytcvPasskeys.isSupported === 'function'
      && window.ytcvPasskeys.isSupported()
    );

    if (googleBtn) googleBtn.hidden = !hasGoogle;
    if (passkeyBtn) passkeyBtn.hidden = !hasPasskeys;

    const anyAlt = hasGoogle || hasPasskeys;
    if (divider) divider.hidden = !anyAlt;
  }

  // ── Event handlers ────────────────────────────────────────────────────────

  function attachEvents() {
    // Login form
    const loginForm = el('lp-login-form');
    if (loginForm) {
      loginForm.addEventListener('submit', async e => {
        e.preventDefault();
        await handleLogin();
      });
    }

    // Register form
    const registerForm = el('lp-register-form');
    if (registerForm) {
      registerForm.addEventListener('submit', async e => {
        e.preventDefault();
        await handleRegister();
      });
    }

    // Wizard form
    const wizardForm = el('lp-wizard-form');
    if (wizardForm) {
      wizardForm.addEventListener('submit', async e => {
        e.preventDefault();
        await handleWizardSave(false);
      });
    }

    // Wizard skip button
    const wizardSkip = el('lp-wizard-skip');
    if (wizardSkip) {
      wizardSkip.addEventListener('click', () => handleWizardSave(true));
    }

    // Switch views
    const goRegister = el('lp-go-register');
    if (goRegister) goRegister.addEventListener('click', () => showView('register'));

    const goLogin = el('lp-go-login');
    if (goLogin) goLogin.addEventListener('click', () => showView('login'));

    // Google
    const googleBtn = el('lp-google-button');
    if (googleBtn) {
      googleBtn.addEventListener('click', () => {
        if (!authProviderData || !authProviderData.google_login_url) return;
        const url = resolveOAuthUrl(authProviderData.google_login_url);
        if (url) window.location.href = url;
      });
    }

    // Passkey
    const passkeyBtn = el('lp-passkey-button');
    if (passkeyBtn) {
      passkeyBtn.addEventListener('click', async () => {
        await handlePasskeyLogin();
      });
    }

    // Device
    const deviceBtn = el('lp-device-button');
    if (deviceBtn) {
      deviceBtn.addEventListener('click', () => {
        // Delegate to the existing pairing flow in auth.js
        window.dispatchEvent(new CustomEvent('login-page:request-device-pairing'));
      });
    }
  }

  // ── Action handlers ───────────────────────────────────────────────────────

  async function handleLogin() {
    const username = (el('lp-login-username') || {}).value || '';
    const password = (el('lp-login-password') || {}).value || '';
    const submitBtn = el('lp-login-submit');
    const labelEl = el('login-submit-label');

    if (!username.trim()) return;

    if (submitBtn) submitBtn.disabled = true;
    if (labelEl) labelEl.textContent = t('loginSigningIn');
    setError('lp-login-error', '');

    const api = getApi();
    if (!api) return;

    const resp = await api.login(username.trim(), password);

    if (submitBtn) submitBtn.disabled = false;
    if (labelEl) labelEl.textContent = t('loginSubmit');

    if (resp.ok && resp.data) {
      if (resp.data.mfa_required) {
        // MFA challenge — delegate to auth.js via event
        window.dispatchEvent(new CustomEvent('login-page:mfa-required', { detail: resp.data }));
        return;
      }
      if (resp.data.needs_setup) {
        showView('wizard', { username: resp.data.username || username });
        return;
      }
      // Successful login — auth.js will fire auth:changed
      notifyAuthSuccess(resp.data);
      return;
    }

    if (resp.status === 423) {
      setError('lp-login-error', t('loginLocked'));
      return;
    }
    setError('lp-login-error', t('loginFailed'));
  }

  async function handleRegister() {
    const username = (el('lp-register-username') || {}).value || '';
    const password = (el('lp-register-password') || {}).value || '';
    const confirm = (el('lp-register-confirm') || {}).value || '';
    const submitBtn = el('lp-register-submit');
    const labelEl = el('register-submit-label');

    if (!username.trim()) return;

    if (password !== confirm) {
      setError('lp-register-error', t('registerPasswordMismatch'));
      return;
    }
    if (password.length < 8) {
      setError('lp-register-error', t('registerPasswordShort'));
      return;
    }

    if (submitBtn) submitBtn.disabled = true;
    if (labelEl) labelEl.textContent = t('registerCreating');
    setError('lp-register-error', '');

    const api = getApi();
    if (!api) return;

    const resp = await api.register(username.trim(), password);

    if (submitBtn) submitBtn.disabled = false;
    if (labelEl) labelEl.textContent = t('registerSubmit');

    if (resp.ok && resp.data) {
      notifyAuthSuccess(resp.data);
      return;
    }

    if (resp.status === 409) {
      setError('lp-register-error', t('registerUsernameTaken'));
      return;
    }
    setError('lp-register-error', t('registerFailed'));
  }

  async function handleWizardSave(skip) {
    const username = (el('lp-wizard-username') || {}).value || '';
    const password = skip ? '' : ((el('lp-wizard-password') || {}).value || '');
    const submitBtn = el('lp-wizard-submit');
    const skipBtn = el('lp-wizard-skip');
    const labelEl = el('wizard-submit-label');

    if (!username.trim()) return;

    if (submitBtn) submitBtn.disabled = true;
    if (skipBtn) skipBtn.disabled = true;
    if (labelEl) labelEl.textContent = t('setupWizardSaving');
    setError('lp-wizard-error', '');

    const api = getApi();
    if (!api) return;

    const resp = await api.completeSetup(username.trim(), password || null);

    if (submitBtn) submitBtn.disabled = false;
    if (skipBtn) skipBtn.disabled = false;
    if (labelEl) labelEl.textContent = t('setupWizardSave');

    if (resp.ok && resp.data) {
      notifyAuthSuccess(resp.data);
      return;
    }

    if (resp.status === 409) {
      setError('lp-wizard-error', t('registerUsernameTaken'));
      return;
    }
    setError('lp-wizard-error', t('setupWizardError'));
  }

  async function handlePasskeyLogin() {
    if (!window.ytcvPasskeys || typeof window.ytcvPasskeys.authenticate !== 'function') {
      return;
    }
    const passkeyBtn = el('lp-passkey-button');
    if (passkeyBtn) passkeyBtn.disabled = true;

    try {
      const user = await window.ytcvPasskeys.authenticate();
      if (user) {
        notifyAuthSuccess(user);
      }
    } finally {
      if (passkeyBtn) passkeyBtn.disabled = false;
    }
  }

  // ── URL param handling ────────────────────────────────────────────────────

  function checkAuthStatusParam() {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('auth_status');
    if (!status) return null;

    params.delete('auth_status');
    const newQuery = params.toString();
    const newUrl = newQuery ? `${window.location.pathname}?${newQuery}` : window.location.pathname;
    window.history.replaceState({}, document.title, newUrl);

    return status;
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  function init() {
    // Listen for successful auth to hide login page
    window.addEventListener('auth:changed', event => {
      const user = event.detail ? event.detail.user : null;
      if (user && visible) {
        hide();
      }
    });

    // Load auth provider data early (for Google button)
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', loadAuthProvider);
    } else {
      loadAuthProvider();
    }
  }

  init();

  // ── Public API ────────────────────────────────────────────────────────────

  window.ytcvLoginPage = {
    show,
    hide,
    isVisible,
    checkAuthStatusParam,
    showView
  };
})();
