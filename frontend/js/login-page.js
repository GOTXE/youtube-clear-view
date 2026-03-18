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
  let currentView = 'login'; // 'login' | 'register' | 'wizard' | 'pairing'
  let authProviderData = null;
  let visible = false;
  let _pairingPollTimer = null;
  let _pairingPublicId = null;

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
    if (currentView === 'pairing' && view !== 'pairing') _stopPairingPoll();
    currentView = view;
    const views = ['login', 'register', 'wizard', 'pairing'];
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
            <button id="lp-device-button" class="button button--ghost" type="button" hidden data-i18n="signInWithDeviceCode">Sign in with device code</button>
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

        <!-- PAIRING PANEL -->
        <div id="lp-pairing" class="login-page__panel" hidden>
          <h2 class="heading-2 login-page__title" data-i18n="pairingLoginTitle">Sign in with device code</h2>
          <p class="body login-page__subtitle" data-i18n="pairingLoginDescription">Use a device code when another signed-in device is nearby to approve this sign-in.</p>
          <div id="lp-pairing-code-box" class="login-page__pairing-code" hidden>
            <p class="login-page__pairing-code-value" id="lp-pairing-code-display"></p>
            <p class="caption login-page__pairing-status" id="lp-pairing-status"></p>
          </div>
          <p id="lp-pairing-loading" class="body login-page__pairing-loading" data-i18n="pairingCodeStarting">Generating device code...</p>
          <p id="lp-pairing-error" class="login-page__error body" role="alert" hidden></p>
          <div class="login-page__alt-actions">
            <button id="lp-pairing-cancel" class="button button--ghost" type="button" data-i18n="cancel">Cancel</button>
            <button id="lp-pairing-new" class="button button--ghost" type="button" data-i18n="generateNewDeviceCode" hidden>Generate new code</button>
          </div>
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
        // Store CSRF token in the API client for subsequent auth requests
        if (resp.data.csrf_token && typeof api.setCsrfToken === 'function') {
          api.setCsrfToken(resp.data.csrf_token);
        }
      }
    } catch (_) { /* ignore */ }
    applyAuthProviderButtons();
  }

  function applyAuthProviderButtons() {
    const googleBtn = el('lp-google-button');
    const passkeyBtn = el('lp-passkey-button');
    const deviceBtn = el('lp-device-button');
    const divider = el('lp-divider');

    const hasGoogle = authProviderData && authProviderData.google_login_url;
    const hasPasskeys = Boolean(
      window.ytcvPasskeys
      && typeof window.ytcvPasskeys.isSupported === 'function'
      && window.ytcvPasskeys.isSupported()
      && typeof window.ytcvPasskeys.authenticateWithPasskey === 'function'
    );

    if (googleBtn) googleBtn.hidden = !hasGoogle;
    if (passkeyBtn) passkeyBtn.hidden = !hasPasskeys;
    if (deviceBtn) deviceBtn.hidden = false; // always available

    const anyAlt = hasGoogle || hasPasskeys || true;
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

    // Device pairing
    const deviceBtn = el('lp-device-button');
    if (deviceBtn) {
      deviceBtn.addEventListener('click', () => {
        showView('pairing');
        startPairingFlow();
      });
    }

    // Pairing cancel
    const pairingCancel = el('lp-pairing-cancel');
    if (pairingCancel) {
      pairingCancel.addEventListener('click', () => showView('login'));
    }

    // Pairing new code
    const pairingNew = el('lp-pairing-new');
    if (pairingNew) {
      pairingNew.addEventListener('click', () => startPairingFlow());
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

  // ── Pairing flow (device code login) ─────────────────────────────────────

  function _stopPairingPoll() {
    if (_pairingPollTimer) { clearInterval(_pairingPollTimer); _pairingPollTimer = null; }
    _pairingPublicId = null;
  }

  async function startPairingFlow() {
    _stopPairingPoll();

    const codeBox = el('lp-pairing-code-box');
    const loading = el('lp-pairing-loading');
    const newBtn = el('lp-pairing-new');
    const errEl = el('lp-pairing-error');
    const statusEl = el('lp-pairing-status');

    if (codeBox) codeBox.hidden = true;
    if (loading) loading.hidden = false;
    if (newBtn) newBtn.hidden = true;
    if (errEl) { errEl.textContent = ''; errEl.hidden = true; }

    const api = getApi();
    if (!api) return;

    const resp = await api.startPairing(null);
    if (!resp.ok || !resp.data) {
      if (loading) loading.hidden = true;
      if (errEl) { errEl.textContent = t('unableStartDeviceCode'); errEl.hidden = false; }
      if (newBtn) newBtn.hidden = false;
      return;
    }

    const { public_id, pairing_code, expires_at } = resp.data;
    _pairingPublicId = public_id;

    const codeDisplay = el('lp-pairing-code-display');
    if (codeDisplay) codeDisplay.textContent = pairing_code;
    if (statusEl) statusEl.textContent = t('pairingCodeWaiting');
    if (loading) loading.hidden = true;
    if (codeBox) codeBox.hidden = false;

    // Countdown display
    const expiresMs = expires_at ? new Date(expires_at).getTime() : Date.now() + 600_000;
    const countdownId = setInterval(() => {
      if (currentView !== 'pairing') { clearInterval(countdownId); return; }
      const remaining = Math.max(0, Math.round((expiresMs - Date.now()) / 1000));
      if (statusEl) {
        statusEl.textContent = remaining > 0
          ? `${t('pairingCodeWaiting')} (${remaining}s)`
          : t('unableClaimDeviceCode');
      }
      if (remaining === 0) {
        clearInterval(countdownId);
        _stopPairingPoll();
        if (newBtn) newBtn.hidden = false;
      }
    }, 1000);

    // Poll for approval
    _pairingPollTimer = setInterval(async () => {
      if (!_pairingPublicId || currentView !== 'pairing') {
        _stopPairingPoll(); clearInterval(countdownId); return;
      }
      const pollResp = await api.claimPairing(_pairingPublicId);
      if (pollResp.status === 410 || pollResp.status === 409) {
        // Expired or already used
        clearInterval(countdownId);
        _stopPairingPoll();
        if (statusEl) statusEl.textContent = t('unableClaimDeviceCode');
        if (newBtn) newBtn.hidden = false;
        return;
      }
      if (!pollResp.ok) return; // network error, keep polling
      if (pollResp.data && pollResp.data.pairing_claimed) {
        clearInterval(countdownId);
        _stopPairingPoll();
        if (statusEl) statusEl.textContent = t('pairingCodeApproved');
        notifyAuthSuccess(pollResp.data);
      }
      // status === 'pending' → keep polling
    }, 3000);
  }

  async function handlePasskeyLogin() {
    if (!window.ytcvPasskeys || typeof window.ytcvPasskeys.authenticateWithPasskey !== 'function') {
      return;
    }
    const passkeyBtnEl = el('lp-passkey-button');
    if (passkeyBtnEl) passkeyBtnEl.disabled = true;

    const passkeyApi = getApi();
    let passkeyResp = null;
    try {
      passkeyResp = await window.ytcvPasskeys.authenticateWithPasskey(passkeyApi);
    } catch (_) { /* user cancelled or error */ }

    if (passkeyBtnEl) passkeyBtnEl.disabled = false;

    if (passkeyResp && passkeyResp.ok && passkeyResp.data) {
      notifyAuthSuccess(passkeyResp.data);
      hide();
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
