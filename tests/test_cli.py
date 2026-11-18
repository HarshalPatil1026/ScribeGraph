import pytest

from scribegraph import run


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    """Keep a developer's real .env out of the CLI tests."""
    monkeypatch.setattr(run, "load_env", lambda: None)


def test_dry_run_from_the_command_line(site, no_llm, capsys, monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    assert run.main(["--dry-run", "--domain", "genai", "--date", "2026-11-18"]) == 0

    out = capsys.readouterr().out
    assert "[DRY RUN] nothing was written" in out
    assert "genai" in out
    assert summary.read_text().startswith("### Dry run:")
    assert not list(site.rglob("*.md"))


def test_missing_api_key_exits_with_code_2(site, capsys):
    assert run.main(["--domain", "ml"]) == 2
    assert "Groq API key is missing" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [["--date", "18-11-2026"], ["--topic", "only a topic"], ["--domain", "astrology"]],
)
def test_bad_arguments_are_rejected(argv):
    with pytest.raises(SystemExit) as exc:
        run.main(argv)
    assert exc.value.code == 2
