import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('phone shell', () => {
  beforeEach(() => {
    vi.resetModules();
    document.documentElement.dataset.mode = 'phone';
    document.body.innerHTML = `
      <div id="channel-sidebar-backdrop" hidden></div>
      <button id="channel-sidebar-close" type="button"></button>
      <nav id="phone-nav" hidden>
        <button id="phone-nav-home" type="button"></button>
        <button id="phone-nav-channels" type="button"></button>
        <button id="phone-nav-categories" type="button"></button>
        <button id="phone-nav-settings" type="button"></button>
      </nav>
    `;
  });

  afterEach(() => {
    delete window.ytcvPhoneShell;
    delete document.documentElement.dataset.mode;
  });

  it('shows the mobile nav and switches between tab views', async () => {
    await import('../js/phone-shell.js');

    const shell = window.ytcvPhoneShell.initPhoneShell({});
    expect(document.getElementById('phone-nav').hidden).toBe(false);
    expect(shell.getActiveView()).toBe('home');

    document.getElementById('phone-nav-channels').click();
    expect(shell.getActiveView()).toBe('channels');
    expect(document.getElementById('phone-nav-channels').classList.contains('is-active')).toBe(true);

    shell.closeChannelSheet();
    expect(shell.getActiveView()).toBe('home');
    expect(document.getElementById('phone-nav-home').classList.contains('is-active')).toBe(true);
  });

  it('notifies the app when the active mobile view changes', async () => {
    const onViewChange = vi.fn();

    await import('../js/phone-shell.js');
    window.ytcvPhoneShell.initPhoneShell({ onViewChange });

    document.getElementById('phone-nav-categories').click();
    document.getElementById('phone-nav-settings').click();

    expect(onViewChange).toHaveBeenCalledWith('categories', expect.objectContaining({ source: 'user' }));
    expect(onViewChange).toHaveBeenCalledWith('settings', expect.objectContaining({ source: 'user' }));
  });

  it('hides mobile nav and resets to home when leaving phone mode', async () => {
    const onViewChange = vi.fn();

    await import('../js/phone-shell.js');
    const shell = window.ytcvPhoneShell.initPhoneShell({ onViewChange });

    shell.setActiveView('settings');
    expect(shell.getActiveView()).toBe('settings');

    document.documentElement.dataset.mode = 'desktop_tablet';
    window.dispatchEvent(new CustomEvent('layout-mode:changed', {
      detail: { mode: 'desktop_tablet' }
    }));

    expect(document.getElementById('phone-nav').hidden).toBe(true);
    expect(onViewChange).toHaveBeenCalledWith('home', expect.objectContaining({ source: 'layout' }));
  });
});
