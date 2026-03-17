import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('tv shell', () => {
  beforeEach(() => {
    vi.resetModules();
    document.documentElement.dataset.mode = 'tv';
    document.body.innerHTML = `
      <nav id="tv-action-bar" hidden>
        <button id="tv-action-channels" type="button"></button>
        <button id="tv-action-filters" type="button"></button>
        <button id="tv-action-refresh" type="button"></button>
        <button id="tv-action-display" type="button"></button>
      </nav>
    `;
  });

  afterEach(() => {
    delete window.ytcvTvShell;
    delete document.documentElement.dataset.mode;
  });

  it('shows the TV action bar in tv mode', async () => {
    await import('../js/tv-shell.js');
    window.ytcvTvShell.initTvShell({});

    expect(document.getElementById('tv-action-bar').hidden).toBe(false);
  });

  it('routes TV quick actions through callbacks', async () => {
    const focusChannels = vi.fn();
    const openFilters = vi.fn();
    const triggerRefresh = vi.fn();
    const openDisplaySetup = vi.fn();

    await import('../js/tv-shell.js');
    window.ytcvTvShell.initTvShell({
      focusChannels,
      openFilters,
      triggerRefresh,
      openDisplaySetup
    });

    document.getElementById('tv-action-channels').click();
    document.getElementById('tv-action-filters').click();
    document.getElementById('tv-action-refresh').click();
    document.getElementById('tv-action-display').click();

    expect(focusChannels).toHaveBeenCalledTimes(1);
    expect(openFilters).toHaveBeenCalledTimes(1);
    expect(triggerRefresh).toHaveBeenCalledTimes(1);
    expect(openDisplaySetup).toHaveBeenCalledTimes(1);
  });

  it('hides the TV action bar when leaving tv mode', async () => {
    await import('../js/tv-shell.js');
    const shell = window.ytcvTvShell.initTvShell({});

    document.documentElement.dataset.mode = 'desktop_tablet';
    window.dispatchEvent(new CustomEvent('layout-mode:changed', {
      detail: { mode: 'desktop_tablet' }
    }));
    shell.sync();

    expect(document.getElementById('tv-action-bar').hidden).toBe(true);
  });
});
