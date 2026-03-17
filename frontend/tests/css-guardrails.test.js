import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

describe('css guardrails', () => {
  it('keeps mode selectors out of main.css', () => {
    const css = readFileSync(path.resolve(process.cwd(), 'css/main.css'), 'utf8');
    expect(css).not.toContain('html[data-mode="');
  });
});
