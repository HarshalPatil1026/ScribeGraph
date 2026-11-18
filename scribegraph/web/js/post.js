/**
 * post.js — article page: loads the Markdown, sanitises it and renders it.
 * The article id comes from the URL hash (#id=blogs/ml/slug.md).
 */
document.addEventListener('DOMContentLoaded', () => {
    initNav();
    loadPost();
    initReadingProgress();
});

// Opening another article by changing only the URL hash should load that article.
const initialPostId = new URLSearchParams(window.location.hash.replace(/^#/, '')).get('id');
window.addEventListener('hashchange', () => {
    if (getHashParam('id') !== initialPostId) window.location.reload();
});

/* ── Parse hash params ── */
function getHashParam(key) {
    const hash = window.location.hash.replace(/^#/, '');
    return new URLSearchParams(hash).get(key);
}

/* ── Nav ── */
function initNav() {
    const navbar = document.getElementById('navbar');
    const hamburger = document.getElementById('hamburger');
    const navLinks = document.getElementById('navLinks');

    window.addEventListener('scroll', () => {
        navbar.classList.toggle('scrolled', window.scrollY > 30);
    });

    hamburger?.addEventListener('click', () => {
        hamburger.classList.toggle('open');
        navLinks.classList.toggle('open');
    });
}

/* ── Reading progress ── */
function initReadingProgress() {
    const bar = document.getElementById('readingProgress');
    if (!bar) return;
    window.addEventListener('scroll', () => {
        const doc = document.documentElement;
        const scrollTop = doc.scrollTop || document.body.scrollTop;
        const scrollHeight = doc.scrollHeight - doc.clientHeight;
        bar.style.width = scrollHeight > 0 ? `${(scrollTop / scrollHeight) * 100}%` : '0%';
    });
}

/* ── Load post ── */
async function loadPost() {
    const id = getHashParam('id');
    const contentEl = document.getElementById('postContent');

    if (!id) {
        window.location.replace('index.html');
        return;
    }

    const blog = await getBlogById(id);
    if (!blog) {
        document.getElementById('postTitleH1').textContent = 'Article not found';
        const crumb = document.getElementById('postTitle');
        if (crumb) crumb.textContent = 'Not found';
        showError('Post not found. It may have been removed or the link is incorrect.', '', contentEl);
        return;
    }
    const meta = categoryMeta(blog.category);

    document.title = `${blog.title} — ${SITE_NAME}`;
    const description = document.querySelector('meta[name="description"]');
    if (description && blog.description) description.setAttribute('content', blog.description);

    // Breadcrumb
    const catLink = document.getElementById('catLink');
    if (catLink) {
        catLink.textContent = meta.label;
        catLink.href = `category.html#cat=${encodeURIComponent(blog.category)}`;
    }
    const postTitleSpan = document.getElementById('postTitle');
    if (postTitleSpan) postTitleSpan.textContent = blog.title;

    // Header
    document.getElementById('postTitleH1').textContent = blog.title;
    document.getElementById('postDate').textContent = formatDate(blog.date);

    const catBadge = document.getElementById('postCatBadge');
    if (catBadge) {
        catBadge.textContent = meta.shortLabel;
        catBadge.className = `post-cat-badge badge-${blog.category}`;
    }

    const readTimeEl = document.getElementById('postReadTime');
    if (readTimeEl && blog.readTime) readTimeEl.textContent = `📖 ${blog.readTime} read`;

    document.querySelectorAll('.nav-link[href]').forEach(link => {
        if (link.href.includes(`cat=${blog.category}`)) link.classList.add('active');
    });

    const backBtn = document.getElementById('backToCat');
    if (backBtn) {
        backBtn.href = `category.html#cat=${encodeURIComponent(blog.category)}`;
        backBtn.textContent = `← Back to ${meta.shortLabel}`;
    }

    const tagsEl = document.getElementById('postTags');
    if (tagsEl && Array.isArray(blog.tags) && blog.tags.length) {
        tagsEl.innerHTML = blog.tags.map(t => `<span class="post-tag">#${escapeHtml(t)}</span>`).join('');
    }

    const url = `${CONTENT_BASE}/${blog.file}`;
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        renderMarkdown(await response.text(), contentEl);
        buildTOC();
    } catch (err) {
        showError('Could not load the article file.', url, contentEl);
        console.error('Failed to load blog post:', err);
    }
}

/* ── Render Markdown (sanitised: articles are LLM output built from web search results) ── */
function renderMarkdown(mdText, container) {
    // The page header already shows the title, so drop a leading "# Title" line.
    const body = mdText.replace(/^\s*#[ \t]+[^\n]*\n+/, '');
    const html = marked.parse(body, { gfm: true, breaks: true });

    if (window.DOMPurify) {
        container.innerHTML = DOMPurify.sanitize(html);
    } else {
        // Fail safe: never insert unsanitised HTML.
        container.innerHTML = `<pre>${escapeHtml(body)}</pre>`;
    }

    addHeadingIds(container);

    container.querySelectorAll('a[href^="http"]').forEach(a => {
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
    });

    if (window.hljs) {
        container.querySelectorAll('pre code').forEach(block => hljs.highlightElement(block));
    }

    container.querySelectorAll('pre').forEach(pre => {
        const btn = document.createElement('button');
        btn.className = 'copy-btn';
        btn.type = 'button';
        btn.textContent = 'Copy';
        btn.style.cssText = `
      position:absolute; top:10px; right:12px;
      background:rgba(124,106,247,0.15); color:#a89cf7;
      border:1px solid rgba(124,106,247,0.25); border-radius:6px;
      padding:3px 10px; font-size:0.75rem; cursor:pointer;
      font-family:var(--font-sans); transition:all 0.15s;
    `;
        btn.addEventListener('click', () => {
            const code = pre.querySelector('code');
            navigator.clipboard.writeText(code?.textContent || '').then(() => {
                btn.textContent = 'Copied!';
                setTimeout(() => (btn.textContent = 'Copy'), 2000);
            });
        });
        pre.style.position = 'relative';
        pre.appendChild(btn);
    });
}

/* Give every heading a unique id for the table of contents. */
function addHeadingIds(container) {
    const used = new Set();
    container.querySelectorAll('h1, h2, h3, h4').forEach(h => {
        const base = h.textContent.toLowerCase().trim()
            .replace(/[^\w]+/g, '-').replace(/^-+|-+$/g, '') || 'section';
        let id = base;
        let n = 2;
        while (used.has(id) || document.getElementById(id)) id = `${base}-${n++}`;
        used.add(id);
        h.id = id;
    });
}

/* ── Table of contents ── */
function buildTOC() {
    const content = document.getElementById('postContent');
    const tocNav = document.getElementById('tocNav');
    if (!content || !tocNav) return;

    const headings = content.querySelectorAll('h2, h3, h4');
    if (headings.length === 0) return;

    tocNav.innerHTML = '';

    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                tocNav.querySelectorAll('.toc-link').forEach(l => l.classList.remove('active'));
                const activeLink = tocNav.querySelector(`[data-target="${CSS.escape(entry.target.id)}"]`);
                activeLink?.classList.add('active');
            }
        });
    }, { rootMargin: '-20% 0px -70% 0px' });

    headings.forEach(h => {
        const level = h.tagName.toLowerCase();
        const link = document.createElement('a');
        link.href = `#${h.id}`;
        link.setAttribute('data-target', h.id);
        link.textContent = h.textContent;
        link.className = `toc-link level-${level}`;
        link.addEventListener('click', e => {
            e.preventDefault();
            document.getElementById(h.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
        tocNav.appendChild(link);
        observer.observe(h);
    });
}

/* ── Error state ── */
function showError(message, url, container) {
    if (!container) return;
    const detail = url
        ? `<br><small>Tried: <code>${escapeHtml(url)}</code></small>
           <br><small>Check that the file exists and, if you use R2, that R2_PUBLIC_URL in js/config.js is correct.</small>`
        : '';
    container.innerHTML = `
    <div style="padding:40px;text-align:center;color:var(--text-muted)">
      <div style="font-size:2.5rem;margin-bottom:16px">⚠️</div>
      <h3 style="color:var(--text-secondary);margin-bottom:12px">Unable to load article</h3>
      <p style="line-height:1.7">${escapeHtml(message)}${detail}</p>
    </div>`;
}
