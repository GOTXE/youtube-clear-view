import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('channel sidebar search helpers', () => {
  beforeEach(() => {
    vi.resetModules();
    delete window.normalizeSidebarQuery;
    delete window.filterChannelsForSidebar;
  });

  it('filters channels by title or channel id without mutating the source array', async () => {
    await import('../js/channel-sidebar-search.js');

    const channels = [
      { id: 1, title: 'Alpha Tech', yt_channel_id: 'alpha-tech' },
      { id: 2, title: 'Beta Music', yt_channel_id: 'beta-music' },
      { id: 3, title: 'Gamma Live', yt_channel_id: 'gamma-live' }
    ];

    const filteredByTitle = window.filterChannelsForSidebar(channels, 'music');
    expect(filteredByTitle).toHaveLength(1);
    expect(filteredByTitle[0].id).toBe(2);

    const filteredById = window.filterChannelsForSidebar(channels, 'gamma-live');
    expect(filteredById).toHaveLength(1);
    expect(filteredById[0].id).toBe(3);

    expect(channels).toHaveLength(3);
  });

  it('normalizes whitespace and casing consistently', async () => {
    await import('../js/channel-sidebar-search.js');

    expect(window.normalizeSidebarQuery('  MiXeD Case  ')).toBe('mixed case');
  });
});
