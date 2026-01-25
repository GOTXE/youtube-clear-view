// Utility helpers for UI and data formatting.

(() => {
  const NOTIFICATION_DURATION = (window.APP_CONFIG && window.APP_CONFIG.NOTIFICATION_DURATION) || 3000;

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
      return 'just now';
    }

    const intervals = [
      { label: 'year', seconds: 31536000 },
      { label: 'month', seconds: 2592000 },
      { label: 'week', seconds: 604800 },
      { label: 'day', seconds: 86400 },
      { label: 'hour', seconds: 3600 },
      { label: 'minute', seconds: 60 },
      { label: 'second', seconds: 1 }
    ];

    for (const interval of intervals) {
      const count = Math.floor(seconds / interval.seconds);
      if (count >= 1) {
        return `${count} ${interval.label}${count > 1 ? 's' : ''} ago`;
      }
    }

    return 'just now';
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

  function getYouTubeVideoUrl(videoId) {
    if (!videoId) {
      return '';
    }

    const baseUrl = window.APP_CONFIG && window.APP_CONFIG.YOUTUBE_BASE_URL
      ? window.APP_CONFIG.YOUTUBE_BASE_URL
      : 'https://www.youtube.com';
    return `${baseUrl}/watch?v=${videoId}`;
  }

  function getYouTubeThumbnail(videoId, quality = 'high') {
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
      heading.textContent = title || 'Message';

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
        : [{ text: 'Close', primary: true }];

      buttonConfigs.forEach(buttonConfig => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = buttonConfig.primary ? 'button' : 'button button--ghost';
        button.textContent = buttonConfig.text || 'OK';

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

  function isLocalhost() {
    return ['localhost', '127.0.0.1'].includes(window.location.hostname);
  }

  let logPanel = null;
  let logEntries = null;
  let logToggle = null;
  const logQueue = [];
  const LOG_LIMIT = 200;

  function initDevLogPanel() {
    if (!isLocalhost() || logPanel || !document.body) {
      return;
    }

    logPanel = document.createElement('section');
    logPanel.className = 'dev-log-panel';
    logPanel.setAttribute('aria-live', 'polite');

    const header = document.createElement('div');
    header.className = 'dev-log-panel__header';

    const title = document.createElement('span');
    title.textContent = 'API log';
    header.appendChild(title);

    const actions = document.createElement('div');
    actions.className = 'dev-log-panel__actions';

    const clearButton = document.createElement('button');
    clearButton.type = 'button';
    clearButton.className = 'dev-log-panel__clear';
    clearButton.textContent = 'Clear';
    clearButton.addEventListener('click', () => {
      if (logEntries) {
        logEntries.innerHTML = '';
      }
    });
    actions.appendChild(clearButton);

    logToggle = document.createElement('button');
    logToggle.type = 'button';
    logToggle.className = 'dev-log-panel__toggle';
    logToggle.textContent = 'Minimize';
    logToggle.setAttribute('aria-pressed', 'false');
    logToggle.addEventListener('click', () => {
      if (!logPanel) {
        return;
      }
      const minimized = logPanel.classList.toggle('dev-log-panel--minimized');
      logToggle.textContent = minimized ? 'Open' : 'Minimize';
      logToggle.setAttribute('aria-pressed', minimized ? 'true' : 'false');
    });
    actions.appendChild(logToggle);

    header.appendChild(actions);

    logEntries = document.createElement('div');
    logEntries.className = 'dev-log-panel__entries';

    logPanel.appendChild(header);
    logPanel.appendChild(logEntries);
    document.body.appendChild(logPanel);

    while (logQueue.length) {
      const entry = logQueue.shift();
      appendLogEntry(entry.message, entry.type);
    }
  }

  function appendLogEntry(message, type) {
    if (!logEntries || !message) {
      return;
    }

    const entry = document.createElement('div');
    entry.className = `dev-log-panel__entry dev-log-panel__entry--${type}`;
    const timestamp = new Date().toLocaleTimeString();
    entry.textContent = `[${timestamp}] ${message}`;
    logEntries.appendChild(entry);

    while (logEntries.children.length > LOG_LIMIT) {
      logEntries.removeChild(logEntries.firstChild);
    }
  }

  function logApiEvent(message, type = 'info') {
    if (!isLocalhost()) {
      return;
    }

    if (!logPanel) {
      logQueue.push({ message, type });
      if (document.readyState !== 'loading') {
        initDevLogPanel();
      }
      return;
    }

    appendLogEntry(message, type);
  }

  window.formatDuration = formatDuration;
  window.formatDate = formatDate;
  window.timeAgo = timeAgo;
  window.truncateText = truncateText;
  window.debounce = debounce;
  window.getYouTubeVideoUrl = getYouTubeVideoUrl;
  window.getYouTubeThumbnail = getYouTubeThumbnail;
  window.generateDeviceFingerprint = generateDeviceFingerprint;
  window.showNotification = showNotification;
  window.showModal = showModal;
  window.loadingSpinner = loadingSpinner;
  window.sanitizeHTML = sanitizeHTML;
  window.initDevLogPanel = initDevLogPanel;
  window.logApiEvent = logApiEvent;

  document.addEventListener('DOMContentLoaded', initDevLogPanel);
})();
