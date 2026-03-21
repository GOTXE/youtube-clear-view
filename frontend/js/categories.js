// Category management for automatic channel classification.

class CategoryManager {
  constructor(api, containerId) {
    this.api = api;
    this.container = document.getElementById(containerId);
    this.categories = [];
    this.carousels = [];
  }

  async init() {
    const response = await this.api.getCategories();
    if (!response.ok || !response.data) {
      return;
    }
    this.categories = response.data.categories || response.data || [];
    await this.render();
  }

  async render() {
    if (!this.container) {
      return;
    }

    this.container.innerHTML = '';

    const categoriesWithChannels = this.categories.filter(cat => cat.channel_count > 0);

    if (!categoriesWithChannels.length) {
      const empty = document.createElement('p');
      empty.className = 'caption';
      empty.textContent = 'No hay canales clasificados todavía';
      this.container.appendChild(empty);
      return;
    }

    for (const category of categoriesWithChannels) {
      await this.renderCategoryCarousel(category);
    }
  }

  async renderCategoryCarousel(category) {
    const carouselId = `category-carousel-${category.id}`;

    const wrapper = document.createElement('div');
    wrapper.className = 'category-carousel-wrapper';

    const header = document.createElement('div');
    header.className = 'category-header';

    const title = document.createElement('h3');
    title.className = 'heading-3 category-title';
    title.innerHTML = `<span class="category-icon">${category.icon || ''}</span> ${category.display_name_es || category.name}`;

    const categoryClass = this.getCategoryColorClass(category.name);
    title.classList.add(categoryClass);

    header.appendChild(title);
    wrapper.appendChild(header);

    const carouselContainer = document.createElement('div');
    carouselContainer.id = carouselId;
    carouselContainer.className = 'carousel-shell';
    wrapper.appendChild(carouselContainer);

    this.container.appendChild(wrapper);

    if (typeof window.Carousel === 'function') {
      const carousel = new window.Carousel(carouselId, async (offset, limit) => {
        const response = await this.api.getCategoryVideos(category.id, limit, offset);
        if (!response.ok || !response.data) {
          return { videos: [], has_more: false, next_offset: null };
        }
        return response.data;
      }, { hideTextForShorts: true });

      await carousel.init();
      this.carousels.push(carousel);
    }
  }

  getCategoryColorClass(categoryName) {
    const name = (categoryName || '').toLowerCase();
    const categoryMap = {
      gaming: 'category-color-gaming',
      technology: 'category-color-technology',
      education: 'category-color-education',
      music: 'category-color-music',
      automotive: 'category-color-automotive',
      food: 'category-color-food',
      fitness: 'category-color-health',
      health: 'category-color-health',
      travel: 'category-color-travel',
      fashion: 'category-color-fashion',
      news: 'category-color-news',
      entertainment: 'category-color-entertainment',
      vlogs: 'category-color-vlogs',
      sports: 'category-color-sports',
      art: 'category-color-art',
      animals: 'category-color-animals',
      science: 'category-color-science',
      lifestyle: 'category-color-lifestyle',
      business: 'category-color-business'
    };
    return categoryMap[name] || 'category-color-default';
  }

  destroy() {
    this.carousels.forEach(carousel => {
      if (typeof carousel.destroy === 'function') {
        carousel.destroy();
      }
    });
    this.carousels = [];
    if (this.container) {
      this.container.innerHTML = '';
    }
  }
}

class ChannelRating {
  constructor(container, channelId, initialRating = null, api, onUpdate) {
    this.container = container;
    this.channelId = channelId;
    this.currentRating = initialRating;
    this.api = api;
    this.onUpdate = onUpdate;
    this.init();
  }

  init() {
    const stars = this.container.querySelectorAll('.star-btn');
    const clearBtn = this.container.querySelector('.rating-clear-btn');

    this.updateVisual();

    stars.forEach(btn => {
      btn.addEventListener('click', async () => {
        const rating = parseInt(btn.dataset.value, 10);
        await this.setRating(rating);
      });
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', async () => {
        await this.clearRating();
      });
    }

    stars.forEach((btn, idx) => {
      btn.addEventListener('mouseenter', () => {
        this.highlightStars(idx + 1);
      });
    });

    this.container.addEventListener('mouseleave', () => {
      this.updateVisual();
    });
  }

  async setRating(rating) {
    const response = await this.api.rateChannel(this.channelId, rating);
    if (response.ok) {
      this.currentRating = rating;
      this.updateVisual();
      if (typeof this.onUpdate === 'function') {
        this.onUpdate(rating);
      }
    }
  }

  async clearRating() {
    const response = await this.api.removeChannelRating(this.channelId);
    if (response.ok) {
      this.currentRating = null;
      this.updateVisual();
      if (typeof this.onUpdate === 'function') {
        this.onUpdate(null);
      }
    }
  }

  updateVisual() {
    const stars = this.container.querySelectorAll('.star-btn');
    stars.forEach((btn, idx) => {
      btn.classList.toggle('active', idx < this.currentRating);
    });
  }

  highlightStars(count) {
    const stars = this.container.querySelectorAll('.star-btn');
    stars.forEach((btn, idx) => {
      btn.classList.toggle('active', idx < count);
    });
  }
}

function createRatingWidget(channelId, initialRating = null) {
  const container = document.createElement('div');
  container.className = 'channel-rating';
  container.dataset.channelId = String(channelId);
  if (initialRating !== null) {
    container.dataset.rating = String(initialRating);
  }

  for (let i = 1; i <= 5; i++) {
    const star = document.createElement('button');
    star.type = 'button';
    star.className = 'star-btn';
    star.dataset.value = String(i);
    star.setAttribute('aria-label', `${i} estrellas`);
    star.innerHTML = '<span class="star-icon">&#9733;</span>';
    container.appendChild(star);
  }

  const clearBtn = document.createElement('button');
  clearBtn.type = 'button';
  clearBtn.className = 'rating-clear-btn';
  clearBtn.setAttribute('aria-label', 'Quitar valoracion');
  clearBtn.innerHTML = '&times;';
  container.appendChild(clearBtn);

  return container;
}

class CategorySelector {
  constructor(api, onCategoryChange) {
    this.api = api;
    this.categories = [];
    this.onCategoryChange = onCategoryChange;
    this.modal = null;
    this.currentChannelId = null;
    this.currentChannelName = '';
  }

  async loadCategories() {
    if (this.categories.length > 0) {
      return this.categories;
    }
    const response = await this.api.getCategories();
    if (response.ok && response.data) {
      this.categories = response.data.categories || response.data || [];
    }
    return this.categories;
  }

  getCategories() {
    return this.categories;
  }

  getCategoryById(id) {
    return this.categories.find(cat => cat.id === id);
  }

  getCategoryByName(name) {
    return this.categories.find(cat => cat.name === name || cat.display_name_es === name);
  }

  createModal() {
    if (this.modal) {
      return this.modal;
    }

    const overlay = document.createElement('div');
    overlay.className = 'category-modal-overlay';
    overlay.id = 'category-modal';
    overlay.hidden = true;

    const modal = document.createElement('div');
    modal.className = 'category-modal';

    const header = document.createElement('div');
    header.className = 'category-modal__header';
    header.innerHTML = `
      <h3 class="heading-3" id="category-modal-title">Seleccionar Categoria</h3>
      <button type="button" class="category-modal__close" aria-label="Cerrar">&times;</button>
    `;

    const body = document.createElement('div');
    body.className = 'category-modal__body';
    body.id = 'category-modal-body';

    const footer = document.createElement('div');
    footer.className = 'category-modal__footer';
    footer.innerHTML = `
      <button type="button" class="btn-secondary" id="category-reset-btn">
        Volver a Auto-clasificar
      </button>
    `;

    modal.appendChild(header);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    this.modal = overlay;

    overlay.querySelector('.category-modal__close').addEventListener('click', () => this.close());
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        this.close();
      }
    });

    document.getElementById('category-reset-btn').addEventListener('click', async () => {
      if (this.currentChannelId) {
        await this.resetCategory(this.currentChannelId);
      }
    });

    return overlay;
  }

  async open(channelId, channelName, currentCategoryId) {
    this.currentChannelId = channelId;
    this.currentChannelName = channelName || '';

    await this.loadCategories();
    this.createModal();

    const titleEl = document.getElementById('category-modal-title');
    if (titleEl) {
      titleEl.textContent = this.currentChannelName ? `Categoria: ${this.currentChannelName}` : 'Seleccionar Categoria';
    }

    const body = document.getElementById('category-modal-body');
    body.innerHTML = '';

    const grid = document.createElement('div');
    grid.className = 'category-grid';

    this.categories.forEach(category => {
      const option = document.createElement('button');
      option.type = 'button';
      option.className = 'category-option';
      if (category.id === currentCategoryId) {
        option.classList.add('is-selected');
      }

      const colorClass = this.getCategoryColorClass(category.name);
      option.innerHTML = `
        <span class="category-option__icon">${category.icon || ''}</span>
        <span class="category-option__name ${colorClass}">${category.display_name_es || category.name}</span>
      `;

      option.addEventListener('click', () => this.selectCategory(category));
      grid.appendChild(option);
    });

    body.appendChild(grid);
    this.modal.hidden = false;
  }

  close() {
    if (this.modal) {
      this.modal.hidden = true;
    }
    this.currentChannelId = null;
    this.currentChannelName = '';
  }

  async selectCategory(category) {
    if (!this.currentChannelId) {
      return;
    }

    const response = await this.api.setChannelCategory(this.currentChannelId, category.name);
    if (response.ok) {
      if (typeof this.onCategoryChange === 'function') {
        this.onCategoryChange(this.currentChannelId, category);
      }
      this.close();
    }
  }

  async resetCategory(channelId) {
    const response = await this.api.resetChannelCategory(channelId);
    if (response.ok) {
      if (typeof this.onCategoryChange === 'function') {
        this.onCategoryChange(channelId, null);
      }
      this.close();
    }
  }

  getCategoryColorClass(categoryName) {
    const name = (categoryName || '').toLowerCase();
    const categoryMap = {
      gaming: 'category-color-gaming',
      technology: 'category-color-technology',
      education: 'category-color-education',
      music: 'category-color-music',
      food: 'category-color-food',
      fitness: 'category-color-health',
      health: 'category-color-health',
      travel: 'category-color-travel',
      fashion: 'category-color-fashion',
      news: 'category-color-news',
      entertainment: 'category-color-entertainment',
      vlogs: 'category-color-vlogs',
      sports: 'category-color-sports',
      art: 'category-color-art',
      science: 'category-color-science',
      lifestyle: 'category-color-lifestyle',
      business: 'category-color-business'
    };
    return categoryMap[name] || 'category-color-default';
  }
}

function createCategoryBadge(category, onClick) {
  const badge = document.createElement('button');
  badge.type = 'button';
  badge.className = 'category-badge';

  if (category) {
    const colorClass = new CategorySelector(null, null).getCategoryColorClass(category.name);
    badge.classList.add(colorClass);
    badge.innerHTML = `<span class="category-badge__icon">${category.icon || ''}</span>`;
    badge.title = category.display_name_es || category.name;
  } else {
    badge.classList.add('category-badge--empty');
    badge.innerHTML = '<span class="category-badge__icon">?</span>';
    badge.title = 'Sin categoria - Click para asignar';
  }

  if (typeof onClick === 'function') {
    badge.addEventListener('click', (e) => {
      e.stopPropagation();
      onClick(e);
    });
  }

  return badge;
}

window.CategoryManager = CategoryManager;
window.ChannelRating = ChannelRating;
window.createRatingWidget = createRatingWidget;
window.CategorySelector = CategorySelector;
window.createCategoryBadge = createCategoryBadge;
