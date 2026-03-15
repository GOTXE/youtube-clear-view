import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('frontend utils', () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = '';
    document.documentElement.removeAttribute('data-theme');
    window.APP_CONFIG = {
      NOTIFICATION_DURATION: 25,
      YT_BASE_URL: 'https://www.youtube.com'
    };
    window.ytcvI18n = {
      t: (key, vars) => {
        if (key === 'timeAgo') {
          return `${vars.count} ${vars.unit} ago`;
        }
        if (key === 'timeJustNow') {
          return 'just now';
        }
        if (key === 'timeMinute') {
          return 'minute';
        }
        if (key === 'timeMinutePlural') {
          return 'minutes';
        }
        if (key === 'timeHour') {
          return 'hour';
        }
        if (key === 'timeHourPlural') {
          return 'hours';
        }
        return key;
      }
    };
  });

  afterEach(() => {
    vi.useRealTimers();
    delete window.APP_CONFIG;
    delete window.ytcvI18n;
    delete window.formatDuration;
    delete window.truncateText;
    delete window.showNotification;
    delete window.sanitizeHTML;
    delete window.getYTVideoUrl;
  });

  it('formats video durations', async () => {
    await import('../js/utils.js');

    expect(window.formatDuration(65)).toBe('1:05');
    expect(window.formatDuration(3661)).toBe('1:01:01');
    expect(window.formatDuration(Number.NaN)).toBe('');
  });

  it('truncates long text safely', async () => {
    await import('../js/utils.js');

    expect(window.truncateText('YT Clear View', 6)).toBe('YT ...');
    expect(window.truncateText('abc', 2)).toBe('..');
    expect(window.truncateText('short', 10)).toBe('short');
  });

  it('sanitizes HTML content before rendering', async () => {
    await import('../js/utils.js');

    expect(window.sanitizeHTML('<script>alert("x")</script>')).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;'
    );
  });

  it('creates and removes toast notifications', async () => {
    vi.useFakeTimers();
    await import('../js/utils.js');

    window.showNotification('Saved', 'success');

    const toast = document.querySelector('.toast');
    expect(toast).not.toBeNull();
    expect(toast.textContent).toBe('Saved');

    vi.advanceTimersByTime(25);
    expect(document.querySelector('.toast')).toBeNull();
  });

  it('builds YouTube URLs from configured base URL', async () => {
    await import('../js/utils.js');

    expect(window.getYTVideoUrl('abc123')).toBe('https://www.youtube.com/watch?v=abc123');
    expect(window.getYTVideoUrl('')).toBe('');
  });

  it('rounds relative times under one hour to 15-minute steps', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-15T10:00:00Z'));
    await import('../js/utils.js');

    expect(window.timeAgo('2026-03-15T09:51:00Z')).toBe('just now');
    expect(window.timeAgo('2026-03-15T09:40:00Z')).toBe('15 minutes ago');
    expect(window.timeAgo('2026-03-15T09:29:00Z')).toBe('30 minutes ago');
    expect(window.timeAgo('2026-03-15T09:10:00Z')).toBe('45 minutes ago');
    expect(window.timeAgo('2026-03-15T09:00:00Z')).toBe('1 hour ago');
  });
});
