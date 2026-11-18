"""Blog categories ("domains").

Keep this list in sync with ``CATEGORY_META`` in ``scribegraph/web/js/blogs-data.js``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    short_label: str


CATEGORIES: dict[str, Category] = {
    c.key: c
    for c in (
        Category("ml", "Machine Learning", "ML"),
        Category("dl", "Deep Learning", "DL"),
        Category("statistics", "Statistics for AI", "Stats"),
        Category("nlp", "Natural Language Processing", "NLP"),
        Category("cv", "Computer Vision", "CV"),
        Category("genai", "Generative AI", "Gen AI"),
        Category("ainews", "AI News", "AI News"),
    )
}

NEWS_DOMAIN = "ainews"

# Categories the tutorial agent rotates through (everything except the news feed).
TUTORIAL_DOMAINS: tuple[str, ...] = tuple(key for key in CATEGORIES if key != NEWS_DOMAIN)


def category_label(key: str) -> str:
    """Human-readable label for a category key (falls back to the key itself)."""
    category = CATEGORIES.get(key)
    return category.label if category else key
