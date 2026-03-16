import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('refresh governance helpers', () => {
  beforeEach(async () => {
    vi.resetModules();
    delete window.ytcvRefreshGovernance;
    await import('../js/refresh-governance.js');
  });

  afterEach(() => {
    delete window.ytcvRefreshGovernance;
  });

  it('rounds retry delay up to at least one minute', () => {
    expect(window.ytcvRefreshGovernance.getRetryMinutes({ retry_after_seconds: 10 })).toBe(1);
    expect(window.ytcvRefreshGovernance.getRetryMinutes({ retry_after_seconds: 125 })).toBe(3);
  });

  it('builds the correct blocked messages for in-progress and cooldown states', () => {
    const t = (key, vars = {}) => `${key}:${vars.minutes || ''}`;

    expect(
      window.ytcvRefreshGovernance.getBlockedProgressMessage(t, { reason: 'refresh_in_progress' })
    ).toBe('refreshProgressAlreadyRunning:');

    expect(
      window.ytcvRefreshGovernance.getBlockedToastMessage(t, {
        reason: 'cooldown_active',
        retry_after_seconds: 125
      })
    ).toBe('refreshCooldownActive:3');
  });
});
