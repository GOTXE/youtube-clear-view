// Embedded player overlay for desktop/tablet and TV modes.
// Integrates YouTube IFrame Player API for progress tracking,
// auto-mark watched at 75%, and playback resume.

(() => {
  let initialized = false;
  let ui = null;
  let opener = null;
  let focusables = [];
  let currentVideo = null;
  let currentChannel = null;
  let currentWatched = false;
  let currentMarkWatched = null;

  // YouTube IFrame API state
  let ytApiLoaded = false;
  let ytApiLoading = false;
  let ytPlayer = null;
  let apiAvailable = false;
  let progressInterval = null;
  let autoMarked = false;
  let playbackStarted = false;
  let lastKnownPosition = 0;
  let lastKnownDuration = 0;
  let saveCounter = 0;
  let confirmVisible = false;
  let resumeSeconds = 0;

  const PROGRESS_POLL_MS = 5000;
  const AUTO_SAVE_EVERY_N_POLLS = 6; // ~30s at 5s interval
  const AUTO_MARK_RATIO = 0.75;
  const YT_API_TIMEOUT_MS = 4000;

  const t = (key, vars) => (
    window.ytcvI18n && typeof window.ytcvI18n.t === 'function'
      ? window.ytcvI18n.t(key, vars)
      : key
  );

  function getCurrentMode() {
    return document.documentElement.dataset.mode || 'desktop_tablet';
  }

  function supportsEmbeddedPlayback(mode = getCurrentMode()) {
    return mode === 'desktop_tablet' || mode === 'tv';
  }

  function getFocusableElements() {
    if (!ui || !ui.dialog) {
      return [];
    }
    return Array.from(ui.dialog.querySelectorAll('button:not([hidden]):not([disabled]), [href], iframe, [tabindex]:not([tabindex="-1"])'));
  }

  function formatMeta(video, channel) {
    const parts = [];
    if (channel && channel.title) {
      parts.push(channel.title);
    }
    if (typeof window.formatDate === 'function' && video && video.published_at) {
      const value = window.formatDate(video.published_at);
      if (value) {
        parts.push(value);
      }
    }
    if (typeof window.formatDuration === 'function' && video && typeof video.duration === 'number') {
      const value = window.formatDuration(video.duration);
      if (value) {
        parts.push(value);
      }
    }
    return parts.join(' \u2022 ');
  }

  function getEmbedUrl(videoId, startSeconds) {
    if (!videoId) {
      return 'about:blank';
    }
    let url = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}?autoplay=1&rel=0&playsinline=1&modestbranding=1&enablejsapi=1&origin=${encodeURIComponent(window.location.origin)}`;
    if (startSeconds && startSeconds > 0) {
      url += `&start=${Math.floor(startSeconds)}`;
    }
    return url;
  }

  // ── YouTube IFrame Player API ─────────────────────────────────────

  function loadYTApi() {
    if (ytApiLoaded || ytApiLoading) {
      return;
    }
    ytApiLoading = true;

    const existing = document.getElementById('yt-iframe-api');
    if (existing) {
      ytApiLoading = false;
      if (window.YT && window.YT.Player) {
        ytApiLoaded = true;
        apiAvailable = true;
      }
      return;
    }

    const script = document.createElement('script');
    script.id = 'yt-iframe-api';
    script.src = 'https://www.youtube.com/iframe_api';

    const prevCallback = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      ytApiLoaded = true;
      ytApiLoading = false;
      apiAvailable = true;
      if (typeof prevCallback === 'function') {
        prevCallback();
      }
      tryCreatePlayer();
    };

    script.onerror = () => {
      ytApiLoading = false;
      apiAvailable = false;
    };

    document.head.appendChild(script);

    // Timeout fallback
    setTimeout(() => {
      if (!ytApiLoaded) {
        ytApiLoading = false;
        apiAvailable = false;
      }
    }, YT_API_TIMEOUT_MS);
  }

  function tryCreatePlayer() {
    if (!apiAvailable || !window.YT || !window.YT.Player) {
      return;
    }
    if (ytPlayer) {
      return;
    }
    if (!ui || !ui.frame || ui.root.hidden) {
      return;
    }

    try {
      ytPlayer = new window.YT.Player('player-overlay-frame', {
        events: {
          onReady: onPlayerReady,
          onStateChange: onPlayerStateChange
        }
      });
    } catch (_err) {
      apiAvailable = false;
    }
  }

  function onPlayerReady() {
    // If resuming, seek to saved position
    if (resumeSeconds > 0 && ytPlayer && typeof ytPlayer.seekTo === 'function') {
      ytPlayer.seekTo(resumeSeconds, true);
    }
  }

  function onPlayerStateChange(event) {
    if (!event || typeof event.data === 'undefined') {
      return;
    }

    const YT = window.YT;
    if (!YT || !YT.PlayerState) {
      return;
    }

    if (event.data === YT.PlayerState.PLAYING) {
      playbackStarted = true;
      startProgressTracking();
    } else if (event.data === YT.PlayerState.PAUSED) {
      stopProgressTracking();
      updateLastPosition();
    } else if (event.data === YT.PlayerState.ENDED) {
      stopProgressTracking();
      if (!autoMarked && !currentWatched) {
        autoMarked = true;
        handleMarkWatched();
      }
    }
  }

  // ── Progress tracking ─────────────────────────────────────────────

  function startProgressTracking() {
    if (!apiAvailable || !ytPlayer) {
      return;
    }
    stopProgressTracking();
    saveCounter = 0;
    progressInterval = setInterval(checkProgress, PROGRESS_POLL_MS);
  }

  function stopProgressTracking() {
    if (progressInterval) {
      clearInterval(progressInterval);
      progressInterval = null;
    }
  }

  function updateLastPosition() {
    if (!ytPlayer || typeof ytPlayer.getCurrentTime !== 'function') {
      return;
    }
    try {
      lastKnownPosition = ytPlayer.getCurrentTime() || 0;
      lastKnownDuration = ytPlayer.getDuration() || 0;
    } catch (_err) {
      // Player may be destroyed
    }
  }

  function checkProgress() {
    updateLastPosition();

    if (lastKnownDuration <= 0) {
      return;
    }

    const ratio = lastKnownPosition / lastKnownDuration;

    // Auto-mark at 75%
    if (ratio >= AUTO_MARK_RATIO && !autoMarked && !currentWatched) {
      autoMarked = true;
      handleMarkWatched();
    }

    // Auto-save progress periodically
    saveCounter++;
    if (saveCounter >= AUTO_SAVE_EVERY_N_POLLS && currentVideo && !currentWatched) {
      saveCounter = 0;
      saveProgressToServer();
    }
  }

  function destroyPlayer() {
    stopProgressTracking();
    if (ytPlayer) {
      try {
        if (typeof ytPlayer.destroy === 'function') {
          ytPlayer.destroy();
        }
      } catch (_err) {
        // Ignore errors during cleanup
      }
      ytPlayer = null;
    }
  }

  // ── Server persistence (progress) ─────────────────────────────────

  function getApi() {
    return window.appApiClient || window.ytcvApi || null;
  }

  function saveProgressToServer() {
    const api = getApi();
    if (!api || !currentVideo) {
      return;
    }
    const videoId = currentVideo.id;
    if (!videoId) {
      return;
    }
    api.saveProgress(videoId, Math.floor(lastKnownPosition), Math.floor(lastKnownDuration || 0));
  }

  function clearProgressFromServer() {
    const api = getApi();
    if (!api || !currentVideo) {
      return;
    }
    const videoId = currentVideo.id;
    if (!videoId) {
      return;
    }
    api.clearProgress(videoId);
  }

  // ── Watched button ────────────────────────────────────────────────

  function syncWatchedButton() {
    if (!ui || !ui.markWatched) {
      return;
    }
    ui.markWatched.disabled = currentWatched;
    ui.markWatched.textContent = currentWatched ? t('watchedBadge') : t('markWatched');
  }

  function restoreFocus() {
    if (opener && typeof opener.focus === 'function') {
      opener.focus();
    }
  }

  async function handleMarkWatched() {
    if (currentWatched || typeof currentMarkWatched !== 'function') {
      return;
    }
    await currentMarkWatched();
    currentWatched = true;
    syncWatchedButton();
    clearProgressFromServer();
  }

  function getVideoUrl() {
    if (!currentVideo || !currentVideo.yt_video_id) {
      return null;
    }
    return typeof window.getYTVideoUrl === 'function'
      ? window.getYTVideoUrl(currentVideo.yt_video_id)
      : `https://www.youtube.com/watch?v=${currentVideo.yt_video_id}`;
  }

  function handleOpenOnYouTube() {
    const url = getVideoUrl();
    if (url) {
      window.open(url, '_blank', 'noopener');
    }
  }

  async function handleCopyUrl() {
    const url = getVideoUrl();
    if (!url) {
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      if (ui.copyUrl) {
        const original = ui.copyUrl.textContent;
        ui.copyUrl.textContent = t('copiedToClipboard');
        setTimeout(() => { ui.copyUrl.textContent = original; }, 1500);
      }
    } catch (_err) {
      // Fallback for insecure contexts
      const ta = document.createElement('textarea');
      ta.value = url;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      if (ui.copyUrl) {
        const original = ui.copyUrl.textContent;
        ui.copyUrl.textContent = t('copiedToClipboard');
        setTimeout(() => { ui.copyUrl.textContent = original; }, 1500);
      }
    }
  }

  // ── Confirm dialog ────────────────────────────────────────────────

  function showConfirm() {
    if (ui.confirmMessage) {
      ui.confirmMessage.textContent = t('playerCloseConfirmMessage');
      ui.confirmMessage.hidden = false;
    }
    confirmVisible = true;

    // Pause video while user decides
    if (ytPlayer && typeof ytPlayer.pauseVideo === 'function') {
      try { ytPlayer.pauseVideo(); } catch (_e) { /* noop */ }
    }

    focusables = getFocusableElements();
    if (ui.markWatched) {
      ui.markWatched.focus();
    }
  }

  function hideConfirm() {
    if (ui.confirmMessage) {
      ui.confirmMessage.hidden = true;
    }
    confirmVisible = false;
  }

  function shouldShowConfirm() {
    if (!apiAvailable || !playbackStarted || currentWatched || autoMarked) {
      return false;
    }
    if (lastKnownDuration <= 0) {
      return false;
    }
    const ratio = lastKnownPosition / lastKnownDuration;
    return ratio > 0.01 && ratio < AUTO_MARK_RATIO;
  }

  // ── Close flow ────────────────────────────────────────────────────

  function doClose({ restore = true } = {}) {
    hideConfirm();
    destroyPlayer();

    if (!ui || !ui.root) {
      return;
    }

    ui.root.hidden = true;
    document.body.classList.remove('player-overlay-open');
    document.documentElement.classList.remove('player-overlay-open');
    ui.frame.src = 'about:blank';

    currentVideo = null;
    currentChannel = null;
    currentMarkWatched = null;
    currentWatched = false;
    autoMarked = false;
    playbackStarted = false;
    lastKnownPosition = 0;
    lastKnownDuration = 0;
    saveCounter = 0;
    resumeSeconds = 0;
    focusables = [];

    if (restore) {
      restoreFocus();
    }
  }

  function closeVideoOverlay({ restore = true } = {}) {
    if (!ui || !ui.root || ui.root.hidden) {
      return;
    }

    // If confirm is already visible, treat as "continue later"
    if (confirmVisible) {
      handleContinueLater();
      return;
    }

    // Update position before deciding
    updateLastPosition();

    if (shouldShowConfirm()) {
      showConfirm();
      return;
    }

    doClose({ restore });
  }

  async function handleConfirmWatch() {
    await handleMarkWatched();
    doClose();
    if (typeof window.ytcvReloadCarousels === 'function') {
      window.ytcvReloadCarousels();
    }
  }

  function handleContinueLater() {
    updateLastPosition();
    if (currentVideo) {
      // Save even with position 0 when API is unavailable — marks the video as "watch later"
      saveProgressToServer();
    }
    doClose();
    // Refresh carousels so "Continue watching" section appears
    if (typeof window.ytcvReloadCarousels === 'function') {
      window.ytcvReloadCarousels();
    }
  }

  // ── Keyboard handling ─────────────────────────────────────────────

  function onKeydown(event) {
    if (!ui || ui.root.hidden) {
      return;
    }

    if (event.key === 'Escape') {
      event.preventDefault();
      closeVideoOverlay();
      return;
    }

    if (event.key !== 'Tab') {
      return;
    }

    focusables = getFocusableElements();
    if (!focusables.length) {
      return;
    }

    const first = focusables[0];
    const last = focusables[focusables.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  // ── Init ──────────────────────────────────────────────────────────

  function initPlayerOverlay() {
    ui = {
      root: document.getElementById('player-overlay'),
      backdrop: document.getElementById('player-overlay-backdrop'),
      dialog: document.querySelector('.player-overlay__dialog'),
      eyebrow: document.getElementById('player-overlay-eyebrow'),
      title: document.getElementById('player-overlay-title'),
      meta: document.getElementById('player-overlay-meta'),
      description: document.getElementById('player-overlay-description'),
      frame: document.getElementById('player-overlay-frame'),
      close: document.getElementById('player-overlay-close'),
      markWatched: document.getElementById('player-overlay-mark-watched'),
      openYoutube: document.getElementById('player-overlay-open-youtube'),
      confirmMessage: document.getElementById('player-overlay-confirm-message'),
      confirmLater: document.getElementById('player-overlay-confirm-later'),
      copyUrl: document.getElementById('player-overlay-copy-url')
    };

    if (!ui.root || initialized) {
      return {
        openVideoOverlay,
        closeVideoOverlay,
        supportsEmbeddedPlayback
      };
    }

    if (ui.close) {
      ui.close.addEventListener('click', () => closeVideoOverlay());
    }

    if (ui.backdrop) {
      ui.backdrop.addEventListener('click', () => closeVideoOverlay());
    }

    if (ui.markWatched) {
      ui.markWatched.addEventListener('click', () => {
        if (confirmVisible) {
          handleConfirmWatch();
        } else {
          handleMarkWatched();
        }
      });
    }

    if (ui.openYoutube) {
      ui.openYoutube.addEventListener('click', () => {
        handleOpenOnYouTube();
      });
    }

    if (ui.confirmLater) {
      ui.confirmLater.addEventListener('click', () => {
        handleContinueLater();
      });
    }

    if (ui.copyUrl) {
      ui.copyUrl.addEventListener('click', () => {
        handleCopyUrl();
      });
    }

    document.addEventListener('keydown', onKeydown);
    window.addEventListener('layout-mode:changed', event => {
      if (event.detail && !supportsEmbeddedPlayback(event.detail.mode)) {
        doClose({ restore: false });
      }
    });

    // Start loading YouTube IFrame API early
    loadYTApi();

    initialized = true;
    return {
      openVideoOverlay,
      closeVideoOverlay,
      supportsEmbeddedPlayback
    };
  }

  // ── Open overlay ──────────────────────────────────────────────────

  function openVideoOverlay({ video, channel, watched = false, onMarkWatched = null, origin = null, progress = null } = {}) {
    if (!supportsEmbeddedPlayback() || !ui || !ui.root || !video || !video.yt_video_id) {
      return false;
    }

    opener = origin || document.activeElement;
    currentVideo = video;
    currentChannel = channel || null;
    currentWatched = Boolean(watched);
    currentMarkWatched = onMarkWatched;
    autoMarked = false;
    playbackStarted = false;
    lastKnownPosition = 0;
    lastKnownDuration = 0;
    saveCounter = 0;
    confirmVisible = false;
    resumeSeconds = (progress && typeof progress === 'number' && progress > 0) ? progress : 0;

    ui.eyebrow.textContent = currentChannel && currentChannel.title ? t('nowPlayingChannel', { channel: currentChannel.title }) : t('nowPlaying');
    ui.title.textContent = video.title || t('untitledVideo');
    ui.meta.textContent = formatMeta(video, channel);
    ui.description.textContent = (video.description || '').trim();
    ui.frame.src = getEmbedUrl(video.yt_video_id, resumeSeconds);
    ui.openYoutube.textContent = t('openOnYouTube');
    if (ui.copyUrl) {
      ui.copyUrl.textContent = t('copyVideoUrl');
    }
    if (ui.confirmLater) {
      ui.confirmLater.textContent = t('playerContinueLater');
    }
    syncWatchedButton();
    hideConfirm();

    ui.root.hidden = false;
    document.body.classList.add('player-overlay-open');
    document.documentElement.classList.add('player-overlay-open');

    // Try to create YT player (API may already be loaded)
    ytPlayer = null;
    if (apiAvailable) {
      // Small delay to let iframe load before wrapping with YT.Player
      setTimeout(() => tryCreatePlayer(), 500);
    }

    focusables = getFocusableElements();
    window.setTimeout(() => {
      const target = ui.close || focusables[0];
      if (target && typeof target.focus === 'function') {
        target.focus();
      }
    }, 0);
    return true;
  }

  const overlayApi = initPlayerOverlay();

  window.ytcvPlayerOverlay = {
    ...overlayApi,
    initPlayerOverlay
  };
})();
