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
  let activeTab = 'password';
  let currentDeviceIdentifier = null;

  // ── Public API ────────────────────────────────────────────────────────────

  function open(tab) {
    if (!overlay) build();
    activeTab = tab || 'password';
    overlay.hidden = false;
    document.body.classList.add('account-panel-open');
    switchTab(activeTab);
    loadTab(activeTab);
  }

  function close() {
    if (!overlay) return;
    overlay.hidden = true;
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
    overlay.hidden = true;

    overlay.innerHTML = `
      <div class="account-panel__card">
        <header class="account-panel__header">
          <h2 id="ap-title" class="heading-2" data-i18n="accountPanelTitle">My account</h2>
          <button id="ap-close" class="account-panel__close" type="button" aria-label="${t('close')}">✕</button>
        </header>

        <nav class="account-panel__tabs" role="tablist">
          <button class="account-panel__tab" role="tab" data-tab="password" data-i18n="accountTabPassword">Password</button>
          <button class="account-panel__tab" role="tab" data-tab="passkeys" data-i18n="accountTabPasskeys">Passkeys</button>
          <button class="account-panel__tab" role="tab" data-tab="totp" data-i18n="accountTabTotp">Authenticator</button>
          <button class="account-panel__tab" role="tab" data-tab="devices" data-i18n="accountTabDevices">Devices</button>
          <button class="account-panel__tab" role="tab" data-tab="youtube" data-i18n="accountTabYoutube">YouTube</button>
        </nav>

        <div class="account-panel__body">
          <!-- PASSWORD TAB -->
          <div id="ap-tab-password" class="account-panel__panel" role="tabpanel">
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
              <p id="ap-pw-msg" class="account-panel__msg" hidden></p>
              <button id="ap-pw-submit" class="button" type="submit" data-i18n="accountPasswordSave">Change password</button>
            </form>
          </div>

          <!-- PASSKEYS TAB -->
          <div id="ap-tab-passkeys" class="account-panel__panel" role="tabpanel" hidden>
            <div id="ap-passkeys-list" class="account-panel__list"></div>
            <div class="account-panel__actions">
              <label class="field account-panel__inline-field">
                <input id="ap-passkey-label" class="field__input" type="text" maxlength="64" placeholder="${t('accountPasskeyLabelPlaceholder')}">
              </label>
              <button id="ap-passkey-add" class="button" type="button" data-i18n="accountPasskeyAdd">Add passkey</button>
            </div>
            <p id="ap-passkeys-msg" class="account-panel__msg" hidden></p>
          </div>

          <!-- TOTP TAB -->
          <div id="ap-tab-totp" class="account-panel__panel" role="tabpanel" hidden>
            <div id="ap-totp-status" class="account-panel__totp-status"></div>
          </div>

          <!-- DEVICES TAB -->
          <div id="ap-tab-devices" class="account-panel__panel" role="tabpanel" hidden>
            <div id="ap-devices-list" class="account-panel__list"></div>
            <p id="ap-devices-msg" class="account-panel__msg" hidden></p>
          </div>

          <!-- YOUTUBE TAB -->
          <div id="ap-tab-youtube" class="account-panel__panel" role="tabpanel" hidden>
            <div id="ap-youtube-status" class="account-panel__youtube-status"></div>
          </div>
        </div>
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
      panel.hidden = panel.id !== `ap-tab-${tabName}`;
    });
  }

  function loadTab(tabName) {
    switch (tabName) {
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
      setupBtn.addEventListener('click', () => renderTotpSetupFlow(container));
      actionsEl.appendChild(setupBtn);
    } else {
      const disableBtn = document.createElement('button');
      disableBtn.className = 'button button--ghost';
      disableBtn.textContent = t('accountTotpDisable');
      disableBtn.addEventListener('click', () => renderTotpDisableFlow(container));
      actionsEl.appendChild(disableBtn);

      const regenBtn = document.createElement('button');
      regenBtn.className = 'button button--ghost';
      regenBtn.textContent = t('accountTotpRegenerateRecovery');
      regenBtn.addEventListener('click', () => renderTotpRegenFlow(container));
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
      const { secret, otpauth_url } = resp.data;

      container.innerHTML = `
        <p class="body">${t('accountTotpScanQr')}</p>
        <div id="ap-totp-qr" class="account-panel__qr"></div>
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

      renderQrCode(document.getElementById('ap-totp-qr'), otpauth_url);

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

  function renderQrCode(container, otpauthUrl) {
    if (!container) return;
    // Use a QR code library if available (e.g. qrcode.js), otherwise show text
    if (window.QRCode) {
      new window.QRCode(container, { text: otpauthUrl, width: 180, height: 180 });
    } else {
      const a = document.createElement('a');
      a.href = otpauthUrl;
      a.textContent = otpauthUrl;
      a.className = 'caption';
      a.style.wordBreak = 'break-all';
      container.appendChild(a);
    }
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
