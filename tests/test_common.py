import pytest

from scribegraph.agents.common import (
    as_bool,
    clean_article,
    clean_tags,
    excerpt,
    extract_json,
    message_text,
    pick_stalest_domain,
    read_time,
    revision_block,
    slugify,
    strip_markdown_fence,
    unique_slug,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Gradient Boosting: From Scratch!", "gradient-boosting-from-scratch"),
        ("  Café & Crème — déjà vu  ", "cafe-creme-deja-vu"),
        ("../../etc/passwd", "etc-passwd"),
        ("", "article"),
        ("!!!", "article"),
    ],
)
def test_slugify(text, expected):
    assert slugify(text) == expected


def test_slugify_truncates_on_a_word_boundary():
    slug = slugify("word " * 40, max_length=20)
    assert len(slug) <= 20
    assert slug.startswith("word-word")
    assert not slug.endswith("-")


def test_unique_slug():
    assert unique_slug("intro", []) == "intro"
    assert unique_slug("intro", ["intro"]) == "intro-2"
    assert unique_slug("intro", ["intro", "intro-2"]) == "intro-3"


def test_read_time():
    assert read_time("") == "1 min"
    assert read_time("word " * 401) == "3 min"


def test_extract_json_handles_fences_and_chatter():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    reply = 'Sure! Here it is:\n{"approved": false, "feedback": "x"}\nHope that helps.'
    assert extract_json(reply) == {"approved": False, "feedback": "x"}


@pytest.mark.parametrize("text", ["", "not json", "[1, 2]", "{broken"])
def test_extract_json_returns_none_when_there_is_no_object(text):
    assert extract_json(text) is None


def test_as_bool():
    assert as_bool(False) is False
    assert as_bool("false") is False
    assert as_bool(" Yes ") is True
    assert as_bool(None) is True
    assert as_bool(None, default=False) is False
    assert as_bool(0) is False


def test_strip_markdown_fence_only_unwraps_markdown_fences():
    wrapped = "```markdown\n## Intro\n\n```python\nprint(1)\n```\n```"
    assert strip_markdown_fence(wrapped) == "## Intro\n\n```python\nprint(1)\n```"
    starts_and_ends_with_code = "```python\nprint(1)\n```\n\ntext\n\n```python\nprint(2)\n```"
    assert strip_markdown_fence(starts_and_ends_with_code) == starts_and_ends_with_code


def test_clean_article_drops_a_leading_title():
    assert clean_article("# Title\n\nBody text.") == "Body text.\n"
    assert clean_article("## Section\n\nBody.") == "## Section\n\nBody.\n"


def test_clean_tags():
    assert clean_tags(["Deep Learning", "deep-learning", "", "XGBoost!"]) == [
        "deep-learning",
        "xgboost",
    ]
    assert clean_tags("a, b") == ["a", "b"]
    assert clean_tags(None) == []


def test_excerpt_skips_headings_and_strips_markdown():
    md = "## Heading\n\nThis is the **first** paragraph with a [link](https://x.y).\n\nSecond."
    assert excerpt(md) == "This is the first paragraph with a link."
    assert len(excerpt("word " * 100)) <= 160


def test_message_text_handles_content_blocks():
    class Message:
        content = [
            {"type": "text", "text": "Hello "},
            {"type": "reasoning", "text": "hidden"},
            "world",
        ]

    assert message_text(Message()) == "Hello world"


def test_pick_stalest_domain_prefers_never_published_categories():
    # Regression: the original sorted the string "Never" after real dates.
    last = {"ml": "2026-03-02", "dl": "2026-01-15", "nlp": None, "cv": None}
    assert pick_stalest_domain(last) == "nlp"


def test_pick_stalest_domain_picks_the_oldest_date():
    assert pick_stalest_domain({"ml": "2026-03-02", "dl": "2026-01-15"}) == "dl"


def test_pick_stalest_domain_needs_choices():
    with pytest.raises(ValueError):
        pick_stalest_domain({})


def test_revision_block():
    assert revision_block({}) == ""
    block = revision_block({"validator_feedback": "Add code.", "content": "Old draft."})
    assert "Add code." in block
    assert "Old draft." in block
