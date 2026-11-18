/**
 * blogs-data.js — article registry shared by every page.
 *
 * The Python pipeline keeps one index per category at blogs/<category>/articles.json
 * (newest first) next to the Markdown files. They are loaded from:
 *   - window.CONFIG.R2_PUBLIC_URL when it is set (Cloudflare R2 storage), otherwise
 *   - this website itself (local storage, e.g. GitHub Pages).
 *
 * articles.json entry:
 *   { id, category, title, description, date: "YYYY-MM-DD", tags: [], readTime, file }
 */

const SITE_NAME = 'ScribeGraph';

/* ── Category metadata (keep in sync with scribegraph/config/categories.py) ── */
const CATEGORY_META = {
  ml: {
    label: 'Machine Learning',
    shortLabel: 'ML',
    description: 'Algorithms, theory, and applied ML from fundamentals to production.',
    icon: '🧠',
    color: '#7c6af7',
    bgColor: 'rgba(124, 106, 247, 0.12)',
  },
  dl: {
    label: 'Deep Learning',
    shortLabel: 'DL',
    description: 'Neural networks, architectures, training tricks, and modern DL research.',
    icon: '🔬',
    color: '#4fc8b8',
    bgColor: 'rgba(79, 200, 184, 0.12)',
  },
  nlp: {
    label: 'Natural Language Processing',
    shortLabel: 'NLP',
    description: 'Text processing, transformers, LLMs, and language understanding.',
    icon: '📝',
    color: '#e879a0',
    bgColor: 'rgba(232, 121, 160, 0.12)',
  },
  cv: {
    label: 'Computer Vision',
    shortLabel: 'CV',
    description: 'Image processing, object detection, segmentation, and visual AI.',
    icon: '👁️',
    color: '#f59e0b',
    bgColor: 'rgba(245, 158, 11, 0.12)',
  },
  genai: {
    label: 'Generative AI',
    shortLabel: 'Gen AI',
    description: 'Diffusion models, LLMs, RAG, agents, and the frontier of AI generation.',
    icon: '✨',
    color: '#a78bfa',
    bgColor: 'rgba(167, 139, 250, 0.12)',
  },
  ainews: {
    label: 'AI News',
    shortLabel: 'AI News',
    description: 'Breaking developments, model releases, and industry analysis.',
    icon: '📡',
    color: '#34d399',
    bgColor: 'rgba(52, 211, 153, 0.12)',
  },
  statistics: {
    label: 'Statistics for AI',
    shortLabel: 'Stats',
    description: 'Probability, statistical tests, distributions, and the math behind ML.',
    icon: '📊',
    color: '#fb923c',
    bgColor: 'rgba(251, 146, 60, 0.12)',
  },
};

const ALL_CATEGORIES = Object.keys(CATEGORY_META);

const FALLBACK_META = {
  label: 'Article', shortLabel: 'Post', description: '', icon: '📄',
  color: '#a89cf7', bgColor: 'rgba(124, 106, 247, 0.12)',
};

function categoryMeta(cat) {
  return CATEGORY_META[cat] || FALLBACK_META;
}

/* ── Where article files live: the R2 bucket if configured, else this site ── */
const CONTENT_BASE = (() => {
  const url = (typeof window !== 'undefined' && window.CONFIG && window.CONFIG.R2_PUBLIC_URL) || '';
  return url ? String(url).replace(/\/+$/, '') : '.';
})();

/* ── Loading (one request per category, shared by every caller) ── */
const _cache = {};

function loadCategoryArticles(cat) {
  if (!_cache[cat]) {
    _cache[cat] = (async () => {
      try {
        const res = await fetch(`${CONTENT_BASE}/blogs/${cat}/articles.json`, { cache: 'no-cache' });
        if (!res.ok) return [];
        const text = await res.text();
        if (!text.trim()) return [];
        const data = JSON.parse(text);
        return Array.isArray(data) ? data.filter(a => a && typeof a === 'object') : [];
      } catch (_) {
        return [];
      }
    })();
  }
  return _cache[cat];
}

/**
 * Articles in a category, sorted by date.
 * @param {string} cat  - category key
 * @param {string} sort - 'newest' | 'oldest'
 */
async function getBlogsByCategory(cat, sort = 'newest') {
  const articles = await loadCategoryArticles(cat);
  return [...articles].sort((a, b) =>
    sort === 'newest'
      ? new Date(b.date) - new Date(a.date)
      : new Date(a.date) - new Date(b.date)
  );
}

/** One article's metadata by id ("blogs/<category>/<slug>.md"). */
async function getBlogById(id) {
  const parts = id.split('/');
  if (parts.length >= 3 && CATEGORY_META[parts[1]]) {
    const found = (await loadCategoryArticles(parts[1])).find(a => a.id === id || a.file === id);
    if (found) return found;
  }
  for (const cat of ALL_CATEGORIES) {
    const found = (await loadCategoryArticles(cat)).find(a => a.id === id || a.file === id);
    if (found) return found;
  }
  return null;
}

/** The n most recent articles across all categories. */
async function getRecentBlogs(n = 6) {
  const all = (await Promise.all(ALL_CATEGORIES.map(loadCategoryArticles))).flat();
  all.sort((a, b) => new Date(b.date) - new Date(a.date));
  return all.slice(0, n);
}

/** Total number of published articles. */
async function getTotalCount() {
  const all = await Promise.all(ALL_CATEGORIES.map(loadCategoryArticles));
  return all.reduce((sum, arr) => sum + arr.length, 0);
}

/* ── Helpers ── */
function formatDate(dateStr) {
  if (!dateStr) return '';
  const [y, m, d] = String(dateStr).split('-').map(Number);
  const date = new Date(y, (m || 1) - 1, d || 1);
  return isNaN(date) ? String(dateStr) : date.toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
}

/** Escape text before putting it into HTML (titles, tags and descriptions come from an LLM). */
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}
