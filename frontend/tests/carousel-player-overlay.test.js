import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('carousel embedded player integration', () => {
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
    window.open = vi.fn();
    window.appApiClient = {
      markAsWatched: vi.fn().mockResolvedValue({ ok: true })
    };
    window.getDeviceId = () => 'device-1';
  });

  it('opens the embedded overlay in desktop/tablet mode instead of leaving the app', async () => {
    document.documentElement.dataset.mode = 'desktop_tablet';
    window.ytcvPlayerOverlay = {
      openVideoOverlay: vi.fn(() => true)
    };

    await import('../js/carousel.js');

    const carousel = new window.Carousel('latest-carousel', async () => ({
      videos: [
        {
          watched: false,
          video: { id: 1, yt_video_id: 'a', title: 'A', duration: 120 },
          channel: { title: 'Channel A' }
        }
      ],
      has_more: false,
      next_offset: null
    }));

    await carousel.init();
    document.querySelector('.video-card').click();

    expect(window.ytcvPlayerOverlay.openVideoOverlay).toHaveBeenCalledTimes(1);
    expect(window.open).not.toHaveBeenCalled();
    expect(window.appApiClient.markAsWatched).not.toHaveBeenCalled();
  });

  it('keeps external playback behavior in phone mode', async () => {
    document.documentElement.dataset.mode = 'phone';
    window.ytcvPlayerOverlay = {
      openVideoOverlay: vi.fn(() => false)
    };

    await import('../js/carousel.js');

    const carousel = new window.Carousel('latest-carousel', async () => ({
      videos: [
        {
          watched: false,
          video: { id: 1, yt_video_id: 'a', title: 'A', duration: 120 },
          channel: { title: 'Channel A' }
        }
      ],
      has_more: false,
      next_offset: null
    }));

    await carousel.init();
    document.querySelector('.video-card').click();
    await Promise.resolve();

    expect(window.open).toHaveBeenCalledWith('https://www.youtube.com/watch?v=a', '_blank', 'noopener');
    expect(window.appApiClient.markAsWatched).toHaveBeenCalledTimes(1);
  });
});
