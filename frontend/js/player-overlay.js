// Embedded player overlay for desktop/tablet and TV modes.

(() => {
  let initialized = false;
  let ui = null;
  let opener = null;
  let focusables = [];
  let currentVideo = null;
  let currentChannel = null;
  let currentWatched = false;
  let currentMarkWatched = null;

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
    return parts.join(' • ');
  }

  function getEmbedUrl(videoId) {
    if (!videoId) {
      return 'about:blank';
    }
    return `https://www.youtube.com/embed/${encodeURIComponent(videoId)}?autoplay=1&rel=0&playsinline=1&modestbranding=1`;
  }

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

  function closeVideoOverlay({ restore = true } = {}) {
    if (!ui || !ui.root || ui.root.hidden) {
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
    focusables = [];

    if (restore) {
      restoreFocus();
    }
  }

  async function handleMarkWatched() {
    if (currentWatched || typeof currentMarkWatched !== 'function') {
      return;
    }
    await currentMarkWatched();
    currentWatched = true;
    syncWatchedButton();
  }

  function handleOpenOnYouTube() {
    if (!currentVideo || !currentVideo.yt_video_id) {
      return;
    }
    const url = typeof window.getYTVideoUrl === 'function'
      ? window.getYTVideoUrl(currentVideo.yt_video_id)
      : `https://www.youtube.com/watch?v=${currentVideo.yt_video_id}`;
    window.open(url, '_blank', 'noopener');
  }

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
      openYoutube: document.getElementById('player-overlay-open-youtube')
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
        handleMarkWatched();
      });
    }

    if (ui.openYoutube) {
      ui.openYoutube.addEventListener('click', () => {
        handleOpenOnYouTube();
      });
    }

    document.addEventListener('keydown', onKeydown);
    window.addEventListener('layout-mode:changed', event => {
      if (event.detail && !supportsEmbeddedPlayback(event.detail.mode)) {
        closeVideoOverlay({ restore: false });
      }
    });

    initialized = true;
    return {
      openVideoOverlay,
      closeVideoOverlay,
      supportsEmbeddedPlayback
    };
  }

  function openVideoOverlay({ video, channel, watched = false, onMarkWatched = null, origin = null } = {}) {
    if (!supportsEmbeddedPlayback() || !ui || !ui.root || !video || !video.yt_video_id) {
      return false;
    }

    opener = origin || document.activeElement;
    currentVideo = video;
    currentChannel = channel || null;
    currentWatched = Boolean(watched);
    currentMarkWatched = onMarkWatched;

    ui.eyebrow.textContent = currentChannel && currentChannel.title ? t('nowPlayingChannel', { channel: currentChannel.title }) : t('nowPlaying');
    ui.title.textContent = video.title || t('untitledVideo');
    ui.meta.textContent = formatMeta(video, channel);
    ui.description.textContent = (video.description || '').trim();
    ui.frame.src = getEmbedUrl(video.yt_video_id);
    ui.openYoutube.textContent = t('openOnYouTube');
    syncWatchedButton();

    ui.root.hidden = false;
    document.body.classList.add('player-overlay-open');
    document.documentElement.classList.add('player-overlay-open');

    focusables = getFocusableElements();
    window.setTimeout(() => {
      const target = ui.close || focusables[0];
      if (target && typeof target.focus === 'function') {
        target.focus();
      }
    }, 0);
    return true;
  }

  const api = initPlayerOverlay();

  window.ytcvPlayerOverlay = {
    ...api,
    initPlayerOverlay
  };
})();
