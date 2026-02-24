import { useEffect } from 'react';

const GOOGLE_TRANSLATE_URL = 'https://translate.googleapis.com/translate_a/single';
const CACHE_PREFIX = 'astrobot_ui_i18n_cache_v1:';
const MAX_TRANSLATABLE_LENGTH = 220;

const CYRILLIC_RE = /[А-Яа-яЁё]/;
const SPACE_RE = /\s+/g;
const TECH_TOKEN_RE = /^[\d\s.,:;!?()[\]{}\-+/*%#@&|_=<>~"'`]+$/;
const SKIP_PARENT_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'CODE', 'PRE', 'TEXTAREA']);
const ATTRS_TO_TRANSLATE = ['placeholder', 'aria-label', 'title'];

const EXACT_OVERRIDES = {
  en: {
    'Назад': 'Back',
    'Загрузка...': 'Loading...',
    'Профиль': 'Profile',
    'Таро': 'Tarot',
    'Нумерология': 'Numerology',
    'Натальная карта': 'Natal chart',
    'Расчёты появятся здесь': 'Calculations will appear here',
    'Расклады появятся здесь': 'Spreads will appear here',
    'Открыть архетип разума →': 'Reveal mind archetype →',
    'Изменить': 'Change',
    'Премиум': 'Premium',
    'Сегодня': 'Today',
    'Вчера': 'Yesterday',
    'Открыть Mini App по кнопке ниже.': 'Open the Mini App using the button below.',
    'Для работы используйте Mini App.': 'Use the Mini App to continue.',
    'Подсказка': 'Hint',
    'Удалить профиль и всю историю? Это действие нельзя отменить.': 'Delete the profile and all history? This action cannot be undone.',
    'Не удалось удалить профиль.': 'Failed to delete profile.',
  },
};

const languageCaches = new Map();
const inflightTranslations = new Map();

function normalizeLang(raw) {
  const source = String(raw || '').trim().toLowerCase().replace('_', '-');
  if (!source) return 'ru';
  const base = source.split('-')[0];
  return /^[a-z]{2,3}$/.test(base) ? base : 'ru';
}

function getLangCache(lang) {
  const normalized = normalizeLang(lang);
  if (languageCaches.has(normalized)) {
    return languageCaches.get(normalized);
  }

  let parsed = {};
  try {
    parsed = JSON.parse(localStorage.getItem(`${CACHE_PREFIX}${normalized}`) || '{}') || {};
  } catch {
    parsed = {};
  }

  const cache = new Map(Object.entries(parsed).filter(([k, v]) => k && typeof v === 'string'));
  languageCaches.set(normalized, cache);
  return cache;
}

function persistLangCache(lang) {
  const normalized = normalizeLang(lang);
  const cache = languageCaches.get(normalized);
  if (!cache) return;
  try {
    localStorage.setItem(`${CACHE_PREFIX}${normalized}`, JSON.stringify(Object.fromEntries(cache.entries())));
  } catch {
    // ignore storage quota/privacy mode errors
  }
}

function looksTranslatable(text) {
  const value = String(text || '').replace(SPACE_RE, ' ').trim();
  if (!value) return false;
  if (!CYRILLIC_RE.test(value)) return false;
  if (value.length < 2 || value.length > MAX_TRANSLATABLE_LENGTH) return false;
  if (TECH_TOKEN_RE.test(value)) return false;
  if (/^https?:\/\//i.test(value)) return false;
  return true;
}

async function fetchGoogleTranslation(text, targetLang) {
  const response = await fetch(
    `${GOOGLE_TRANSLATE_URL}?${new URLSearchParams({
      client: 'gtx',
      sl: 'auto',
      tl: targetLang,
      dt: 't',
      q: text,
    })}`,
    { method: 'GET' }
  );

  if (!response.ok) {
    throw new Error(`Google translate failed: ${response.status}`);
  }

  const payload = await response.json();
  if (!Array.isArray(payload) || !Array.isArray(payload[0])) {
    return text;
  }

  const chunks = [];
  for (const item of payload[0]) {
    if (Array.isArray(item) && typeof item[0] === 'string') {
      chunks.push(item[0]);
    }
  }
  return (chunks.join('').trim() || text);
}

async function translateUiString(text, lang) {
  const targetLang = normalizeLang(lang);
  if (targetLang === 'ru') return text;
  if (!looksTranslatable(text)) return text;

  const exact = EXACT_OVERRIDES[targetLang]?.[text];
  if (exact) return exact;

  const cache = getLangCache(targetLang);
  const cached = cache.get(text);
  if (cached) return cached;

  const key = `${targetLang}::${text}`;
  if (inflightTranslations.has(key)) {
    return inflightTranslations.get(key);
  }

  const promise = fetchGoogleTranslation(text, targetLang)
    .then((translated) => {
      cache.set(text, translated);
      persistLangCache(targetLang);
      return translated;
    })
    .catch(() => text)
    .finally(() => {
      inflightTranslations.delete(key);
    });

  inflightTranslations.set(key, promise);
  return promise;
}

function shouldSkipElement(el) {
  if (!el) return true;
  if (el.closest('[data-no-ui-translate="true"]')) return true;
  if (el.isContentEditable) return true;

  let current = el;
  while (current) {
    if (SKIP_PARENT_TAGS.has(current.tagName)) return true;
    current = current.parentElement;
  }
  return false;
}

async function processTextNode(node, lang, isActive) {
  if (!node || !node.parentElement) return;
  if (shouldSkipElement(node.parentElement)) return;

  const original = node.nodeValue || '';
  if (!looksTranslatable(original)) return;

  const translated = await translateUiString(original, lang);
  if (!isActive()) return;

  if ((node.nodeValue || '') === original && translated && translated !== original) {
    node.nodeValue = translated;
  }
}

async function processElementAttributes(el, lang, isActive) {
  if (!el || shouldSkipElement(el)) return;
  for (const attr of ATTRS_TO_TRANSLATE) {
    const original = el.getAttribute?.(attr);
    if (!looksTranslatable(original)) continue;
    const translated = await translateUiString(original, lang);
    if (!isActive()) return;
    if (el.getAttribute(attr) === original && translated && translated !== original) {
      el.setAttribute(attr, translated);
    }
  }
}

function collectNodes(root) {
  const textNodes = [];
  const elements = [];

  if (!(root instanceof Node)) return { textNodes, elements };

  if (root.nodeType === Node.TEXT_NODE) {
    textNodes.push(root);
    return { textNodes, elements };
  }

  if (!(root instanceof Element)) {
    return { textNodes, elements };
  }

  elements.push(root);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ALL);
  let current = walker.nextNode();
  while (current) {
    if (current.nodeType === Node.TEXT_NODE) {
      textNodes.push(current);
    } else if (current.nodeType === Node.ELEMENT_NODE) {
      elements.push(current);
    }
    current = walker.nextNode();
  }
  return { textNodes, elements };
}

async function translateSubtree(root, lang, isActive) {
  const { textNodes, elements } = collectNodes(root);
  for (const el of elements) {
    // Fire-and-forget is fine; dedupe/cache prevents a request storm.
    processElementAttributes(el, lang, isActive);
  }
  for (const textNode of textNodes) {
    processTextNode(textNode, lang, isActive);
  }
}

export function useUiAutoTranslate(languageCode) {
  useEffect(() => {
    const lang = normalizeLang(languageCode);
    if (lang === 'ru') return undefined;

    let active = true;
    const isActive = () => active;
    const root = document.getElementById('root') || document.body;
    if (!root) return undefined;

    translateSubtree(root, lang, isActive);

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'characterData' && mutation.target?.nodeType === Node.TEXT_NODE) {
          processTextNode(mutation.target, lang, isActive);
          continue;
        }

        if (mutation.type === 'attributes' && mutation.target instanceof Element) {
          processElementAttributes(mutation.target, lang, isActive);
          continue;
        }

        if (mutation.type === 'childList') {
          mutation.addedNodes?.forEach((node) => {
            translateSubtree(node, lang, isActive);
          });
        }
      }
    });

    observer.observe(root, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ATTRS_TO_TRANSLATE,
    });

    return () => {
      active = false;
      observer.disconnect();
    };
  }, [languageCode]);
}

export function translateFixedUiText(text, languageCode) {
  const lang = normalizeLang(languageCode);
  if (lang === 'ru') return text;
  return EXACT_OVERRIDES[lang]?.[text] || text;
}
