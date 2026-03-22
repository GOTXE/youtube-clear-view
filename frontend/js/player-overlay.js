// Embedded player overlay for desktop/tablet and TV modes.
// Integrates YouTube IFrame Player API for progress tracking,
// auto-mark watched at 75%, and playback resume.

(() => {
  const USE_EMBED_ONLY = true;
  let initialized = false;
  let ui = null;
  let opener = null;
  let focusables = [];
  let currentVideo = null;
  let currentChannel = null;
  let currentWatched = false;
  let currentMarkWatched = null;
  let currentHasSavedProgress = false;
  let currentInContinueWatching = false;
  let sessionWatchStartedAt = 0;

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
  let confirmVisible = false;
  let confirmMode = null;
  let confirmBusy = false;
  let resumeSeconds = 0;
  let playerInitTimer = null;
  let frameInstanceCounter = 0;

  const PROGRESS_POLL_MS = 5000;
  const AUTO_MARK_RATIO = 0.75;
  const CONTINUE_WATCHING_PROMPT_RATIO = 1 / 3;
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

  function getEmbedUrl(videoId, startSeconds, frameNonce = 0) {
    if (!videoId) {
      return 'about:blank';
    }
    let url = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}?autoplay=1&rel=0&playsinline=1&modestbranding=1`;
    if (!USE_EMBED_ONLY) {
      url += `&enablejsapi=1&origin=${encodeURIComponent(window.location.origin)}`;
    }
    if (startSeconds && startSeconds > 0) {
      url += `&start=${Math.floor(startSeconds)}`;
    }
    if (frameNonce > 0) {
      url += `&ytcv_frame=${frameNonce}`;
    }
    url += `&vq=${encodeURIComponent(getPreferredQualityHint())}`;
    return url;
  }

  function getPreferredQualityHint() {
    const width = Math.max(
      window.innerWidth || 0,
      window.screen && window.screen.width ? window.screen.width : 0
    );
    const height = Math.max(
      window.innerHeight || 0,
      window.screen && window.screen.height ? window.screen.height : 0
    );
    const effectiveWidth = width * (window.devicePixelRatio || 1);
    const effectiveHeight = height * (window.devicePixelRatio || 1);

    if (effectiveWidth >= 3800 || effectiveHeight >= 2100) {
      return 'highres';
    }
    if (effectiveWidth >= 2500 || effectiveHeight >= 1400) {
      return 'hd1440';
    }
    if (effectiveWidth >= 1900 || effectiveHeight >= 1060) {
      return 'hd1080';
    }
    if (effectiveWidth >= 1260 || effectiveHeight >= 700) {
      return 'hd720';
    }
    if (effectiveWidth >= 850 || effectiveHeight >= 470) {
      return 'large';
    }
    return 'medium';
  }

  // ── YouTube IFrame Player API ─────────────────────────────────────

  function loadYTApi() {
    if (USE_EMBED_ONLY) {
      apiAvailable = false;
      ytApiLoaded = false;
      ytApiLoading = false;
      return;
    }
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
    if (USE_EMBED_ONLY) {
      return;
    }
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
      ytPlayer = new window.YT.Player(ui.frame.id, {
        events: {
          onReady: onPlayerReady,
          onStateChange: onPlayerStateChange
        }
      });
    } catch (_err) {
      apiAvailable = false;
    }
  }

  function clearPlayerInitTimer() {
    if (playerInitTimer) {
      window.clearTimeout(playerInitTimer);
      playerInitTimer = null;
    }
  }

  function schedulePlayerInit() {
    if (USE_EMBED_ONLY) {
      return;
    }
    clearPlayerInitTimer();
    if (!ui || !ui.frame) {
      return;
    }

    const targetFrame = ui.frame;
    const init = () => {
      if (!ui || ui.frame !== targetFrame) {
        return;
      }
      clearPlayerInitTimer();
      tryCreatePlayer();
    };

    targetFrame.addEventListener('load', init, { once: true });
    playerInitTimer = window.setTimeout(init, 1200);
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
  }

  function destroyPlayer() {
    stopProgressTracking();
    clearPlayerInitTimer();
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

  function buildFreshFrame() {
    const freshFrame = document.createElement('iframe');
    freshFrame.className = 'player-overlay__frame';
    freshFrame.title = 'Embedded video player';
    freshFrame.src = 'about:blank';
    freshFrame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    freshFrame.setAttribute('allowfullscreen', '');
    return freshFrame;
  }

  function resetFrameElement() {
    if (!ui || !ui.frame || !ui.frame.parentElement) {
      return;
    }

    frameInstanceCounter += 1;
    const freshFrame = buildFreshFrame();
    freshFrame.id = `player-overlay-frame-${frameInstanceCounter}`;
    ui.frame.replaceWith(freshFrame);
    ui.frame = freshFrame;
  }

  // ── Server persistence (progress) ─────────────────────────────────

  function getApi() {
    return window.appApiClient || window.ytcvApi || null;
  }

  function saveProgressToServer() {
    const api = getApi();
    if (!api || !currentVideo) {
      return Promise.resolve();
    }
    const videoId = currentVideo.id;
    if (!videoId) {
      return Promise.resolve();
    }
    return api.saveProgress(videoId, Math.floor(lastKnownPosition), Math.floor(lastKnownDuration || 0));
  }

  function saveProgressPosition(positionSeconds, durationSeconds = null, options = {}) {
    if (!currentVideo || !currentVideo.id) {
      return Promise.resolve();
    }
    return saveProgressForVideo(
      currentVideo.id,
      positionSeconds,
      durationSeconds || currentVideo.duration || lastKnownDuration || 0,
      options
    );
  }

  function saveProgressForVideo(videoId, positionSeconds, durationSeconds = null, options = {}) {
    const api = getApi();
    if (!api || !videoId) {
      return Promise.resolve();
    }
    return api.saveProgress(
      videoId,
      Math.floor(Math.max(positionSeconds || 0, 0)),
      Math.floor(durationSeconds || 0),
      options
    );
  }

  function clearProgressFromServer() {
    const api = getApi();
    if (!api || !currentVideo) {
      return Promise.resolve();
    }
    const videoId = currentVideo.id;
    if (!videoId) {
      return Promise.resolve();
    }
    return api.clearProgress(videoId);
  }

  function markVideoWatchedForCurrentUser(videoId) {
    const api = getApi();
    if (!api || !videoId) {
      return Promise.resolve();
    }
    const deviceId = typeof window.getDeviceId === 'function' ? window.getDeviceId() : null;
    return api.markAsWatched(videoId, deviceId || undefined);
  }

  async function finalizeWatchedTransition(videoId, options = {}) {
    const shouldRefreshWatched = options.refreshWatched !== false;
    if (typeof window.ytcvHandleVideoMarkedWatched === 'function') {
      await window.ytcvHandleVideoMarkedWatched(videoId, { refreshWatched: shouldRefreshWatched });
      return;
    }
    if (typeof window.ytcvReloadCarousels === 'function') {
      await window.ytcvReloadCarousels({ preserveDOM: false });
    }
  }

  // ── Watched button ────────────────────────────────────────────────

  function syncWatchedButton() {
    if (!ui || !ui.markWatched) {
      return;
    }
    ui.markWatched.disabled = currentWatched;
    ui.markWatched.textContent = currentWatched ? t('watchedBadge') : t('markWatched');
  }

  function syncProgressButtons() {
    if (!ui) {
      return;
    }
    if (ui.markWatched) {
      ui.markWatched.disabled = currentWatched || confirmBusy;
    }
    if (ui.saveForLater) {
      ui.saveForLater.hidden = currentInContinueWatching || currentWatched || confirmVisible;
      ui.saveForLater.disabled = confirmBusy;
      ui.saveForLater.textContent = t('saveForLater');
    }
    if (ui.removeProgress) {
      ui.removeProgress.hidden = !currentInContinueWatching || currentWatched || confirmVisible;
      ui.removeProgress.disabled = confirmBusy;
      ui.removeProgress.textContent = t('removeFromContinueWatching');
    }
    if (ui.confirmLater) {
      ui.confirmLater.hidden = !confirmVisible;
      ui.confirmLater.disabled = confirmBusy;
    }
    if (ui.copyUrl) {
      ui.copyUrl.hidden = confirmVisible;
    }
    if (ui.openYoutube) {
      ui.openYoutube.hidden = confirmVisible;
    }
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
    currentHasSavedProgress = false;
    currentInContinueWatching = false;
    syncWatchedButton();
    syncProgressButtons();
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

  function showConfirmAddToContinueWatching() {
    if (ui.confirmMessage) {
      ui.confirmMessage.textContent = t('playerSaveToContinueWatchingMessage');
      ui.confirmMessage.hidden = false;
    }
    confirmVisible = true;
    confirmMode = 'continue-watching';

    // Pause video while user decides
    if (ytPlayer && typeof ytPlayer.pauseVideo === 'function') {
      try { ytPlayer.pauseVideo(); } catch (_e) { /* noop */ }
    }

    if (ui.markWatched) {
      ui.markWatched.textContent = t('addToContinueWatching');
    }
    if (ui.confirmLater) {
      ui.confirmLater.textContent = t('skipContinueWatching');
    }
    syncProgressButtons();

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
    confirmMode = null;
    confirmBusy = false;
    syncWatchedButton();
    syncProgressButtons();
  }

  function setConfirmBusy(isBusy, action = null) {
    confirmBusy = Boolean(isBusy);
    if (ui.markWatched) {
      ui.markWatched.textContent = confirmMode === 'continue-watching'
        ? (confirmBusy && action === 'add'
            ? t('savingContinueWatching')
            : t('addToContinueWatching'))
        : (currentWatched ? t('watchedBadge') : t('markWatched'));
    }
    if (ui.confirmLater && confirmMode === 'continue-watching') {
      ui.confirmLater.textContent = confirmBusy && action === 'skip'
        ? t('savingContinueWatching')
        : t('skipContinueWatching');
    }
    syncProgressButtons();
  }

  function estimateProgressState() {
    const duration = currentVideo && typeof currentVideo.duration === 'number'
      ? currentVideo.duration
      : lastKnownDuration;
    const elapsedSeconds = sessionWatchStartedAt
      ? Math.max(0, Math.floor((Date.now() - sessionWatchStartedAt) / 1000))
      : 0;
    const estimatedPosition = Math.min(
      Math.max(resumeSeconds + elapsedSeconds, 0),
      duration || Math.max(resumeSeconds + elapsedSeconds, 0)
    );
    return {
      duration: duration || 0,
      position: estimatedPosition,
      ratio: duration > 0 ? (estimatedPosition / duration) : 0
    };
  }

  function shouldOfferContinueWatching() {
    if (currentHasSavedProgress || currentInContinueWatching || currentWatched || autoMarked) {
      return false;
    }
    const { duration, ratio } = estimateProgressState();
    if (duration <= 0) {
      return false;
    }
    return ratio >= CONTINUE_WATCHING_PROMPT_RATIO && ratio < AUTO_MARK_RATIO;
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
    resetFrameElement();

    currentVideo = null;
    currentChannel = null;
    currentMarkWatched = null;
    currentWatched = false;
    currentHasSavedProgress = false;
    currentInContinueWatching = false;
    autoMarked = false;
    playbackStarted = false;
    lastKnownPosition = 0;
    lastKnownDuration = 0;
    resumeSeconds = 0;
    sessionWatchStartedAt = 0;
    focusables = [];

    if (restore) {
      restoreFocus();
    }
  }

  async function closeVideoOverlay({ restore = true, immediate = false } = {}) {
    if (!ui || !ui.root || ui.root.hidden) {
      return;
    }

    // If confirm is already visible, treat as "continue later"
    if (confirmVisible) {
      await skipContinueWatching();
      return;
    }

    if (shouldOfferContinueWatching()) {
      showConfirmAddToContinueWatching();
      return;
    }

    const videoId = currentVideo && currentVideo.id;
    const { position, duration, ratio } = estimateProgressState();
    const shouldMarkAsWatched = Boolean(
      !currentWatched
      && videoId
      && duration > 0
      && ratio >= AUTO_MARK_RATIO
    );

    let progressUpdated = false;
    let persistedVideoId = null;
    let persistedPosition = 0;
    let persistedDuration = 0;
    let persistedContinueWatching = false;

    if (!shouldMarkAsWatched && !currentWatched && position > 0 && position > resumeSeconds) {
      persistedVideoId = videoId;
      persistedPosition = position;
      persistedDuration = duration;
      persistedContinueWatching = currentInContinueWatching;
      lastKnownPosition = position;
      lastKnownDuration = duration;
      progressUpdated = true;
    }

    if (immediate) {
      doClose({ restore });
      if (shouldMarkAsWatched && videoId) {
        (async () => {
          await markVideoWatchedForCurrentUser(videoId);
          await finalizeWatchedTransition(videoId);
        })();
        return;
      }
      if (progressUpdated && persistedVideoId) {
        (async () => {
          await saveProgressForVideo(persistedVideoId, persistedPosition, persistedDuration, {
            continue_watching: persistedContinueWatching
          });
          if (typeof window.ytcvReloadCarousels === 'function') {
            await window.ytcvReloadCarousels({ preserveDOM: false });
          }
        })();
      }
      return;
    }

    if (shouldMarkAsWatched && videoId) {
      doClose({ restore });
      await markVideoWatchedForCurrentUser(videoId);
      await finalizeWatchedTransition(videoId);
      return;
    }

    if (progressUpdated && persistedVideoId) {
      await saveProgressForVideo(persistedVideoId, persistedPosition, persistedDuration, {
        continue_watching: persistedContinueWatching
      });
    }
    if (progressUpdated && typeof window.ytcvReloadCarousels === 'function') {
      await window.ytcvReloadCarousels({ preserveDOM: false });
    }

    doClose({ restore });
  }

  async function handleConfirmWatch() {
    const videoId = currentVideo && currentVideo.id;
    await handleMarkWatched();
    doClose();
    await finalizeWatchedTransition(videoId);
  }

  async function addToContinueWatching() {
    setConfirmBusy(true, 'add');
    const { position, duration } = estimateProgressState();
    const videoId = currentVideo && currentVideo.id;
    const shouldSave = position > 0 && videoId && !currentWatched;
    const saveDuration = duration || (currentVideo && currentVideo.duration) || lastKnownDuration || 0;
    if (position > 0 && currentVideo && !currentWatched) {
      lastKnownPosition = position;
      lastKnownDuration = duration;
      currentHasSavedProgress = true;
      currentInContinueWatching = true;
    }
    doClose();
    (async () => {
      if (shouldSave) {
        await saveProgressForVideo(videoId, position, saveDuration, { continue_watching: true });
      }
      if (typeof window.ytcvReloadCarousels === 'function') {
        await window.ytcvReloadCarousels({ preserveDOM: false });
      }
    })();
  }

  async function saveForLater() {
    const { position, duration } = estimateProgressState();
    const videoId = currentVideo && currentVideo.id;
    const saveDuration = duration || (currentVideo && currentVideo.duration) || lastKnownDuration || 0;
    const savePosition = Math.max(position, resumeSeconds);

    if (savePosition > 0 && currentVideo && !currentWatched) {
      lastKnownPosition = savePosition;
      lastKnownDuration = saveDuration;
    }
    currentHasSavedProgress = true;
    currentInContinueWatching = true;
    doClose();
    (async () => {
      if (videoId) {
        await saveProgressForVideo(videoId, savePosition, saveDuration, { continue_watching: true });
      }
      if (typeof window.ytcvReloadCarousels === 'function') {
        await window.ytcvReloadCarousels({ preserveDOM: false });
      }
    })();
  }

  async function skipContinueWatching() {
    setConfirmBusy(true, 'skip');
    const { position, duration } = estimateProgressState();
    const videoId = currentVideo && currentVideo.id;
    const shouldSave = position > 0 && videoId && !currentWatched;
    const saveDuration = duration || (currentVideo && currentVideo.duration) || lastKnownDuration || 0;
    if (position > 0 && currentVideo && !currentWatched) {
      lastKnownPosition = position;
      lastKnownDuration = duration;
      currentHasSavedProgress = false;
      currentInContinueWatching = false;
    }
    doClose();
    (async () => {
      if (shouldSave) {
        await saveProgressForVideo(videoId, position, saveDuration, { continue_watching: false });
      }
      if (typeof window.ytcvReloadCarousels === 'function') {
        await window.ytcvReloadCarousels({ preserveDOM: false });
      }
    })();
  }

  async function removeFromContinueWatching() {
    if (!currentHasSavedProgress || !currentVideo) {
      return;
    }
    const { position, duration } = estimateProgressState();
    currentHasSavedProgress = false;
    currentInContinueWatching = false;
    await saveProgressPosition(
      position > 0 ? position : resumeSeconds,
      duration,
      { continue_watching: false }
    );
    syncProgressButtons();
    if (typeof window.ytcvReloadCarousels === 'function') {
      await window.ytcvReloadCarousels({ preserveDOM: false });
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
      channelBadge: document.getElementById('player-overlay-channel'),
      channelLogo: document.getElementById('player-overlay-channel-logo'),
      channelName: document.getElementById('player-overlay-channel-name'),
      description: document.getElementById('player-overlay-description'),
      frame: document.getElementById('player-overlay-frame'),
      close: document.getElementById('player-overlay-close'),
      markWatched: document.getElementById('player-overlay-mark-watched'),
      saveForLater: document.getElementById('player-overlay-save-for-later'),
      removeProgress: document.getElementById('player-overlay-remove-progress'),
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
      ui.close.addEventListener('click', () => closeVideoOverlay({ immediate: true }));
    }

    if (ui.backdrop) {
      ui.backdrop.addEventListener('click', () => closeVideoOverlay({ immediate: true }));
    }

    if (ui.markWatched) {
      ui.markWatched.addEventListener('click', () => {
        if (confirmVisible) {
          if (confirmMode === 'continue-watching') {
            addToContinueWatching();
          } else {
            handleConfirmWatch();
          }
        } else {
          handleMarkWatched();
        }
      });
    }

    if (ui.removeProgress) {
      ui.removeProgress.addEventListener('click', () => {
        removeFromContinueWatching();
      });
    }

    if (ui.saveForLater) {
      ui.saveForLater.addEventListener('click', () => {
        saveForLater();
      });
    }

    if (ui.openYoutube) {
      ui.openYoutube.addEventListener('click', () => {
        handleOpenOnYouTube();
      });
    }

    if (ui.confirmLater) {
      ui.confirmLater.addEventListener('click', () => {
        if (confirmMode === 'continue-watching') {
          skipContinueWatching();
        }
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

  function openVideoOverlay({
    video,
    channel,
    watched = false,
    onMarkWatched = null,
    origin = null,
    progress = null,
    continueWatching = false
  } = {}) {
    if (!supportsEmbeddedPlayback() || !ui || !ui.root || !video || !video.yt_video_id) {
      return false;
    }

    destroyPlayer();
    resetFrameElement();

    opener = origin || document.activeElement;
    currentVideo = video;
    currentChannel = channel || null;
    currentWatched = Boolean(watched);
    currentMarkWatched = onMarkWatched;
    currentHasSavedProgress = Boolean(progress && typeof progress === 'number' && progress > 0);
    currentInContinueWatching = Boolean(continueWatching);
    autoMarked = false;
    playbackStarted = false;
    lastKnownPosition = 0;
    lastKnownDuration = 0;
    confirmVisible = false;
    confirmMode = null;
    confirmBusy = false;
    resumeSeconds = (progress && typeof progress === 'number' && progress > 0) ? progress : 0;
    sessionWatchStartedAt = 0;

    ui.eyebrow.textContent = currentChannel && currentChannel.title ? t('nowPlayingChannel', { channel: currentChannel.title }) : t('nowPlaying');
    ui.title.textContent = video.title || t('untitledVideo');
    ui.meta.textContent = formatMeta(video, channel);
    const channelLogoUrl = channel && (channel.thumbnail_local_url || channel.thumbnail_url)
      ? (channel.thumbnail_local_url || channel.thumbnail_url)
      : null;
    if (ui.channelBadge) {
      ui.channelBadge.hidden = !(channel && channel.title);
    }
    if (ui.channelLogo) {
      if (channelLogoUrl) {
        ui.channelLogo.src = channelLogoUrl;
        ui.channelLogo.alt = channel && channel.title ? channel.title : '';
        ui.channelLogo.hidden = false;
      } else {
        ui.channelLogo.hidden = true;
        ui.channelLogo.removeAttribute('src');
        ui.channelLogo.alt = '';
      }
    }
    if (ui.channelName) {
      ui.channelName.textContent = channel && channel.title ? channel.title : '';
    }
    const rawDescription = (video.description || '').trim();
    ui.description.textContent = typeof window.truncateText === 'function'
      ? window.truncateText(rawDescription, 420)
      : rawDescription;
    ui.openYoutube.textContent = t('openOnYouTube');
    if (ui.copyUrl) {
      ui.copyUrl.textContent = t('copyVideoUrl');
    }
    if (ui.confirmLater) {
      ui.confirmLater.textContent = t('skipContinueWatching');
    }
    if (ui.saveForLater) {
      ui.saveForLater.textContent = t('saveForLater');
    }
    syncWatchedButton();
    hideConfirm();
    syncProgressButtons();

    ui.root.hidden = false;
    document.body.classList.add('player-overlay-open');
    document.documentElement.classList.add('player-overlay-open');

    const activeVideoId = video.yt_video_id;
    const activeResumeSeconds = resumeSeconds;
    window.requestAnimationFrame(() => {
      if (!currentVideo || currentVideo.yt_video_id !== activeVideoId || !ui || !ui.frame || ui.root.hidden) {
        return;
      }
      if (apiAvailable && !USE_EMBED_ONLY) {
        schedulePlayerInit();
      }
      ui.frame.addEventListener('load', () => {
        if (!sessionWatchStartedAt) {
          sessionWatchStartedAt = Date.now();
        }
      }, { once: true });
      ui.frame.src = getEmbedUrl(activeVideoId, activeResumeSeconds, frameInstanceCounter);
    });

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
