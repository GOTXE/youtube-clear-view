import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('category manager', () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = '<div id="category-carousels"></div>';
    window.ytcvI18n = {
      t: (key, vars = {}) => {
        if (key === 'mobileChannelsCount') {
          return `${vars.count} channels`;
        }
        return key;
      }
    };
    window.Carousel = class {
      constructor() {}
      async init() {}
      destroy() {}
    };
  });

  it('renders an active category tile and emits selection events', async () => {
    await import('../js/categories.js');

    const onCategorySelect = vi.fn();
    const api = {
      getCategories: vi.fn().mockResolvedValue({
        ok: true,
        data: {
          categories: [
            { id: 1, name: 'technology', display_name_es: 'Tecnologia', icon: '💻', channel_count: 4 }
          ]
        }
      }),
      getCategoryVideos: vi.fn().mockResolvedValue({
        ok: true,
        data: { videos: [], has_more: false, next_offset: null }
      })
    };

    const manager = new window.CategoryManager(api, 'category-carousels', {
      getSelectedCategoryId: () => 1,
      onCategorySelect
    });

    await manager.init();

    const tile = document.querySelector('.category-carousel-wrapper');
    expect(tile).not.toBeNull();
    expect(tile.classList.contains('is-active')).toBe(true);
    expect(tile.getAttribute('aria-pressed')).toBe('true');
    expect(tile.textContent).toContain('4 channels');

    tile.click();
    expect(onCategorySelect).toHaveBeenCalledTimes(1);
    expect(onCategorySelect.mock.calls[0][0].id).toBe(1);
  });
});
