// Lightweight i18n helper for static UI copy.

(() => {
  const STORAGE_KEY = 'ytcv_lang';
  const SUPPORTED = ['en', 'es'];

  function interpolate(template, vars) {
    if (!vars) {
      return template;
    }
    return template.replace(/\{(\w+)\}/g, (match, key) => {
      if (typeof vars[key] === 'undefined') {
        return match;
      }
      return String(vars[key]);
    });
  }

  function resolveLanguage() {
    const params = new URLSearchParams(window.location.search);
    const override = (params.get('lang') || '').toLowerCase();
    if (SUPPORTED.includes(override)) {
      try {
        localStorage.setItem(STORAGE_KEY, override);
      } catch (error) {
        // Ignore storage errors.
      }
      return override;
    }

    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (SUPPORTED.includes(stored)) {
        return stored;
      }
    } catch (error) {
      // Ignore storage errors.
    }

    const browserLang = (navigator.language || '').toLowerCase();
    if (browserLang.startsWith('es')) {
      return 'es';
    }

    return 'en';
  }

  const language = resolveLanguage();
  document.documentElement.setAttribute('lang', language);

  const loadJson = async path => {
    try {
      const response = await fetch(path);
      if (!response.ok) {
        return {};
      }
      return await response.json();
    } catch (error) {
      return {};
    }
  };

  window.ytcvI18n = {
    language,
    t: key => key
  };

  window.ytcvI18nReady = (async () => {
    const base = await loadJson('i18n/en.json');
    const localized = language === 'en' ? {} : await loadJson(`i18n/${language}.json`);
    const translations = { ...base, ...localized };

    window.ytcvI18n = {
      language,
      t: (key, vars) => {
        const template = translations[key] || base[key] || key;
        return interpolate(template, vars);
      }
    };
  })();
})();
