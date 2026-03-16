// Helpers for interpreting server-governed refresh responses.

(() => {
  function getRetryMinutes(payload) {
    const seconds = payload && typeof payload.retry_after_seconds === 'number'
      ? payload.retry_after_seconds
      : 0;
    return Math.max(1, Math.ceil(seconds / 60));
  }

  function getBlockedProgressMessage(t, payload) {
    if (!payload || payload.reason === 'refresh_in_progress') {
      return t('refreshProgressAlreadyRunning');
    }
    return t('refreshProgressCooldown', { minutes: getRetryMinutes(payload) });
  }

  function getBlockedToastMessage(t, payload) {
    if (!payload || payload.reason === 'refresh_in_progress') {
      return t('refreshAlreadyRunning');
    }
    return t('refreshCooldownActive', { minutes: getRetryMinutes(payload) });
  }

  window.ytcvRefreshGovernance = {
    getRetryMinutes,
    getBlockedProgressMessage,
    getBlockedToastMessage
  };
})();
