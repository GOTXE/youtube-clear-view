import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('player overlay', () => {
  beforeEach(() => {
    vi.resetModules();
    document.documentElement.dataset.mode = 'desktop_tablet';
    document.body.innerHTML = `
      <section id="player-overlay" hidden>
        <div id="player-overlay-backdrop"></div>
        <div class="player-overlay__dialog">
          <p id="player-overlay-eyebrow"></p>
          <h2 id="player-overlay-title"></h2>
          <p id="player-overlay-meta"></p>
          <p id="player-overlay-description"></p>
          <iframe id="player-overlay-frame" src="about:blank"></iframe>
          <button id="player-overlay-close" type="button">Close</button>
          <button id="player-overlay-mark-watched" type="button">Mark watched</button>
          <button id="player-overlay-open-youtube" type="button">Open on YouTube</button>
        </div>
      </section>
      <button id="origin" type="button">Origin</button>
    `;

    window.ytcvI18n = {
      t: (key, vars = {}) => {
        if (key === 'nowPlayingChannel') {
          return `Now playing from ${vars.channel}`;
        }
        const translations = {
          openOnYouTube: 'Open on YouTube',
          markWatched: 'Mark watched',
          watchedBadge: 'Watched',
          untitledVideo: 'Untitled video',
          nowPlaying: 'Now playing'
        };
        return translations[key] || key;
      }
    };
    window.formatDate = () => 'Mar 17, 2026';
    window.formatDuration = () => '10:00';
    window.getYTVideoUrl = videoId => `https://www.youtube.com/watch?v=${videoId}`;
    window.open = vi.fn();
  });

  afterEach(() => {
    delete window.ytcvPlayerOverlay;
    delete window.ytcvI18n;
    delete window.formatDate;
    delete window.formatDuration;
    delete window.getYTVideoUrl;
    delete document.documentElement.dataset.mode;
  });

  it('opens and closes the overlay in desktop/tablet mode', async () => {
    await import('../js/player-overlay.js');

    const origin = document.getElementById('origin');
    origin.focus();

    const opened = window.ytcvPlayerOverlay.openVideoOverlay({
      origin,
      video: {
        yt_video_id: 'abc123',
        title: 'Overlay video',
        description: 'Test description',
        published_at: '2026-03-17T10:00:00Z',
        duration: 600
      },
      channel: {
        title: 'Overlay channel'
      }
    });

    expect(opened).toBe(true);
    expect(document.getElementById('player-overlay').hidden).toBe(false);
    expect(document.getElementById('player-overlay-title').textContent).toBe('Overlay video');
    expect(document.getElementById('player-overlay-meta').textContent).toContain('Overlay channel');
    expect(document.getElementById('player-overlay-frame').src).toContain('/embed/abc123');

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));

    expect(document.getElementById('player-overlay').hidden).toBe(true);
    expect(document.activeElement).toBe(origin);
  });

  it('keeps phone mode on external playback', async () => {
    document.documentElement.dataset.mode = 'phone';
    await import('../js/player-overlay.js');

    const opened = window.ytcvPlayerOverlay.openVideoOverlay({
      video: { yt_video_id: 'abc123', title: 'Phone video' },
      channel: { title: 'Phone channel' }
    });

    expect(opened).toBe(false);
    expect(document.getElementById('player-overlay').hidden).toBe(true);
  });

  it('can mark a video watched and open the YouTube fallback', async () => {
    const markWatched = vi.fn().mockResolvedValue(undefined);
    await import('../js/player-overlay.js');

    window.ytcvPlayerOverlay.openVideoOverlay({
      video: {
        yt_video_id: 'abc123',
        title: 'Overlay video',
        description: '',
        published_at: '2026-03-17T10:00:00Z',
        duration: 600
      },
      channel: {
        title: 'Overlay channel'
      },
      onMarkWatched: markWatched
    });

    document.getElementById('player-overlay-mark-watched').click();
    await Promise.resolve();

    const watchedButton = document.getElementById('player-overlay-mark-watched');
    expect(markWatched).toHaveBeenCalledTimes(1);
    expect(watchedButton.disabled).toBe(true);
    expect(watchedButton.textContent).toBe('Watched');

    document.getElementById('player-overlay-open-youtube').click();
    expect(window.open).toHaveBeenCalledWith('https://www.youtube.com/watch?v=abc123', '_blank', 'noopener');
  });
});
