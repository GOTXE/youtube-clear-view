import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('header context helpers', () => {
  beforeEach(() => {
    vi.resetModules();
    delete window.buildHeaderContext;
    window.timeAgo = value => `ago:${value}`;
  });

  it('builds a global summary when no channel is selected', async () => {
    await import('../js/header-context.js');

    const t = (key, vars) => {
      if (key === 'headerContextOverviewDescription') {
        return `${vars.count} subscriptions tracked`;
      }
      return key;
    };

    const result = window.buildHeaderContext(
      [
        { id: 1, unwatched_total: 3, last_checked_at: '2026-03-15T09:00:00Z' },
        { id: 2, unwatched_total: 4, category: { category: { name: 'Music' } } }
      ],
      null,
      null,
      null,
      t
    );

    expect(result.title).toBe('headerContextOverviewTitle');
    expect(result.description).toBe('2 subscriptions tracked');
    expect(result.metrics[0]).toEqual({ label: 'headerMetricSubscriptions', value: '2' });
    expect(result.metrics[1]).toEqual({ label: 'headerMetricUnwatched', value: '7' });
    expect(result.metrics[3]).toEqual({ label: 'headerMetricUnclassified', value: '1' });
  });

  it('builds a selected-channel summary with category and recent counts', async () => {
    await import('../js/header-context.js');

    const t = key => key;
    const result = window.buildHeaderContext(
      [
        {
          id: 8,
          yt_channel_id: 'channel-8',
          title: 'Andrea Ferrandis',
          description: 'Nutrition and endurance training insights.',
          unwatched_total: 9,
          recent_total_30: 12,
          last_checked_at: '2026-03-15T08:00:00Z',
          category: { category: { name: 'Fitness' } },
          thumbnail_local_url: '/api/channels/8/thumbnail'
        }
      ],
      8,
      null,
      null,
      t
    );

    expect(result.title).toBe('Andrea Ferrandis');
    expect(result.metrics[0]).toEqual({ label: 'headerMetricCategory', value: 'Fitness' });
    expect(result.metrics[1]).toEqual({ label: 'headerMetricUnwatched', value: '9' });
    expect(result.metrics[2]).toEqual({ label: 'headerMetricRecent', value: '12' });
    expect(result.media.url).toBe('/api/channels/8/thumbnail');
  });
});
