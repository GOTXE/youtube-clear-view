import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('phone shell', () => {
  beforeEach(() => {
    vi.resetModules();
    document.documentElement.dataset.mode = 'phone';
    document.body.innerHTML = `
      <div id="channel-sidebar-backdrop" hidden></div>
      <button id="channel-sidebar-close" type="button"></button>
      <nav id="phone-nav" hidden>
        <button id="phone-nav-channels" type="button"></button>
        <button id="phone-nav-filters" type="button"></button>
        <button id="phone-nav-menu" type="button"></button>
      </nav>
    `;
  });

  afterEach(() => {
    delete window.ytcvPhoneShell;
    delete document.documentElement.dataset.mode;
    document.body.classList.remove('phone-sidebar-open');
  });

  it('shows the mobile nav and toggles the subscriptions sheet', async () => {
    await import('../js/phone-shell.js');

    const shell = window.ytcvPhoneShell.initPhoneShell({});
    expect(document.getElementById('phone-nav').hidden).toBe(false);

    document.getElementById('phone-nav-channels').click();
    expect(document.body.classList.contains('phone-sidebar-open')).toBe(true);
    expect(document.getElementById('channel-sidebar-backdrop').hidden).toBe(false);

    shell.closeChannelSheet();
    expect(document.body.classList.contains('phone-sidebar-open')).toBe(false);
    expect(document.getElementById('channel-sidebar-backdrop').hidden).toBe(true);
  });

  it('routes filters and menu actions through callbacks', async () => {
    const openFilters = vi.fn();
    const openMenu = vi.fn();

    await import('../js/phone-shell.js');
    window.ytcvPhoneShell.initPhoneShell({ openFilters, openMenu });

    document.getElementById('phone-nav-filters').click();
    document.getElementById('phone-nav-menu').click();

    expect(openFilters).toHaveBeenCalledTimes(1);
    expect(openMenu).toHaveBeenCalledTimes(1);
  });

  it('hides mobile nav and closes the sheet when leaving phone mode', async () => {
    await import('../js/phone-shell.js');
    const shell = window.ytcvPhoneShell.initPhoneShell({});

    shell.openChannelSheet();
    expect(document.body.classList.contains('phone-sidebar-open')).toBe(true);

    document.documentElement.dataset.mode = 'desktop_tablet';
    window.dispatchEvent(new CustomEvent('layout-mode:changed', {
      detail: { mode: 'desktop_tablet' }
    }));

    expect(document.getElementById('phone-nav').hidden).toBe(true);
    expect(document.body.classList.contains('phone-sidebar-open')).toBe(false);
  });
});
