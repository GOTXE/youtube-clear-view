import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('desktop shell', () => {
  beforeEach(() => {
    vi.resetModules();
    document.documentElement.dataset.mode = 'desktop_tablet';
    window.innerWidth = 1440;
    localStorage.clear();
    document.body.innerHTML = `
      <section id="filter-panel" class="filter-panel" hidden>
        <div class="filter-panel__header">
          <h2>Filters</h2>
          <button id="filters-close" type="button">✕</button>
        </div>
        <div class="filter-panel__body"></div>
      </section>
    `;
  });

  afterEach(() => {
    delete window.ytcvDesktopShell;
    delete document.documentElement.dataset.mode;
    document.body.classList.remove('desktop-filters-docked');
    localStorage.clear();
  });

  it('keeps the floating filters closed until the user docks them', async () => {
    await import('../js/desktop-shell.js');
    window.ytcvDesktopShell.initDesktopShell();

    const panel = document.getElementById('filter-panel');
    const dockButton = document.getElementById('filters-dock-toggle');

    expect(panel.hidden).toBe(true);
    expect(panel.classList.contains('is-docked')).toBe(false);
    expect(dockButton.textContent).toBe('dockFilters');
  });

  it('persists manual dock decisions', async () => {
    await import('../js/desktop-shell.js');
    window.ytcvDesktopShell.initDesktopShell();

    const panel = document.getElementById('filter-panel');
    const dockButton = document.getElementById('filters-dock-toggle');
    dockButton.click();

    expect(panel.classList.contains('is-docked')).toBe(true);
    expect(panel.hidden).toBe(false);
    expect(localStorage.getItem('ytcv_desktop_filters_docked')).toBe('true');
    expect(dockButton.textContent).toBe('undockFilters');
  });

  it('hides the panel when leaving desktop/tablet mode', async () => {
    await import('../js/desktop-shell.js');
    const shell = window.ytcvDesktopShell.initDesktopShell();

    document.documentElement.dataset.mode = 'phone';
    window.dispatchEvent(new CustomEvent('layout-mode:changed', {
      detail: { mode: 'phone' }
    }));
    shell.sync();

    const panel = document.getElementById('filter-panel');
    const dockButton = document.getElementById('filters-dock-toggle');
    expect(panel.hidden).toBe(true);
    expect(dockButton.hidden).toBe(true);
  });
});
