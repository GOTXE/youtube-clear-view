import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('carousel keyboard navigation', () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = '<div id="latest-carousel"></div>';
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
  });

  it('moves focus between cards with arrow keys', async () => {
    await import('../js/carousel.js');

    const carousel = new window.Carousel('latest-carousel', async () => ({
      videos: [
        {
          video: { id: 1, yt_video_id: 'a', title: 'A', duration: 120 },
          channel: { title: 'Channel A' }
        },
        {
          video: { id: 2, yt_video_id: 'b', title: 'B', duration: 120 },
          channel: { title: 'Channel B' }
        }
      ],
      has_more: false,
      next_offset: null
    }));

    await carousel.init();

    const cards = document.querySelectorAll('.video-card');
    expect(cards).toHaveLength(2);

    cards[0].focus();
    cards[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));

    expect(document.activeElement).toBe(cards[1]);
  });
});
