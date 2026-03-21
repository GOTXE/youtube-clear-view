// Dedicated manager page for admin operations.

document.addEventListener('DOMContentLoaded', async () => {
  const t = (key, vars) => (
    window.ytcvI18n && typeof window.ytcvI18n.t === 'function'
      ? window.ytcvI18n.t(key, vars)
      : key
  );

  const applyStaticI18n = () => {
    document.querySelectorAll('[data-i18n]').forEach(node => {
      const key = node.getAttribute('data-i18n');
      const translated = t(key);
      if (translated && translated !== key) {
        node.textContent = translated;
      }
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(node => {
      const key = node.getAttribute('data-i18n-placeholder');
      const translated = t(key);
      if (translated && translated !== key) {
        node.setAttribute('placeholder', translated);
      }
    });
  };

  const api = window.appApiClient || new window.APIClient(
    window.APP_CONFIG.API_BASE_URL,
    window.APP_CONFIG.REQUEST_TIMEOUT
  );
  window.appApiClient = api;

  const state = {
    user: null,
    loading: false,
    query: '',
    summary: null,
    users: [],
    runtime: [],
    passwordPolicy: null,
    refreshSchedule: null
  };

  const ui = {
    status: document.getElementById('gestor-status'),
    refreshButton: document.getElementById('gestor-refresh'),
    logoutButtons: [document.getElementById('gestor-header-logout')].filter(Boolean),
    searchInput: document.getElementById('gestor-user-search'),
    searchButton: document.getElementById('gestor-user-search-button'),
    summaryGrid: document.getElementById('gestor-summary-grid'),
    usersBody: document.getElementById('gestor-users-body'),
    security: document.getElementById('gestor-security-content'),
    runtime: document.getElementById('gestor-runtime-content'),
    navLinks: Array.from(document.querySelectorAll('.admin-page__nav-link'))
  };

  function setStatus(message, type = 'info') {
    if (!ui.status) {
      return;
    }
    ui.status.textContent = message || '';
    ui.status.dataset.type = message ? type : '';
  }

  function enforceLightTheme() {
    document.documentElement.setAttribute('data-theme', 'light');
    const appRoot = document.getElementById('app');
    if (appRoot) {
      appRoot.setAttribute('data-theme', 'light');
    }
  }

  function formatDate(value) {
    if (!value) {
      return '—';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return '—';
    }
    return date.toLocaleString();
  }

  function getBrowserTimezone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Madrid';
    } catch (error) {
      return 'Europe/Madrid';
    }
  }

  function buildScheduleOptions(select) {
    if (!select) {
      return;
    }
    select.innerHTML = '';
    for (let hour = 0; hour < 24; hour += 1) {
      const option = document.createElement('option');
      option.value = String(hour);
      option.textContent = `${String(hour).padStart(2, '0')}:00`;
      select.appendChild(option);
    }
  }

  function makeBadge(label, tone = 'neutral') {
    const badge = document.createElement('span');
    badge.className = `admin-page__badge admin-page__badge--${tone}`;
    if (tone === 'google') {
      badge.setAttribute('aria-label', label);
      [
        ['G', 'blue'],
        ['o', 'red'],
        ['o', 'yellow'],
        ['g', 'blue'],
        ['l', 'green'],
        ['e', 'red']
      ].forEach(([letter, color]) => {
        const span = document.createElement('span');
        span.className = `admin-page__badge-letter admin-page__badge-letter--${color}`;
        span.textContent = letter;
        badge.appendChild(span);
      });
      return badge;
    }
    badge.textContent = label;
    return badge;
  }

  function getCurrentAnchor() {
    const hash = window.location.hash || '#summary';
    const clean = hash.replace(/^#/, '') || 'summary';
    return clean;
  }

  function updateNavActiveState() {
    const active = getCurrentAnchor();
    ui.navLinks.forEach(link => {
      link.classList.toggle('is-active', link.dataset.adminAnchor === active);
    });
  }

  function getDeviceIcon(type) {
    switch ((type || '').toLowerCase()) {
      case 'tv':
        return '📺';
      case 'tablet':
        return '📟';
      case 'mobile':
        return '📱';
      case 'desktop':
      default:
        return '🖥️';
    }
  }

  function renderSummary() {
    ui.summaryGrid.innerHTML = '';
    if (!state.summary) {
      return;
    }

    const cards = [
      { label: t('adminSummaryUsersTotal'), value: state.summary.users_total || 0, tone: 'neutral' },
      { label: t('adminSummaryAdmins'), value: state.summary.users_admin || 0, tone: 'blue' },
      { label: t('adminSummaryChannels'), value: state.summary.channels_total || 0, tone: 'neutral' },
      { label: t('adminSummaryDevices'), value: state.summary.devices_total || 0, tone: 'neutral' },
      { label: t('adminSummaryUnclassified'), value: state.summary.channels_unclassified || 0, tone: (state.summary.channels_unclassified || 0) > 0 ? 'amber' : 'green' },
      { label: t('adminSummaryQuotaUsed'), value: `${state.summary.quota_used || 0} / ${state.summary.quota_daily_limit || 0}`, tone: 'blue' }
    ];

    cards.forEach(card => {
      const article = document.createElement('article');
      article.className = `admin-page__metric-card admin-page__metric-card--${card.tone}`;

      const label = document.createElement('p');
      label.className = 'caption admin-page__metric-label';
      label.textContent = card.label;

      const value = document.createElement('p');
      value.className = 'admin-page__metric-value';
      value.textContent = String(card.value);

      article.appendChild(label);
      article.appendChild(value);

      ui.summaryGrid.appendChild(article);
    });
  }

  function getPasswordPolicyHint(option) {
    if (!option || !option.value) {
      return '';
    }
    return t(`adminPasswordPolicyHint_${option.value}`, {
      min: option.min_length || 0
    });
  }

  async function toggleUser(user) {
    if (user.is_active) {
      const confirmed = window.confirm(t('adminDisableUserConfirm', { user: user.display_name || user.username || `#${user.id}` }));
      if (!confirmed) {
        return;
      }
    }
    const response = user.is_active
      ? await api.disableAdminUser(user.id)
      : await api.enableAdminUser(user.id);
    if (!response.ok || !response.data) {
      setStatus(response.error || t('unableUpdateAdminUser'), 'error');
      return;
    }
    setStatus(t('adminUserUpdated'), 'success');
    await refresh(state.query);
  }

  async function resetUserPassword(user, temporaryPassword) {
    const response = await api.resetAdminUserPassword(user.id, temporaryPassword);
    if (!response.ok || !response.data) {
      setStatus(response.error || t('unableResetAdminPassword'), 'error');
      return;
    }
    setStatus(t('adminPasswordResetSuccess'), 'success');
    await refresh(state.query);
  }

  function renderUsers() {
    ui.usersBody.innerHTML = '';
    if (!state.users.length) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 9;
      cell.className = 'admin-page__table-empty';
      cell.textContent = t('adminNoUsers');
      row.appendChild(cell);
      ui.usersBody.appendChild(row);
      return;
    }

    state.users.forEach(user => {
      const row = document.createElement('tr');

      const authCell = document.createElement('td');
      const authTone = user.auth_provider === 'google' ? 'google' : 'neutral';
      authCell.appendChild(makeBadge(user.auth_provider || '—', authTone));

      const adminCell = document.createElement('td');
      adminCell.appendChild(makeBadge(user.is_admin ? t('yes') : t('no'), user.is_admin ? 'blue' : 'neutral'));

      const totpCell = document.createElement('td');
      totpCell.appendChild(makeBadge(user.totp_enabled ? t('yes') : t('no'), user.totp_enabled ? 'green' : 'neutral'));

      const activeCell = document.createElement('td');
      activeCell.appendChild(makeBadge(user.is_active ? t('yes') : t('no'), user.is_active ? 'green' : 'amber'));

      const actionsCell = document.createElement('td');
      const actions = document.createElement('div');
      actions.className = 'admin-page__table-actions';

      const toggleButton = document.createElement('button');
      toggleButton.type = 'button';
      toggleButton.className = `admin-page__mini-btn ${user.is_active ? 'admin-page__mini-btn--danger' : 'admin-page__mini-btn--ghost'}`;
      toggleButton.textContent = user.is_active ? t('adminDisableUser') : t('adminEnableUser');
      toggleButton.addEventListener('click', async () => {
        toggleButton.disabled = true;
        await toggleUser(user);
        toggleButton.disabled = false;
      });

      const tempPasswordInput = document.createElement('input');
      tempPasswordInput.className = 'field__input admin-page__table-input';
      tempPasswordInput.type = 'text';
      tempPasswordInput.placeholder = t('adminTemporaryPasswordPlaceholder');

      const resetButton = document.createElement('button');
      resetButton.type = 'button';
      resetButton.className = 'admin-page__mini-btn admin-page__mini-btn--primary';
      resetButton.textContent = t('adminResetPassword');
      resetButton.addEventListener('click', async () => {
        const temporaryPassword = tempPasswordInput.value.trim();
        if (!temporaryPassword) {
          setStatus(t('adminTemporaryPasswordRequired'), 'error');
          tempPasswordInput.focus();
          return;
        }
        resetButton.disabled = true;
        await resetUserPassword(user, temporaryPassword);
        resetButton.disabled = false;
      });

      actions.appendChild(toggleButton);
      actions.appendChild(tempPasswordInput);
      actions.appendChild(resetButton);
      actionsCell.appendChild(actions);

      [
        user.username || '—',
        user.display_name || '—',
        authCell,
        adminCell,
        totpCell,
        activeCell,
        formatDate(user.last_activity_at || user.session_created_at),
        String(user.device_count || 0),
        actionsCell
      ].forEach(value => {
        const cell = document.createElement('td');
        if (value instanceof HTMLElement) {
          cell.appendChild(value);
        } else {
          cell.textContent = value;
        }
        row.appendChild(cell);
      });

      ui.usersBody.appendChild(row);
    });
  }

  function renderSecurity() {
    ui.security.innerHTML = '';

    const policyCard = document.createElement('article');
    policyCard.className = 'admin-page__panel-card';
    policyCard.innerHTML = `
      <p class="caption">${t('adminPasswordPolicyDescription')}</p>
    `;

    const controls = document.createElement('div');
    controls.className = 'admin-page__inline-controls';

    const policySelect = document.createElement('select');
    policySelect.className = 'field__input';
    (state.passwordPolicy.options || []).forEach(option => {
      const node = document.createElement('option');
      node.value = option.value;
      node.textContent = t(`adminPasswordPolicyLabel_${option.value}`);
      node.selected = option.value === state.passwordPolicy.password_policy;
      policySelect.appendChild(node);
    });

    const saveButton = document.createElement('button');
    saveButton.type = 'button';
    saveButton.className = 'admin-page__mini-btn admin-page__mini-btn--primary';
    saveButton.textContent = t('saveSecuritySettings');
    saveButton.addEventListener('click', async () => {
      saveButton.disabled = true;
      const response = await api.updateAdminPasswordPolicy(policySelect.value);
      saveButton.disabled = false;
      if (!response.ok || !response.data) {
        setStatus(response.error || t('unableSaveAdminPasswordPolicy'), 'error');
        return;
      }
      state.passwordPolicy = response.data;
      renderSecurity();
      setStatus(t('adminPasswordPolicyUpdated'), 'success');
    });

    controls.appendChild(policySelect);
    controls.appendChild(saveButton);
    policyCard.appendChild(controls);

    const selectedOption = (state.passwordPolicy.options || []).find(
      option => option.value === state.passwordPolicy.password_policy
    );

    const guidance = document.createElement('div');
    guidance.className = 'admin-page__policy-guidance';

    const item = document.createElement('div');
    item.className = 'admin-page__policy-item is-active';

    const title = document.createElement('p');
    title.className = 'admin-page__policy-title';
    title.textContent = selectedOption ? t(`adminPasswordPolicyLabel_${selectedOption.value}`) : '—';

    const hint = document.createElement('p');
    hint.className = 'caption admin-page__policy-hint';
    hint.textContent = getPasswordPolicyHint(selectedOption);

    item.appendChild(title);
    item.appendChild(hint);
    guidance.appendChild(item);
    policyCard.appendChild(guidance);

    policySelect.addEventListener('change', () => {
      const nextOption = (state.passwordPolicy.options || []).find(option => option.value === policySelect.value);
      title.textContent = nextOption ? t(`adminPasswordPolicyLabel_${nextOption.value}`) : '—';
      hint.textContent = getPasswordPolicyHint(nextOption);
    });

    ui.security.appendChild(policyCard);

    const scheduleCard = document.createElement('article');
    scheduleCard.className = 'admin-page__panel-card';
    scheduleCard.innerHTML = `
      <h4 class="heading-3">${t('adminRefreshScheduleTitle')}</h4>
      <p class="caption">${t('adminRefreshScheduleDescription')}</p>
    `;

    const scheduleControls = document.createElement('div');
    scheduleControls.className = 'admin-page__stack';

    const scheduleGrid = document.createElement('div');
    scheduleGrid.className = 'schedule-grid';
    scheduleGrid.setAttribute('role', 'group');
    scheduleGrid.setAttribute('aria-label', t('adminRefreshScheduleTitle'));

    const selectedHours = Array.isArray(state.refreshSchedule?.schedule_hours)
      ? state.refreshSchedule.schedule_hours
      : [7, 12, 17, 21];

    const hourSelects = Array.from({ length: 4 }, (_, index) => {
      const field = document.createElement('label');
      field.className = 'schedule-field';

      const label = document.createElement('span');
      label.className = 'caption';
      label.textContent = t('scheduleSlot', { index: index + 1 });

      const select = document.createElement('select');
      select.className = 'field__input field__input--compact';
      buildScheduleOptions(select);
      select.value = String(selectedHours[index] ?? selectedHours[selectedHours.length - 1] ?? 0);

      field.appendChild(label);
      field.appendChild(select);
      scheduleGrid.appendChild(field);
      return select;
    });

    const timezoneField = document.createElement('label');
    timezoneField.className = 'schedule-field';

    const timezoneLabel = document.createElement('span');
    timezoneLabel.className = 'caption';
    timezoneLabel.textContent = t('timezone');

    const timezoneInput = document.createElement('input');
    timezoneInput.className = 'field__input field__input--compact';
    timezoneInput.type = 'text';
    timezoneInput.value = state.refreshSchedule?.timezone || getBrowserTimezone();
    timezoneInput.placeholder = 'Europe/Madrid';

    timezoneField.appendChild(timezoneLabel);
    timezoneField.appendChild(timezoneInput);

    const scheduleMeta = document.createElement('div');
    scheduleMeta.className = 'admin-page__policy-guidance';

    const scheduleInfo = document.createElement('div');
    scheduleInfo.className = 'admin-page__policy-item is-active';

    const scheduleInfoTitle = document.createElement('p');
    scheduleInfoTitle.className = 'admin-page__policy-title';
    scheduleInfoTitle.textContent = t('adminRefreshScheduleCurrent');

    const scheduleInfoHint = document.createElement('p');
    scheduleInfoHint.className = 'caption admin-page__policy-hint';
    scheduleInfoHint.textContent = state.refreshSchedule?.last_run_at
      ? t('adminRefreshScheduleLastRun', { value: formatDate(state.refreshSchedule.last_run_at) })
      : t('adminRefreshScheduleNotRunYet');

    scheduleInfo.appendChild(scheduleInfoTitle);
    scheduleInfo.appendChild(scheduleInfoHint);
    scheduleMeta.appendChild(scheduleInfo);

    const scheduleActions = document.createElement('div');
    scheduleActions.className = 'admin-page__inline-controls';

    const scheduleSaveButton = document.createElement('button');
    scheduleSaveButton.type = 'button';
    scheduleSaveButton.className = 'admin-page__mini-btn admin-page__mini-btn--primary';
    scheduleSaveButton.textContent = t('saveScheduleSettings');
    scheduleSaveButton.addEventListener('click', async () => {
      const nextHours = hourSelects
        .map(select => Number(select.value))
        .filter(hour => Number.isInteger(hour))
        .slice(0, 4);
      const timezone = timezoneInput.value.trim() || getBrowserTimezone();
      scheduleSaveButton.disabled = true;
      const response = await api.updateAdminRefreshSchedule(nextHours, timezone);
      scheduleSaveButton.disabled = false;
      if (!response.ok || !response.data) {
        setStatus(response.error || t('unableSaveAdminRefreshSchedule'), 'error');
        return;
      }
      state.refreshSchedule = response.data;
      renderSecurity();
      setStatus(t('adminRefreshScheduleUpdated'), 'success');
    });

    scheduleGrid.appendChild(timezoneField);
    scheduleActions.appendChild(scheduleSaveButton);
    scheduleControls.appendChild(scheduleGrid);
    scheduleControls.appendChild(scheduleMeta);
    scheduleControls.appendChild(scheduleActions);
    scheduleCard.appendChild(scheduleControls);

    ui.security.appendChild(scheduleCard);
  }

  function renderRuntime() {
    ui.runtime.innerHTML = '';
    if (!state.runtime.length) {
      const empty = document.createElement('article');
      empty.className = 'admin-page__panel-card';
      empty.innerHTML = `<p class="caption">${t('adminNoRuntimeUsers')}</p>`;
      ui.runtime.appendChild(empty);
      return;
    }

    state.runtime.forEach(user => {
      const card = document.createElement('article');
      card.className = 'admin-page__panel-card admin-page__runtime-card';

      const header = document.createElement('div');
      header.className = 'admin-page__runtime-header';

      const copy = document.createElement('div');
      copy.className = 'admin-page__runtime-copy';

      const title = document.createElement('h4');
      title.className = 'heading-3';
      title.textContent = user.display_name || user.username || user.email || `#${user.id}`;

      const summary = document.createElement('p');
      summary.className = 'caption';
      summary.textContent = t('adminRuntimeUserSummary', {
        devices: user.device_count || 0,
        session: user.has_active_session ? t('yes') : t('no')
      });

      const meta = document.createElement('div');
      meta.className = 'admin-page__runtime-meta';
      meta.appendChild(makeBadge(user.has_active_session ? t('adminRuntimeSessionOpen') : t('adminRuntimeSessionClosed'), user.has_active_session ? 'green' : 'neutral'));
      meta.appendChild(makeBadge(`${user.device_count || 0} ${t('adminTableDevices').toLowerCase()}`, 'blue'));

      copy.appendChild(title);
      copy.appendChild(summary);
      header.appendChild(copy);
      header.appendChild(meta);
      card.appendChild(header);

      const devices = Array.isArray(user.devices) ? user.devices : [];
      if (devices.length) {
        const list = document.createElement('div');
        list.className = 'admin-page__device-grid';
        devices.forEach(device => {
          const item = document.createElement('div');
          item.className = 'admin-page__device-card';
          item.innerHTML = `
            <div class="admin-page__device-icon" aria-hidden="true">${getDeviceIcon(device.device_type)}</div>
            <div class="admin-page__device-copy">
              <p class="admin-page__device-name">${device.display_name || device.device_identifier}</p>
              <p class="caption admin-page__device-meta">${t(`deviceType${(device.device_type || 'desktop').replace(/^./, c => c.toUpperCase())}`) || device.device_type} · ${device.frontend_mode || '—'}</p>
            </div>
          `;
          list.appendChild(item);
        });
        card.appendChild(list);
      }

      ui.runtime.appendChild(card);
    });
  }

  function renderAll() {
    updateNavActiveState();
    renderSummary();
    renderUsers();
    renderSecurity();
    renderRuntime();
  }

  async function refresh(query = state.query) {
    if (state.loading) {
      return;
    }

    state.loading = true;
    state.query = query;
    setStatus(t('adminPageLoading'));

    const [summaryResponse, usersResponse, runtimeResponse, passwordPolicyResponse, refreshScheduleResponse] = await Promise.all([
      api.getAdminSummary(),
      api.getAdminUsers(query),
      api.getAdminRuntimeState(),
      api.getAdminPasswordPolicy(),
      api.getAdminRefreshSchedule()
    ]);

    state.loading = false;

    if (
      !summaryResponse.ok
      || !usersResponse.ok
      || !runtimeResponse.ok
      || !passwordPolicyResponse.ok
      || !refreshScheduleResponse.ok
    ) {
      setStatus(t('adminPageLoadError'), 'error');
      return;
    }

    state.summary = summaryResponse.data;
    state.users = Array.isArray(usersResponse.data && usersResponse.data.users) ? usersResponse.data.users : [];
    state.runtime = Array.isArray(runtimeResponse.data && runtimeResponse.data.users) ? runtimeResponse.data.users : [];
    state.passwordPolicy = passwordPolicyResponse.data || {};
    state.refreshSchedule = refreshScheduleResponse.data || {};
    renderAll();
    setStatus('');
  }

  function showLogin(options = {}) {
    if (window.ytcvLoginPage) {
      window.ytcvLoginPage.show(options);
    }
  }

  function hideLogin() {
    if (window.ytcvLoginPage) {
      window.ytcvLoginPage.hide();
    }
  }

  async function bootstrapPage() {
    if (typeof window.initAuth !== 'function') {
      return;
    }

    await (window.ytcvI18nReady || Promise.resolve());
    applyStaticI18n();
    enforceLightTheme();
    state.user = await window.initAuth();
    const authStatus = window.ytcvLoginPage ? window.ytcvLoginPage.checkAuthStatusParam() : null;

    if (!state.user) {
      const options = authStatus === 'needs_setup' ? { wizard: true } : {};
      showLogin(options);
      return;
    }

    if (!state.user.is_admin) {
      window.location.assign('/');
      return;
    }

    enforceLightTheme();
    hideLogin();
    if (window.ytcvLoginPage && typeof window.ytcvLoginPage.releaseAuthGate === 'function') {
      window.ytcvLoginPage.releaseAuthGate();
    }
    await refresh();
  }

  ui.refreshButton.addEventListener('click', async () => {
    await refresh();
  });

  ui.logoutButtons.forEach(button => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      await api.logout();
      window.location.assign('/');
    });
  });

  ui.searchButton.addEventListener('click', async () => {
    await refresh(ui.searchInput.value.trim());
  });

  ui.searchInput.addEventListener('keydown', async event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      await refresh(ui.searchInput.value.trim());
    }
  });

  ui.navLinks.forEach(link => {
    link.addEventListener('click', event => {
      const targetId = link.getAttribute('href');
      if (!targetId || !targetId.startsWith('#')) {
        return;
      }
      event.preventDefault();
      const section = document.querySelector(targetId);
      if (section) {
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      window.history.replaceState({}, document.title, `${window.location.pathname}${targetId}`);
      window.setTimeout(updateNavActiveState, 0);
    });
  });

  window.addEventListener('auth:changed', async event => {
    const user = event.detail ? event.detail.user : null;
    state.user = user;
    if (!user) {
      showLogin();
      return;
    }
    if (!user.is_admin) {
      window.location.assign('/');
      return;
    }
    enforceLightTheme();
    hideLogin();
    await refresh();
  });

  window.addEventListener('auth-required', () => {
    showLogin();
  });

  window.addEventListener('hashchange', updateNavActiveState);

  enforceLightTheme();
  await bootstrapPage();
});
