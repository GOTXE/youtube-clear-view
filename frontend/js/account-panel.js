// Account management panel — Password, Passkeys, TOTP, Devices, YouTube.

(() => {
  const t = (key, vars) => {
    if (window.ytcvI18n && typeof window.ytcvI18n.t === 'function') {
      return window.ytcvI18n.t(key, vars);
    }
    return key;
  };

  function getApi() {
    return window.appApiClient || null;
  }

  // ── State ─────────────────────────────────────────────────────────────────

  let overlay = null;
  let activeTab = 'profile';
  let currentDeviceIdentifier = null;

  // ── Public API ────────────────────────────────────────────────────────────

  function open(tab) {
    if (!overlay) build();
    activeTab = tab || 'profile';
    overlay.style.display = '';
    document.body.classList.add('account-panel-open');
    switchTab(activeTab);
    loadTab(activeTab);
  }

  function close() {
    if (!overlay) return;
    overlay.style.display = 'none';
    document.body.classList.remove('account-panel-open');
  }

  // ── Build DOM ─────────────────────────────────────────────────────────────

  function build() {
    overlay = document.createElement('section');
    overlay.id = 'account-panel';
    overlay.className = 'account-panel-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'ap-title');
    overlay.style.display = 'none';

    overlay.innerHTML = `
      <div class="account-panel__card">
        <header class="account-panel__header">
          <h2 id="ap-title" class="heading-2" data-i18n="accountPanelTitle">My account</h2>
          <button id="ap-close" class="account-panel__close" type="button" aria-label="${t('close')}">✕</button>
        </header>

        <nav class="account-panel__tabs" role="tablist">
          <button class="account-panel__tab" role="tab" data-tab="profile" data-i18n="accountTabProfile">Profile</button>
          <button class="account-panel__tab" role="tab" data-tab="password" data-i18n="accountTabPassword">Password</button>
          <button class="account-panel__tab" role="tab" data-tab="passkeys" data-i18n="accountTabPasskeys">Passkeys</button>
          <button class="account-panel__tab" role="tab" data-tab="totp" data-i18n="accountTabTotp">Authenticator</button>
          <button class="account-panel__tab" role="tab" data-tab="devices" data-i18n="accountTabDevices">Devices</button>
          <button class="account-panel__tab" role="tab" data-tab="youtube" data-i18n="accountTabYoutube">YouTube</button>
        </nav>

        <div class="account-panel__body">
          <div id="ap-tab-profile" class="account-panel__panel" role="tabpanel" style="display:none">
            <div id="ap-profile-content" class="account-panel__profile-content"></div>
          </div>

          <div id="ap-tab-password" class="account-panel__panel" role="tabpanel" style="display:none">
            <form id="ap-password-form" class="account-panel__form" novalidate>
              <label class="field">
                <span class="field__label" data-i18n="accountPasswordCurrent">Current password</span>
                <input id="ap-pw-current" class="field__input" type="password" autocomplete="current-password" required>
              </label>
              <label class="field">
                <span class="field__label" data-i18n="accountPasswordNew">New password</span>
                <input id="ap-pw-new" class="field__input" type="password" autocomplete="new-password" required>
              </label>
              <label class="field">
                <span class="field__label" data-i18n="accountPasswordConfirm">Confirm new password</span>
                <input id="ap-pw-confirm" class="field__input" type="password" autocomplete="new-password" required>
              </label>
              <p id="ap-pw-msg" class="account-panel__msg"></p>
              <button id="ap-pw-submit" class="button" type="submit" data-i18n="accountPasswordSave">Change password</button>
            </form>
          </div>

          <div id="ap-tab-passkeys" class="account-panel__panel" role="tabpanel" style="display:none">
            <div id="ap-passkeys-list" class="account-panel__list"></div>
            <div class="account-panel__actions">
              <label class="field account-panel__inline-field">
                <input id="ap-passkey-label" class="field__input" type="text" maxlength="64" placeholder="${t('accountPasskeyLabelPlaceholder')}">
              </label>
              <button id="ap-passkey-add" class="button" type="button" data-i18n="accountPasskeyAdd">Add passkey</button>
            </div>
            <p id="ap-passkeys-msg" class="account-panel__msg"></p>
          </div>

          <div id="ap-tab-totp" class="account-panel__panel" role="tabpanel" style="display:none">
            <div id="ap-totp-status" class="account-panel__totp-status"></div>
          </div>

          <div id="ap-tab-devices" class="account-panel__panel" role="tabpanel" style="display:none">
            <div id="ap-devices-list" class="account-panel__list"></div>
            <p id="ap-devices-msg" class="account-panel__msg"></p>
            <div id="ap-devices-approve" class="account-panel__pairing-section"></div>
          </div>

          <div id="ap-tab-youtube" class="account-panel__panel" role="tabpanel" style="display:none">
            <div id="ap-youtube-status" class="account-panel__youtube-status"></div>
          </div>
        </div>

        <footer class="account-panel__footer">
          <button id="ap-cancel" class="button button--ghost" type="button" data-i18n="cancel">${t('cancel')}</button>
        </footer>
      </div>
    `;

    document.body.appendChild(overlay);
    applyI18n();
    attachEvents();
  }

  function applyI18n() {
    if (!overlay) return;
    overlay.querySelectorAll('[data-i18n]').forEach(node => {
      const key = node.getAttribute('data-i18n');
      const val = t(key);
      if (val && val !== key) node.textContent = val;
    });
  }

  // ── Tab switching ─────────────────────────────────────────────────────────

  function switchTab(tabName) {
    activeTab = tabName;
    overlay.querySelectorAll('.account-panel__tab').forEach(btn => {
      const active = btn.dataset.tab === tabName;
      btn.classList.toggle('account-panel__tab--active', active);
      btn.setAttribute('aria-selected', String(active));
    });
    overlay.querySelectorAll('.account-panel__panel').forEach(panel => {
      panel.style.display = panel.id === `ap-tab-${tabName}` ? '' : 'none';
    });
  }

  function loadTab(tabName) {
    switch (tabName) {
      case 'profile': loadProfile(); break;
      case 'passkeys': loadPasskeys(); break;
      case 'totp': loadTotp(); break;
      case 'devices': loadDevices(); break;
      case 'youtube': loadYoutube(); break;
    }
  }

  // ── Event wiring ──────────────────────────────────────────────────────────

  function attachEvents() {
    const closeBtn = document.getElementById('ap-close');
    if (closeBtn) closeBtn.addEventListener('click', close);

    const cancelBtn = document.getElementById('ap-cancel');
    if (cancelBtn) cancelBtn.addEventListener('click', close);

    overlay.addEventListener('click', e => {
      if (e.target === overlay) close();
    });

    overlay.querySelectorAll('.account-panel__tab').forEach(btn => {
      btn.addEventListener('click', () => {
        switchTab(btn.dataset.tab);
        loadTab(btn.dataset.tab);
      });
    });

    // Password form
    const pwForm = document.getElementById('ap-password-form');
    if (pwForm) pwForm.addEventListener('submit', e => { e.preventDefault(); handlePasswordChange(); });

    // Passkey add
    const passkeyAdd = document.getElementById('ap-passkey-add');
    if (passkeyAdd) passkeyAdd.addEventListener('click', handlePasskeyAdd);
  }

  // ── Profile tab ─────────────────────────────────────────────────────────

  async function loadProfile() {
    const container = document.getElementById('ap-profile-content');
    if (!container) return;
    container.textContent = '…';

    const api = getApi();
    if (!api) return;
    const resp = await api.getCurrentUser();
    if (!resp.ok) { container.textContent = ''; return; }

    renderProfile(resp.data, container);
  }

  function renderProfile(data, container) {
    container.innerHTML = '';
    const isLocal = data.auth_provider === 'local';
    const providerLabel = isLocal ? t('accountProfileAuthLocal') : t('accountProfileAuthGoogle');

    container.innerHTML = `
      <div class="account-panel__profile-badge">
        <span class="account-panel__auth-badge account-panel__auth-badge--${isLocal ? 'local' : 'google'}">${escapeHtml(providerLabel)}</span>
      </div>
      <form id="ap-profile-form" class="account-panel__form" novalidate>
        <label class="field">
          <span class="field__label">${t('accountProfileUsername')}</span>
          <input id="ap-profile-username" class="field__input" type="text" value="${escapeHtml(data.username || '')}" maxlength="64">
          <span class="field__hint">${t('accountProfileUsernameHint')}</span>
        </label>
        <label class="field">
          <span class="field__label">${t('accountProfileDisplayName')}</span>
          <input id="ap-profile-display-name" class="field__input" type="text" value="${escapeHtml(data.display_name || '')}" maxlength="128">
        </label>
        <label class="field">
          <span class="field__label">${t('accountProfileEmail')}</span>
          <input id="ap-profile-email" class="field__input field__input--readonly" type="text" value="${escapeHtml(data.email || '—')}" readonly>
        </label>
        <p id="ap-profile-msg" class="account-panel__msg" hidden></p>
        <button id="ap-profile-save" class="button" type="submit">${t('accountProfileSave')}</button>
      </form>
    `;

    const form = document.getElementById('ap-profile-form');
    if (form) {
      form.addEventListener('submit', async e => {
        e.preventDefault();
        const saveBtn = document.getElementById('ap-profile-save');
        if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = t('accountPasswordSaving'); }
        clearMsg('ap-profile-msg');

        const payload = {
          display_name: (document.getElementById('ap-profile-display-name') || {}).value || '',
          username: (document.getElementById('ap-profile-username') || {}).value || ''
        };

        const api = getApi();
        const r = await api.updateProfile(payload);

        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = t('accountProfileSave'); }

        if (r.ok) {
          showMsg('ap-profile-msg', t('accountProfileSaved'), 'success');
        } else if (r.status === 409) {
          showMsg('ap-profile-msg', t('accountProfileUsernameTaken'), 'error');
        } else {
          showMsg('ap-profile-msg', t('accountPasswordFailed'), 'error');
        }
      });
    }
  }

  // ── Password tab ──────────────────────────────────────────────────────────

  async function handlePasswordChange() {
    const current = (document.getElementById('ap-pw-current') || {}).value || '';
    const newPw = (document.getElementById('ap-pw-new') || {}).value || '';
    const confirm = (document.getElementById('ap-pw-confirm') || {}).value || '';
    const submitBtn = document.getElementById('ap-pw-submit');

    if (newPw !== confirm) { showMsg('ap-pw-msg', t('accountPasswordMismatch'), 'error'); return; }
    if (newPw.length < 8) { showMsg('ap-pw-msg', t('accountPasswordShort'), 'error'); return; }

    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = t('accountPasswordSaving'); }
    clearMsg('ap-pw-msg');

    const api = getApi();
    if (!api) return;
    const resp = await api.changePassword(current, newPw);

    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = t('accountPasswordSave'); }

    if (resp.ok) {
      showMsg('ap-pw-msg', t('accountPasswordSuccess'), 'success');
      ['ap-pw-current', 'ap-pw-new', 'ap-pw-confirm'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      });
      return;
    }
    if (resp.status === 400 || resp.status === 401) {
      showMsg('ap-pw-msg', t('accountPasswordWrong'), 'error');
      return;
    }
    showMsg('ap-pw-msg', t('accountPasswordFailed'), 'error');
  }

  // ── Passkeys tab ──────────────────────────────────────────────────────────

  async function loadPasskeys() {
    const container = document.getElementById('ap-passkeys-list');
    if (!container) return;
    container.textContent = '…';

    const api = getApi();
    if (!api) return;
    const resp = await api.getPasskeys();
    if (!resp.ok) { container.textContent = ''; return; }

    const passkeys = (resp.data && resp.data.passkeys) || [];
    renderPasskeys(passkeys);
  }

  function renderPasskeys(passkeys) {
    const container = document.getElementById('ap-passkeys-list');
    if (!container) return;
    container.innerHTML = '';

    if (!passkeys.length) {
      const p = document.createElement('p');
      p.className = 'account-panel__empty body';
      p.textContent = t('accountPasskeysNone');
      container.appendChild(p);
      return;
    }

    passkeys.forEach(pk => {
      const row = document.createElement('div');
      row.className = 'account-panel__row';
      row.innerHTML = `
        <div class="account-panel__row-info">
          <span class="account-panel__row-name body">${escapeHtml(pk.label || `Passkey ${pk.id}`)}</span>
          <span class="account-panel__row-meta caption">${t('accountPasskeyAdded')}: ${formatDate(pk.created_at)}</span>
        </div>
        <button class="button button--ghost button--sm" data-id="${pk.id}" data-action="revoke-passkey">${t('accountPasskeyRevoke')}</button>
      `;
      container.appendChild(row);
    });

    container.querySelectorAll('[data-action="revoke-passkey"]').forEach(btn => {
      btn.addEventListener('click', () => handleRevokePasskey(Number(btn.dataset.id), btn));
    });
  }

  async function handleRevokePasskey(id, btn) {
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = t('accountPasskeyRevoking');

    const api = getApi();
    const resp = await api.deletePasskey(id);
    if (resp.ok) {
      showMsg('ap-passkeys-msg', t('accountPasskeyRevoked'), 'success');
      loadPasskeys();
    } else {
      btn.disabled = false;
      btn.textContent = orig;
      showMsg('ap-passkeys-msg', t('accountPasskeyRevokeFailed'), 'error');
    }
  }

  async function handlePasskeyAdd() {
    if (!window.ytcvPasskeys || typeof window.ytcvPasskeys.registerPasskey !== 'function') return;
    const labelInput = document.getElementById('ap-passkey-label');
    const label = labelInput ? labelInput.value.trim() : '';
    const api = getApi();
    if (!api) return;

    const addBtn = document.getElementById('ap-passkey-add');
    if (addBtn) addBtn.disabled = true;
    clearMsg('ap-passkeys-msg');

    try {
      await window.ytcvPasskeys.registerPasskey(api, label);
      if (labelInput) labelInput.value = '';
      loadPasskeys();
    } catch (_) {
      showMsg('ap-passkeys-msg', t('accountPasskeyRevokeFailed'), 'error');
    } finally {
      if (addBtn) addBtn.disabled = false;
    }
  }

  // ── TOTP tab ──────────────────────────────────────────────────────────────

  async function loadTotp() {
    const container = document.getElementById('ap-totp-status');
    if (!container) return;
    container.textContent = '…';

    const api = getApi();
    if (!api) return;
    const resp = await api.getMfaStatus();
    if (!resp.ok) { container.textContent = ''; return; }

    renderTotpStatus(resp.data);
  }

  function renderTotpStatus(data) {
    const container = document.getElementById('ap-totp-status');
    if (!container) return;
    container.innerHTML = '';

    const enabled = data && data.totp_enabled;
    const remaining = data ? data.recovery_codes_remaining : 0;

    const statusEl = document.createElement('p');
    statusEl.className = 'body account-panel__totp-line';
    statusEl.textContent = enabled ? t('accountTotpEnabled') : t('accountTotpDisabled');
    container.appendChild(statusEl);

    if (enabled) {
      const codesEl = document.createElement('p');
      codesEl.className = 'caption account-panel__totp-line';
      codesEl.textContent = t('accountTotpRecoveryCodes', { count: remaining });
      container.appendChild(codesEl);
    }

    const msgEl = document.createElement('p');
    msgEl.id = 'ap-totp-msg';
    msgEl.className = 'account-panel__msg';
    msgEl.hidden = true;
    container.appendChild(msgEl);

    const actionsEl = document.createElement('div');
    actionsEl.className = 'account-panel__actions';

    if (!enabled) {
      const setupBtn = document.createElement('button');
      setupBtn.className = 'button';
      setupBtn.textContent = t('accountTotpSetup');
      setupBtn.addEventListener('click', () => {
        setupBtn.disabled = true;
        renderTotpSetupFlow(container);
      });
      actionsEl.appendChild(setupBtn);
    } else {
      const disableBtn = document.createElement('button');
      disableBtn.className = 'button button--ghost';
      disableBtn.textContent = t('accountTotpDisable');
      disableBtn.addEventListener('click', () => {
        disableBtn.disabled = true;
        regenBtn.disabled = true;
        renderTotpDisableFlow(container);
      });
      actionsEl.appendChild(disableBtn);

      const regenBtn = document.createElement('button');
      regenBtn.className = 'button button--ghost';
      regenBtn.textContent = t('accountTotpRegenerateRecovery');
      regenBtn.addEventListener('click', () => {
        regenBtn.disabled = true;
        disableBtn.disabled = true;
        renderTotpRegenFlow(container);
      });
      actionsEl.appendChild(regenBtn);
    }

    container.appendChild(actionsEl);
  }

  function renderTotpSetupFlow(container) {
    container.innerHTML = '<p class="body">…</p>';
    const api = getApi();
    if (!api) return;

    api.setupTotp().then(resp => {
      if (!resp.ok) { container.innerHTML = ''; loadTotp(); return; }
      const { secret, otpauth_url, qr_code } = resp.data;

      const qrHtml = qr_code
        ? `<div class="account-panel__qr"><img src="${qr_code}" alt="TOTP QR" width="180" height="180"></div>`
        : `<div class="account-panel__qr"><a href="${escapeHtml(otpauth_url)}" class="caption" style="word-break:break-all">${escapeHtml(otpauth_url)}</a></div>`;

      container.innerHTML = `
        <p class="body">${t('accountTotpScanQr')}</p>
        ${qrHtml}
        <p class="caption account-panel__totp-secret">${escapeHtml(secret)}</p>
        <form id="ap-totp-confirm-form" class="account-panel__form" novalidate>
          <label class="field">
            <span class="field__label" data-i18n="accountTotpCodeLabel">${t('accountTotpCodeLabel')}</span>
            <input id="ap-totp-code" class="field__input" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required>
          </label>
          <p id="ap-totp-msg" class="account-panel__msg" hidden></p>
          <div class="account-panel__actions">
            <button id="ap-totp-activate" class="button" type="submit">${t('accountTotpActivate')}</button>
            <button id="ap-totp-cancel" class="button button--ghost" type="button">${t('cancel')}</button>
          </div>
        </form>
      `;

      const form = document.getElementById('ap-totp-confirm-form');
      if (form) {
        form.addEventListener('submit', async e => {
          e.preventDefault();
          const code = (document.getElementById('ap-totp-code') || {}).value || '';
          const activateBtn = document.getElementById('ap-totp-activate');
          if (activateBtn) { activateBtn.disabled = true; activateBtn.textContent = t('accountTotpActivating'); }
          clearMsg('ap-totp-msg');

          const r = await api.confirmTotp(code);
          if (r.ok) {
            showMsg('ap-totp-msg', t('accountTotpActivated'), 'success');
            setTimeout(() => loadTotp(), 1500);
          } else {
            if (activateBtn) { activateBtn.disabled = false; activateBtn.textContent = t('accountTotpActivate'); }
            showMsg('ap-totp-msg', t('accountTotpActivateFailed'), 'error');
          }
        });
      }

      const cancelBtn = document.getElementById('ap-totp-cancel');
      if (cancelBtn) cancelBtn.addEventListener('click', () => loadTotp());
    });
  }

  function renderTotpDisableFlow(container) {
    container.innerHTML = `
      <p class="body">${t('accountTotpDisableConfirm')}</p>
      <form id="ap-totp-disable-form" class="account-panel__form" novalidate>
        <label class="field">
          <span class="field__label">${t('accountTotpCodeLabel')}</span>
          <input id="ap-totp-disable-code" class="field__input" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6">
        </label>
        <p id="ap-totp-msg" class="account-panel__msg" hidden></p>
        <div class="account-panel__actions">
          <button id="ap-totp-disable-submit" class="button button--ghost" type="submit">${t('accountTotpDisable')}</button>
          <button id="ap-totp-disable-cancel" class="button button--ghost" type="button">${t('cancel')}</button>
        </div>
      </form>
    `;

    const form = document.getElementById('ap-totp-disable-form');
    if (form) {
      form.addEventListener('submit', async e => {
        e.preventDefault();
        const code = (document.getElementById('ap-totp-disable-code') || {}).value || '';
        const btn = document.getElementById('ap-totp-disable-submit');
        if (btn) btn.disabled = true;
        clearMsg('ap-totp-msg');

        const api = getApi();
        const r = await api.disableTotp(code || null, null);
        if (r.ok) {
          showMsg('ap-totp-msg', t('accountTotpDisabled2'), 'success');
          setTimeout(() => loadTotp(), 1200);
        } else {
          if (btn) btn.disabled = false;
          showMsg('ap-totp-msg', t('accountTotpDisableFailed'), 'error');
        }
      });
    }

    const cancelBtn = document.getElementById('ap-totp-disable-cancel');
    if (cancelBtn) cancelBtn.addEventListener('click', () => loadTotp());
  }

  function renderTotpRegenFlow(container) {
    container.innerHTML = `
      <p class="body">${t('accountTotpCodeLabel')}:</p>
      <form id="ap-totp-regen-form" class="account-panel__form" novalidate>
        <label class="field">
          <input id="ap-totp-regen-code" class="field__input" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required>
        </label>
        <p id="ap-totp-msg" class="account-panel__msg" hidden></p>
        <div class="account-panel__actions">
          <button id="ap-totp-regen-submit" class="button" type="submit">${t('accountTotpRegenerateRecovery')}</button>
          <button id="ap-totp-regen-cancel" class="button button--ghost" type="button">${t('cancel')}</button>
        </div>
        <div id="ap-totp-regen-codes" class="account-panel__recovery-codes" hidden></div>
      </form>
    `;

    const form = document.getElementById('ap-totp-regen-form');
    if (form) {
      form.addEventListener('submit', async e => {
        e.preventDefault();
        const code = (document.getElementById('ap-totp-regen-code') || {}).value || '';
        const btn = document.getElementById('ap-totp-regen-submit');
        if (btn) { btn.disabled = true; btn.textContent = t('accountTotpRegenerating'); }
        clearMsg('ap-totp-msg');

        const api = getApi();
        const r = await api.regenerateRecoveryCodes(code);
        if (r.ok && r.data && r.data.recovery_codes) {
          const codesEl = document.getElementById('ap-totp-regen-codes');
          if (codesEl) {
            codesEl.hidden = false;
            codesEl.innerHTML = `<p class="caption">${t('accountTotpRegenerateSuccess')}</p><pre class="account-panel__code-block">${r.data.recovery_codes.join('\n')}</pre>`;
          }
          showMsg('ap-totp-msg', '', '');
          if (btn) { btn.disabled = false; btn.textContent = t('accountTotpRegenerateRecovery'); }
        } else {
          if (btn) { btn.disabled = false; btn.textContent = t('accountTotpRegenerateRecovery'); }
          showMsg('ap-totp-msg', t('accountTotpRegenerateFailed'), 'error');
        }
      });
    }

    const cancelBtn = document.getElementById('ap-totp-regen-cancel');
    if (cancelBtn) cancelBtn.addEventListener('click', () => loadTotp());
  }

  // ── Devices tab ───────────────────────────────────────────────────────────

  async function loadDevices() {
    const container = document.getElementById('ap-devices-list');
    if (!container) return;
    container.textContent = '…';

    const api = getApi();
    if (!api) return;
    const resp = await api.getDevices();
    if (!resp.ok) { container.textContent = ''; return; }

    renderDevices(resp.data || []);
    renderPairingApproveSection();
  }

  function renderDevices(devices) {
    const container = document.getElementById('ap-devices-list');
    if (!container) return;
    container.innerHTML = '';

    if (!devices.length) {
      const p = document.createElement('p');
      p.className = 'account-panel__empty body';
      p.textContent = t('accountDevicesNone');
      container.appendChild(p);
      return;
    }

    devices.forEach(device => {
      const isCurrent = device.device_identifier === currentDeviceIdentifier;
      const row = document.createElement('div');
      row.className = 'account-panel__row';

      const typeLabel = device.device_type || '?';
      const lastUsed = device.last_used_at ? formatDate(device.last_used_at) : '—';
      const label = device.user_agent ? device.user_agent.slice(0, 60) : typeLabel;

      row.innerHTML = `
        <div class="account-panel__row-info">
          <span class="account-panel__row-name body">${escapeHtml(label)}${isCurrent ? ` <span class="account-panel__badge">${t('accountDeviceThisDevice')}</span>` : ''}</span>
          <span class="account-panel__row-meta caption">${t('accountDeviceLastUsed', { date: lastUsed })}</span>
        </div>
        ${isCurrent ? '' : `<button class="button button--ghost button--sm" data-id="${device.id}" data-action="revoke-device">${t('accountDeviceRevoke')}</button>`}
      `;
      container.appendChild(row);
    });

    container.querySelectorAll('[data-action="revoke-device"]').forEach(btn => {
      btn.addEventListener('click', () => handleRevokeDevice(Number(btn.dataset.id), btn));
    });
  }

  async function handleRevokeDevice(id, btn) {
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = t('accountDeviceRevoking');

    const api = getApi();
    const resp = await api.deleteDevice(id);
    if (resp.ok) {
      showMsg('ap-devices-msg', t('accountDeviceRevoked'), 'success');
      loadDevices();
    } else {
      btn.disabled = false;
      btn.textContent = orig;
      showMsg('ap-devices-msg', t('accountDeviceRevokeFailed'), 'error');
    }
  }

  function renderPairingApproveSection() {
    const container = document.getElementById('ap-devices-approve');
    if (!container) return;
    container.innerHTML = `
      <p class="body account-panel__section-title">${t('pairingApproveTitle')}</p>
      <p class="caption account-panel__section-desc">${t('pairingApproveDescription')}</p>
      <div class="account-panel__pairing-form">
        <input id="ap-pairing-code-input" class="field__input account-panel__pairing-input"
          type="text" maxlength="9" autocomplete="off" spellcheck="false"
          placeholder="XXXX-XXXX">
        <button id="ap-pairing-approve-btn" class="button" type="button">${t('approveDeviceCode')}</button>
      </div>
      <p id="ap-pairing-msg" class="account-panel__msg" hidden></p>
    `;

    const input = document.getElementById('ap-pairing-code-input');
    if (input) {
      // Auto-format: uppercase + insert hyphen after 4th char
      input.addEventListener('input', () => {
        const raw = input.value.replace(/[^A-Z0-9]/gi, '').toUpperCase().slice(0, 8);
        input.value = raw.length > 4 ? `${raw.slice(0, 4)}-${raw.slice(4)}` : raw;
      });
      input.addEventListener('keydown', e => {
        if (e.key === 'Enter') handleApprovePairing();
        // Allow backspace to remove hyphen cleanly
        if (e.key === 'Backspace' && input.value.endsWith('-')) {
          e.preventDefault();
          input.value = input.value.slice(0, -1);
        }
      });
    }

    const btn = document.getElementById('ap-pairing-approve-btn');
    if (btn) btn.addEventListener('click', () => handleApprovePairing());
  }

  async function handleApprovePairing() {
    const input = document.getElementById('ap-pairing-code-input');
    const btn = document.getElementById('ap-pairing-approve-btn');
    const code = (input ? input.value.trim().toUpperCase() : '');
    if (!code) return;

    if (btn) { btn.disabled = true; btn.textContent = t('approvingDeviceCode'); }
    clearMsg('ap-pairing-msg');

    const api = getApi();
    const resp = await api.approvePairing(code);

    if (btn) { btn.disabled = false; btn.textContent = t('approveDeviceCode'); }

    if (resp.ok) {
      if (input) input.value = '';
      showMsg('ap-pairing-msg', t('deviceCodeApprovedSuccess'), 'success');
      return;
    }
    if (resp.status === 404 || resp.status === 410) {
      showMsg('ap-pairing-msg', t('unableApproveDeviceCode'), 'error');
    } else if (resp.status === 409) {
      showMsg('ap-pairing-msg', t('unableApproveDeviceCode'), 'error');
    } else {
      showMsg('ap-pairing-msg', t('unableApproveDeviceCode'), 'error');
    }
  }

  // ── YouTube tab ───────────────────────────────────────────────────────────

  async function loadYoutube() {
    const container = document.getElementById('ap-youtube-status');
    if (!container) return;
    container.textContent = '…';

    const api = getApi();
    if (!api) return;
    const resp = await api.getCurrentUser();
    if (!resp.ok) { container.textContent = ''; return; }

    renderYoutubeStatus(resp.data);
  }

  function renderYoutubeStatus(data) {
    const container = document.getElementById('ap-youtube-status');
    if (!container) return;
    container.innerHTML = '';

    const linked = data && data.google_auth_status === 'active';
    const googleAvailable = Boolean(
      window._ytcvAuthProvider && window._ytcvAuthProvider.google_link_url
    );

    const statusEl = document.createElement('p');
    statusEl.className = 'body';
    statusEl.textContent = linked ? t('accountYoutubeLinked') : t('accountYoutubeNotLinked');
    container.appendChild(statusEl);

    const msgEl = document.createElement('p');
    msgEl.id = 'ap-youtube-msg';
    msgEl.className = 'account-panel__msg';
    msgEl.hidden = true;
    container.appendChild(msgEl);

    const actionsEl = document.createElement('div');
    actionsEl.className = 'account-panel__actions';

    if (googleAvailable) {
      const linkBtn = document.createElement('button');
      linkBtn.className = 'button';
      linkBtn.textContent = linked ? t('accountYoutubeRelink') : t('accountYoutubeLink');
      linkBtn.addEventListener('click', () => {
        const url = resolveUrl(window._ytcvAuthProvider.google_link_url);
        if (url) window.location.href = url;
      });
      actionsEl.appendChild(linkBtn);
    }

    if (linked) {
      const unlinkBtn = document.createElement('button');
      unlinkBtn.className = 'button button--ghost';
      unlinkBtn.textContent = t('accountYoutubeUnlink');
      unlinkBtn.addEventListener('click', () => handleYoutubeUnlink(unlinkBtn));
      actionsEl.appendChild(unlinkBtn);
    }

    container.appendChild(actionsEl);
  }

  async function handleYoutubeUnlink(btn) {
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = t('accountYoutubeUnlinking');

    const api = getApi();
    const resp = await api.unlinkGoogle();
    if (resp.ok) {
      showMsg('ap-youtube-msg', t('accountYoutubeUnlinkSuccess'), 'success');
      loadYoutube();
    } else {
      btn.disabled = false;
      btn.textContent = orig;
      showMsg('ap-youtube-msg', t('accountYoutubeUnlinkFailed'), 'error');
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  function showMsg(id, text, type) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text || '';
    el.hidden = !text;
    el.className = `account-panel__msg${type === 'error' ? ' account-panel__msg--error' : type === 'success' ? ' account-panel__msg--success' : ''}`;
  }

  function clearMsg(id) {
    showMsg(id, '', '');
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatDate(isoString) {
    if (!isoString) return '—';
    try {
      return new Date(isoString).toLocaleDateString();
    } catch (_) {
      return isoString;
    }
  }

  function resolveUrl(path) {
    if (!path) return null;
    try {
      return new URL(path, window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL).toString();
    } catch (_) {
      return path;
    }
  }

  // ── Auth provider cache ───────────────────────────────────────────────────

  function cacheAuthProvider(data) {
    window._ytcvAuthProvider = data;
  }

  // Store auth provider data when loaded elsewhere
  window.addEventListener('auth:provider-loaded', e => {
    if (e.detail) cacheAuthProvider(e.detail);
  });

  // ── Device identifier ─────────────────────────────────────────────────────

  function setCurrentDeviceIdentifier(identifier) {
    currentDeviceIdentifier = identifier;
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  window.ytcvAccountPanel = {
    open,
    close,
    setCurrentDeviceIdentifier
  };
})();
