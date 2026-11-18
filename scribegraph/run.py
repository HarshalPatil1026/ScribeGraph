"""Command-line entry point.

Examples::

    uv run scribegraph                      # today's article, category picked automatically
    uv run scribegraph --domain nlp         # force a category
    uv run scribegraph --topic "LoRA fine-tuning explained" --domain genai
    uv run scribegraph --ainews             # weekly AI news roundup (needs a search API key)
    uv run scribegraph --dry-run            # offline preview: no API keys, nothing written
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any

from scribegraph import __version__
from scribegraph.config import CATEGORIES, NEWS_DOMAIN, PROJECT_ROOT, ConfigError, get_settings

IST = timezone(timedelta(hours=5, minutes=30))
log = logging.getLogger("scribegraph")


def today_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def _iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}; use YYYY-MM-DD") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scribegraph",
        description="Generate and publish one AI-written technical article.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples::", 1)[1],
    )
    parser.add_argument("--date", type=_iso_date, help="publication date (default: today, IST)")
    parser.add_argument(
        "--domain",
        choices=list(CATEGORIES),
        help="category to write for (default: the one that has waited longest)",
    )
    parser.add_argument("--topic", help="article topic (default: chosen by the agent)")
    parser.add_argument("--ainews", action="store_true", help="shortcut for --domain ainews")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="offline preview: no LLM or search calls and nothing is written",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # optional
        return
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv()  # a .env in the current directory, if different


def init_sentry() -> None:
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        log.warning("SENTRY_DSN is set but sentry-sdk is not installed.")
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0")),
    )


def opik_callbacks(graph: Any) -> list[Any]:
    """Trace the whole run in Opik when it is configured; never fail the run over it."""
    if not os.getenv("OPIK_API_KEY"):
        return []
    try:
        from opik.integrations.langchain import OpikTracer

        return [
            OpikTracer(
                project_name=os.getenv("OPIK_PROJECT_NAME", "scribegraph"),
                graph=graph.get_graph(xray=True),
            )
        ]
    except Exception as exc:
        log.info("Opik tracing disabled (%s).", exc)
        return []


def write_github_summary(result: dict[str, Any]) -> None:
    """Add a short Markdown summary to the GitHub Actions job page, when running there."""
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    status = "Dry run" if not result.get("published") else "Published"
    lines = [
        f"### {status}: {result.get('title', '?')}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Category | `{result.get('domain', '?')}` |",
        f"| Topic | {result.get('topic', '?')} |",
        f"| Read time | {result.get('read_time', '?')} |",
        f"| Revisions | {result.get('revision_count', 0)} |",
        f"| File | `{result.get('md_path', '?')}` |",
    ]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.topic and not (args.domain or args.ainews):
        parser.error("--topic needs --domain (or --ainews) so the topic matches its category")
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
    for noisy in ("httpx", "httpcore", "urllib3", "botocore", "boto3", "opik"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    load_env()
    get_settings.cache_clear()
    init_sentry()
    settings = get_settings()

    from scribegraph.graph.graph import graph  # import after the environment is loaded

    state: dict[str, Any] = {"date": args.date or today_ist(), "dry_run": args.dry_run}
    domain = NEWS_DOMAIN if args.ainews else args.domain
    if domain:
        state["domain"] = domain
    if args.topic:
        state["topic"] = args.topic.strip()

    rule = "=" * 60
    banner = [
        ("Date", state["date"]),
        ("Category", domain or "auto (longest-waiting category)"),
        ("Model", "none (dry run)" if args.dry_run else settings.llm.model_name),
        ("Storage", settings.storage_backend),
    ]
    print(f"\n{rule}\n  ScribeGraph {__version__}: autonomous AI article generator")
    for label, value in banner:
        print(f"  {label:<9} : {value}")
    print(rule)

    callbacks = [] if args.dry_run else opik_callbacks(graph)
    config: dict[str, Any] = {"recursion_limit": 40, "run_name": "scribegraph"}
    if callbacks:
        config["callbacks"] = callbacks

    try:
        result = graph.invoke(state, config=config)
    except ConfigError as exc:
        print(f"\nConfiguration error: {exc}", file=sys.stderr)
        return 2
    finally:
        for callback in callbacks:
            flush = getattr(callback, "flush", None)
            if callable(flush):
                flush()

    rows = [
        ("Title", result.get("title", "?")),
        ("Category", result.get("domain", "?")),
        ("Topic", result.get("topic", "?")),
        ("Read time", result.get("read_time", "?")),
        ("Revisions", result.get("revision_count", 0)),
        ("Would be" if args.dry_run else "File", result.get("md_path", "?")),
    ]
    print(f"\n{rule}")
    print("  [DRY RUN] nothing was written" if args.dry_run else "  Article published")
    for label, value in rows:
        print(f"  {label:<9} : {value}")
    print(f"{rule}\n")
    write_github_summary(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
