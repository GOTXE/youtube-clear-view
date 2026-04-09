import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('carousel keyboard navigation', () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = '<div id="latest-carousel"></div>';
    document.documentElement.dataset.mode = 'phone';
    window.ytcvI18n = {
      t: key => key
    };
    window.APP_CONFIG = {
      VIDEOS_PER_LOAD: 2,
      YT_BASE_URL: 'https://www.youtube.com'
    };
    window.IntersectionObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
    window.timeAgo = value => `ago:${value}`;
  });

  it('moves focus between cards with arrow keys', async () => {
    await import('../js/carousel.js');

    const carousel = new window.Carousel('latest-carousel', async () => ({
      videos: [
        {
          video: { id: 1, yt_video_id: 'a', title: 'A', duration: 120, published_at: '2026-04-01T10:00:00Z' },
          channel: { title: 'Channel A' }
        },
        {
          video: { id: 2, yt_video_id: 'b', title: 'B', duration: 120, published_at: '2026-04-01T12:00:00Z' },
          channel: { title: 'Channel B' }
        }
      ],
      has_more: false,
      next_offset: null
    }));

    await carousel.init();

    const cards = document.querySelectorAll('.video-card');
    expect(cards).toHaveLength(2);
    expect(cards[0].querySelector('.video-card__duration')?.textContent).toBe('2:00');
    expect(cards[0].querySelector('.video-card__duration-line')).toBeNull();
    expect(cards[0].querySelector('.video-card__details')?.textContent).toBe('ago:2026-04-01T10:00:00Z');
    expect(cards[0].querySelector('.video-card__description')).toBeNull();

    cards[0].focus();
    cards[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));

    expect(document.activeElement).toBe(cards[1]);
  });
});
