// Utility helpers for UI and data formatting.

(() => {
  const NOTIFICATION_DURATION = (window.APP_CONFIG && window.APP_CONFIG.NOTIFICATION_DURATION) || 3000;
  const t = (key, vars) => (
    window.ytcvI18n && typeof window.ytcvI18n.t === 'function'
      ? window.ytcvI18n.t(key, vars)
      : key
  );

  function formatDuration(seconds) {
    if (typeof seconds !== 'number' || Number.isNaN(seconds)) {
      return '';
    }

    const total = Math.max(0, Math.floor(seconds));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;

    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    return `${minutes}:${String(secs).padStart(2, '0')}`;
  }

  function formatDate(dateString) {
    if (!dateString) {
      return '';
    }

    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) {
      return '';
    }

    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    }).format(date);
  }

  function timeAgo(dateString) {
    if (!dateString) {
      return '';
    }

    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) {
      return '';
    }

    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 0) {
      return t('timeJustNow');
    }

    const intervals = [
      { key: 'timeYear', seconds: 31536000 },
      { key: 'timeMonth', seconds: 2592000 },
      { key: 'timeWeek', seconds: 604800 },
      { key: 'timeDay', seconds: 86400 },
      { key: 'timeHour', seconds: 3600 },
      { key: 'timeMinute', seconds: 60 },
      { key: 'timeSecond', seconds: 1 }
    ];

    for (const interval of intervals) {
      const count = Math.floor(seconds / interval.seconds);
      if (count >= 1) {
        const unitKey = count === 1 ? interval.key : `${interval.key}Plural`;
        return t('timeAgo', { count, unit: t(unitKey) });
      }
    }

    return t('timeJustNow');
  }

  function truncateText(text, maxLength) {
    if (!text || typeof maxLength !== 'number' || maxLength <= 0) {
      return '';
    }

    if (text.length <= maxLength) {
      return text;
    }

    if (maxLength <= 3) {
      return '.'.repeat(maxLength);
    }

    return `${text.slice(0, maxLength - 3)}...`;
  }

  function debounce(func, delay) {
    let timeoutId = null;

    return function debounced(...args) {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      timeoutId = setTimeout(() => {
        func.apply(this, args);
      }, delay);
    };
  }

  function getYTVideoUrl(videoId) {
    if (!videoId) {
      return '';
    }

    const baseUrl = window.APP_CONFIG && window.APP_CONFIG.YT_BASE_URL
      ? window.APP_CONFIG.YT_BASE_URL
      : 'https://www.youtube.com';
    return `${baseUrl}/watch?v=${videoId}`;
  }

  function getYTThumbnail(videoId, quality = 'high') {
    if (!videoId) {
      return '';
    }

    const mapping = {
      default: 'default.jpg',
      medium: 'mqdefault.jpg',
      high: 'hqdefault.jpg',
      maxres: 'maxresdefault.jpg'
    };

    const filename = mapping[quality] || mapping.high;
    return `https://img.youtube.com/vi/${videoId}/${filename}`;
  }

  function hashString(value) {
    let hash = 2166136261;
    for (let i = 0; i < value.length; i += 1) {
      hash ^= value.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16);
  }

  function generateDeviceFingerprint() {
    const userAgent = navigator.userAgent || '';
    const width = window.screen ? window.screen.width : 0;
    const height = window.screen ? window.screen.height : 0;
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    const language = navigator.language || '';
    const fingerprint = `${userAgent}|${width}x${height}|${timezone}|${language}`;
    return `dev-${hashString(fingerprint)}`;
  }

  function sanitizeHTML(str) {
    if (str === null || str === undefined) {
      return '';
    }

    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');

    const colorTokens = {
      success: 'var(--success)',
      error: 'var(--error)',
      info: 'var(--info)',
      warning: 'var(--warning)'
    };

    if (colorTokens[type]) {
      toast.style.borderColor = colorTokens[type];
    }

    document.body.appendChild(toast);

    setTimeout(() => {
      toast.remove();
    }, NOTIFICATION_DURATION);
  }

  function showModal(title, content, buttons = []) {
    return new Promise(resolve => {
      const overlay = document.createElement('div');
      overlay.className = 'modal';
      overlay.setAttribute('role', 'dialog');
      overlay.setAttribute('aria-modal', 'true');

      const modalContent = document.createElement('div');
      modalContent.className = 'modal__content';

      const heading = document.createElement('h2');
      heading.className = 'heading-2';
      heading.textContent = title || t('modalMessageTitle');

      const body = document.createElement('div');
      if (typeof content === 'string') {
        const paragraph = document.createElement('p');
        paragraph.className = 'body';
        paragraph.textContent = content;
        body.appendChild(paragraph);
      } else if (content instanceof Node) {
        body.appendChild(content);
      }

      const actions = document.createElement('div');
      actions.className = 'field__group';

      const buttonConfigs = buttons.length
        ? buttons
        : [{ text: t('modalClose'), primary: true }];

      buttonConfigs.forEach(buttonConfig => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = buttonConfig.primary ? 'button' : 'button button--ghost';
        button.textContent = buttonConfig.text || t('modalOk');

        button.addEventListener('click', () => {
          if (typeof buttonConfig.onClick === 'function') {
            buttonConfig.onClick();
          }
          overlay.remove();
          resolve(buttonConfig);
        });

        actions.appendChild(button);
      });

      modalContent.appendChild(heading);
      modalContent.appendChild(body);
      modalContent.appendChild(actions);
      overlay.appendChild(modalContent);
      overlay.addEventListener('click', event => {
        if (event.target === overlay) {
          overlay.remove();
          resolve(null);
        }
      });

      document.body.appendChild(overlay);
    });
  }

  let scrollTimer = null;
  const handleScroll = () => {
    document.body.classList.add('is-scrolling');
    if (scrollTimer) {
      clearTimeout(scrollTimer);
    }
    scrollTimer = setTimeout(() => {
      document.body.classList.remove('is-scrolling');
    }, 800);
  };

  document.addEventListener('scroll', handleScroll, { passive: true, capture: true });

  function loadingSpinner(show, containerId) {
    const overlayId = 'global-loading-spinner';
    const container = containerId ? document.getElementById(containerId) : null;

    if (!show) {
      const existing = container
        ? container.querySelector('[data-loading="true"]')
        : document.getElementById(overlayId);

      if (existing) {
        existing.remove();
      }

      if (container) {
        const skeletons = container.querySelectorAll('[data-skeleton="true"]');
        skeletons.forEach(node => node.remove());
      }

      return;
    }

    if (container) {
      const spinner = document.createElement('div');
      spinner.className = 'spinner';
      spinner.dataset.loading = 'true';
      container.appendChild(spinner);

      for (let i = 0; i < 3; i += 1) {
        const skeleton = document.createElement('div');
        skeleton.className = 'video-card';
        skeleton.dataset.skeleton = 'true';
        skeleton.style.opacity = '0.6';

        const thumb = document.createElement('div');
        thumb.className = 'video-card__thumb';
        thumb.style.background = 'var(--border)';

        const body = document.createElement('div');
        body.className = 'video-card__body';

        const line = document.createElement('div');
        line.style.height = '16px';
        line.style.borderRadius = 'var(--radius-2)';
        line.style.background = 'var(--border)';

        body.appendChild(line);
        skeleton.appendChild(thumb);
        skeleton.appendChild(body);

        container.appendChild(skeleton);
      }

      return;
    }

    const overlay = document.createElement('div');
    overlay.className = 'modal';
    overlay.id = overlayId;

    const spinner = document.createElement('div');
    spinner.className = 'spinner';

    overlay.appendChild(spinner);
    document.body.appendChild(overlay);
  }

  window.formatDuration = formatDuration;
  window.formatDate = formatDate;
  window.timeAgo = timeAgo;
  window.truncateText = truncateText;
  window.debounce = debounce;
  window.getYTVideoUrl = getYTVideoUrl;
  window.getYTThumbnail = getYTThumbnail;
  window.generateDeviceFingerprint = generateDeviceFingerprint;
  window.showNotification = showNotification;
  window.showModal = showModal;
  window.loadingSpinner = loadingSpinner;
  window.sanitizeHTML = sanitizeHTML;
})();
