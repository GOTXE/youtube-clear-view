// Infinite carousel component for video lists.

class Carousel {
  constructor(containerId, fetchFunction, options = {}) {
    this.containerId = containerId;
    this.fetchFunction = fetchFunction;
    this.options = {
      gap: 20,
      showControls: true,
      theme: null,
      ...options
    };

    this.container = null;
    this.track = null;
    this.leftControl = null;
    this.rightControl = null;
    this.loadingIndicator = null;
    this.sentinel = null;
    this.offset = 0;
    this.limit = (window.APP_CONFIG && window.APP_CONFIG.VIDEOS_PER_LOAD) || 20;
    this.hasMore = true;
    this.loading = false;
    this.skeletons = [];

    this.thumbObserver = null;
    this.scrollObserver = null;

    this.onLeftClick = () => this.scrollLeft();
    this.onRightClick = () => this.scrollRight();
    this.onTrackKeydown = event => this.handleTrackKeydown(event);
    this.onResize = () => this.updateCardSizing();
  }

  async init() {
    this.container = document.getElementById(this.containerId);
    if (!this.container) {
      return;
    }

    this.container.innerHTML = '';
    this.render();
    await this.loadMore();
    this.updateCardSizing();
    window.addEventListener('resize', this.onResize);
  }

  render() {
    if (!this.container) {
      return;
    }

    const carousel = document.createElement('div');
    carousel.className = 'carousel';
    if (this.options.theme) {
      carousel.dataset.themeColor = this.options.theme;
    }

    if (this.options.showControls) {
      this.leftControl = document.createElement('button');
      this.leftControl.type = 'button';
      this.leftControl.className = 'carousel-control';
      this.leftControl.textContent = '◀';
      this.leftControl.setAttribute('aria-label', 'Scroll left');
      this.leftControl.addEventListener('click', this.onLeftClick);
      carousel.appendChild(this.leftControl);
    }

    this.track = document.createElement('div');
    this.track.className = 'carousel-track';
    this.track.tabIndex = 0;
    this.track.setAttribute('aria-label', 'Video carousel');
    this.track.addEventListener('keydown', this.onTrackKeydown);

    const gapToken = this.options.gap === 20
      ? 'var(--space-5)'
      : this.options.gap === 16
        ? 'var(--space-4)'
        : null;
    if (gapToken) {
      this.track.style.gap = gapToken;
    }

    carousel.appendChild(this.track);

    if (this.options.showControls) {
      this.rightControl = document.createElement('button');
      this.rightControl.type = 'button';
      this.rightControl.className = 'carousel-control';
      this.rightControl.textContent = '▶';
      this.rightControl.setAttribute('aria-label', 'Scroll right');
      this.rightControl.addEventListener('click', this.onRightClick);
      carousel.appendChild(this.rightControl);
    }

    this.loadingIndicator = document.createElement('div');
    this.loadingIndicator.className = 'spinner';
    this.loadingIndicator.hidden = true;

    this.sentinel = document.createElement('div');
    this.sentinel.setAttribute('aria-hidden', 'true');

    this.track.appendChild(this.loadingIndicator);
    this.track.appendChild(this.sentinel);

    this.container.appendChild(carousel);

    this.setupObservers();
  }

  setupObservers() {
    if (!this.track || !this.sentinel) {
      return;
    }

    this.thumbObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) {
          return;
        }

        const target = entry.target;
        const src = target.getAttribute('data-src');
        if (src) {
          target.src = src;
          target.removeAttribute('data-src');
        }
        this.thumbObserver.unobserve(target);
      });
    }, { root: this.track, rootMargin: '150px' });

    this.scrollObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          this.loadMore();
        }
      });
    }, { root: this.track, rootMargin: '200px' });

    this.scrollObserver.observe(this.sentinel);
  }

  async loadMore() {
    if (this.loading || !this.hasMore || !this.fetchFunction) {
      return;
    }

    this.loading = true;
    this.loadingIndicator.hidden = false;
    this.renderSkeletons(3);

    let payload = null;
    try {
      payload = await this.fetchFunction(this.offset, this.limit);
    } catch (error) {
      payload = null;
    }

    const data = payload && payload.videos ? payload : payload && payload.data ? payload.data : null;

    this.clearSkeletons();

    if (!data || !Array.isArray(data.videos)) {
      this.loadingIndicator.hidden = true;
      this.loading = false;
      return;
    }

    if (!data.videos.length && this.offset === 0) {
      this.renderEmptyState();
    }

    data.videos.forEach(item => {
      const card = this.renderVideoCard(item);
      if (card) {
        this.track.insertBefore(card, this.loadingIndicator);
      }
    });

    this.hasMore = Boolean(data.has_more);
    if (typeof data.next_offset === 'number') {
      this.offset = data.next_offset;
    } else {
      this.offset = this.offset + this.limit;
    }

    if (!this.hasMore && this.sentinel) {
      this.scrollObserver.unobserve(this.sentinel);
      this.sentinel.remove();
    }

    this.updateCardSizing();
    this.loadingIndicator.hidden = true;
    this.loading = false;
  }

  renderSkeletons(count) {
    this.clearSkeletons();
    if (!this.track) {
      return;
    }

    for (let i = 0; i < count; i += 1) {
      const skeleton = document.createElement('div');
      skeleton.className = 'video-card';
      skeleton.setAttribute('aria-hidden', 'true');
      skeleton.style.opacity = '0.6';

      const thumb = document.createElement('div');
      thumb.className = 'video-card__thumb';
      thumb.style.background = 'var(--border)';

      const body = document.createElement('div');
      body.className = 'video-card__body';

      const line = document.createElement('div');
      line.style.height = '16px';
      line.style.borderRadius = 'var(--radius-2)';
      line.style.background = 'var(--border)';

      body.appendChild(line);
      skeleton.appendChild(thumb);
      skeleton.appendChild(body);

      this.track.insertBefore(skeleton, this.loadingIndicator);
      this.skeletons.push(skeleton);
    }
  }

  clearSkeletons() {
    this.skeletons.forEach(node => node.remove());
    this.skeletons = [];
  }

  renderEmptyState() {
    if (!this.track) {
      return;
    }

    const message = document.createElement('p');
    message.className = 'caption';
    message.textContent = 'No videos to display yet.';
    this.track.insertBefore(message, this.loadingIndicator);
  }

  renderVideoCard(item) {
    const video = item.video || {};
    const channel = item.channel || {};
    const watched = Boolean(item.watched);

    const card = document.createElement('article');
    card.className = 'video-card';
    card.tabIndex = 0;
    card.setAttribute('role', 'button');

    const title = video.title || 'Untitled video';
    card.setAttribute('aria-label', `Open ${title}`);

    const thumb = document.createElement('div');
    thumb.className = 'video-card__thumb';

    if (video.thumbnail_url) {
      const image = document.createElement('img');
      image.className = 'video-card__thumb-image';
      image.alt = title;
      image.loading = 'lazy';
      image.setAttribute('data-src', video.thumbnail_url);
      if (this.thumbObserver) {
        this.thumbObserver.observe(image);
      }
      thumb.appendChild(image);
    }

    const body = document.createElement('div');
    body.className = 'video-card__body';

    const titleEl = document.createElement('h3');
    titleEl.className = 'video-card__title';
    titleEl.textContent = title;

    const channelEl = document.createElement('p');
    channelEl.className = 'video-card__meta';
    channelEl.textContent = channel.title || 'Unknown channel';

    const details = document.createElement('p');
    details.className = 'video-card__meta';

    const durationText = this.formatDuration(video.duration);
    if (durationText) {
      details.appendChild(document.createTextNode(durationText));
    }

    if (watched) {
      this.applyWatchedState(card, details, Boolean(durationText));
    }

    body.appendChild(titleEl);
    body.appendChild(channelEl);
    body.appendChild(details);

    card.appendChild(thumb);
    card.appendChild(body);

    const handleActivate = () => {
      const videoId = video.youtube_video_id;
      if (videoId) {
        const baseUrl = window.APP_CONFIG && window.APP_CONFIG.YOUTUBE_BASE_URL
          ? window.APP_CONFIG.YOUTUBE_BASE_URL
          : 'https://www.youtube.com';
        const url = `${baseUrl}/watch?v=${videoId}`;
        window.open(url, '_blank', 'noopener');
      }

      if (card.dataset.watched !== 'true') {
        this.markWatched(video, card, details, Boolean(durationText));
      }
    };

    card.addEventListener('click', handleActivate);
    card.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        handleActivate();
      }
    });

    return card;
  }

  applyWatchedState(card, detailsElement, hasDuration) {
    card.dataset.watched = 'true';
    card.classList.add('video-card--watched');
    card.style.transition = 'opacity 0.3s ease';
    card.style.opacity = '0.7';

    const watchedTag = document.createElement('span');
    watchedTag.textContent = hasDuration ? ' • Watched' : 'Watched';
    watchedTag.style.color = 'var(--success)';
    detailsElement.appendChild(watchedTag);
  }

  async markWatched(video, card, detailsElement, hasDuration) {
    const api = window.appApiClient;
    if (!api || !video.id) {
      return;
    }

    const deviceId = typeof window.getDeviceId === 'function' ? window.getDeviceId() : null;
    const response = await api.markAsWatched(video.id, deviceId || undefined);
    if (!response.ok) {
      return;
    }

    if (card.dataset.watched !== 'true') {
      this.applyWatchedState(card, detailsElement, hasDuration || detailsElement.textContent.length > 0);
    }
  }

  formatDuration(seconds) {
    if (typeof seconds !== 'number' || Number.isNaN(seconds)) {
      return '';
    }

    const total = Math.max(0, Math.floor(seconds));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;

    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    return `${minutes}:${String(secs).padStart(2, '0')}`;
  }

  handleTrackKeydown(event) {
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      this.scrollLeft();
    }

    if (event.key === 'ArrowRight') {
      event.preventDefault();
      this.scrollRight();
    }
  }

  getVisibleCount() {
    const body = document.body;
    if (!body) {
      return 3;
    }

    if (body.classList.contains('device-tv')) {
      return 5;
    }

    if (body.classList.contains('device-tablet')) {
      return 3;
    }

    if (body.classList.contains('device-mobile')) {
      return 2;
    }

    return 4;
  }

  updateCardSizing() {
    if (!this.track) {
      return;
    }

    const count = this.getVisibleCount();
    const cards = this.track.querySelectorAll('.video-card');
    cards.forEach(card => {
      card.style.flex = `0 0 ${100 / count}%`;
    });
  }

  scrollLeft() {
    if (!this.track) {
      return;
    }

    const amount = this.track.clientWidth;
    this.track.scrollBy({ left: -amount, behavior: 'smooth' });
  }

  scrollRight() {
    if (!this.track) {
      return;
    }

    const amount = this.track.clientWidth;
    this.track.scrollBy({ left: amount, behavior: 'smooth' });
  }

  destroy() {
    if (this.leftControl) {
      this.leftControl.removeEventListener('click', this.onLeftClick);
    }

    if (this.rightControl) {
      this.rightControl.removeEventListener('click', this.onRightClick);
    }

    if (this.track) {
      this.track.removeEventListener('keydown', this.onTrackKeydown);
    }

    window.removeEventListener('resize', this.onResize);

    if (this.thumbObserver) {
      this.thumbObserver.disconnect();
    }

    if (this.scrollObserver) {
      this.scrollObserver.disconnect();
    }

    if (this.container) {
      this.container.innerHTML = '';
    }
  }
}

window.Carousel = Carousel;
