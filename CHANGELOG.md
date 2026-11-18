# Changelog

All notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-11-18

First release of **ScribeGraph**, built on [BlogBoard](https://github.com/KalyanM45/BlogBoard-AI-Blog-Generator) (commit `8b743e2`, MIT License).

### Renamed

- Project, Python package (`blogboard` → `scribegraph`), command-line tool (`scribegraph`), website branding and page titles.
- Removed the original author's Google Analytics tag, Cloudflare R2 bucket URL and social links from the website.

### Fixed

- **AI News could not run.** `create_react_agent(state_modifier=...)` raises a `TypeError` on LangGraph 1.0. The research agent now uses `langchain.agents.create_agent(system_prompt=...)`, covered by a regression test.
- **The default model was retired.** Groq shut down `llama-3.3-70b-versatile` for free and developer accounts on 16 August 2026. The default is now `openai/gpt-oss-120b`, and any Groq model can be set with `llm__model_name`.
- **Tavily searches were rejected.** The API key is now sent as an `Authorization: Bearer` header, and the look-back window is sent as `time_range` (the API no longer accepts `api_key` or `days` in the body).
- **Empty categories were never written.** The rotation sorted the string `"Never"` after real dates, so categories with no articles (Statistics, NLP, CV, Gen AI) could never be picked. They are now picked first.
- **Dry runs were not dry.** `--dry-run` still called Groq to choose a topic and needed every API key. It is now completely offline and needs no keys.
- **New articles could overwrite old ones.** A slug that matched an existing article replaced it. Slugs are now unique (`-2`, `-3`, ...) and properly normalised (lowercase ASCII, no spaces).
- **An R2 read error could wipe the article index.** Every error was treated as "file missing", so the next save replaced `articles.json` with a single entry. Only a real "not found" counts as empty now; other errors stop the run. Failed uploads also stop the run instead of reporting success.
- **Empty metadata from the editor** produced files named `.md`. Title, description and slug now fall back to the topic and the first paragraph.
- **Stale lock file.** `uv.lock` was missing `opik` and `sentry-sdk`. It has been regenerated.
- **`requests` was used but not declared** as a dependency.
- **The README described a layout that no longer existed** (`backend/run.py`, `requirements.txt`, `frontend/`), and its Python version disagreed with `pyproject.toml`.
- Website: duplicate titles when an article began with `# Title`; duplicate heading ids broke table-of-contents links; pages crashed on an article with an unknown category; the home page downloaded every index twice; a missing article left the header on "Loading…".

### Security

- Article HTML is sanitised with DOMPurify before it is inserted into the page. Articles are LLM output, partly built from web search results.
- Titles, descriptions and tags are HTML-escaped everywhere on the site.
- The research prompt tells the agent to treat search results as untrusted data and never follow instructions inside them.
- API keys are redacted from search-tool error messages (the Guardian key travels in the request URL).
- Local storage refuses paths outside its folder, and writes are atomic.
- Front-end libraries are self-hosted in `scribegraph/web/vendor` instead of loaded from CDNs.

### Added

- **Local storage backend** (`storage__backend=local`). Articles are written into the website folder, committed by GitHub Actions and served by GitHub Pages, so no Cloudflare account is needed. `auto` (the default) uses R2 when it is configured.
- **Revisions with context.** A rejected draft goes back to the writer together with the editor's numbered feedback, so it is revised rather than rewritten from scratch.
- **Tags.** The editor returns 3 to 5 tags per article, which the site displays and searches.
- **Command-line tool** `scribegraph` with `--domain`, `--topic`, `--ainews`, `--date`, `--dry-run`, `-v` and `--version`. Configuration problems give a clear message and exit code 2. Runs on GitHub Actions write a job summary.
- **GitHub Actions**: CI (ruff, pytest on Python 3.12 and 3.13, offline smoke test), daily article generation at 08:00 IST (AI News on Sundays) with auto-commit, and GitHub Pages deployment. The automation workflows skip themselves with a notice until the secret and Pages are set up.
- **Tests**: 60 offline tests with a scripted LLM covering the agents, the revision loop, storage backends, settings, search tools and the CLI.
- **Opik tracing** of complete graph runs when `OPIK_API_KEY` is set, next to the existing Opik prompt library support.
- `GROQ_API_KEY` is accepted as an alias for `llm__api_key`. New settings `pipeline__max_revisions` and `pipeline__history_size`.
- Clearer prompts: length and structure targets, runnable code, a "Key Takeaways" section, and no invented facts or URLs in news roundups.

### Changed

- Upgraded to LangGraph 1.2, LangChain 1.5 and langchain-groq 1.2. Python 3.12 is now supported (was 3.13 only).
- Opik is now an optional extra (`uv sync --extra opik`) because it adds about 60 packages.
- Settings no longer fail at import time when an unrelated key (for example R2 or Tavily) is missing.
- Front-end libraries: marked 9.1.6 → 18.2.1, highlight.js 11.9.0 → 11.12.0, and DOMPurify 3.4.18 added.

### Removed

- Unused dependencies `fastapi`, `uvicorn`, `pandas`, `openpyxl` and `ipykernel`, and the unused `package.json`.
- Unused files: `data/Tracker.xlsx`, a placeholder test article and `config.js.example`. The unused `content__unsplash_api_key` setting.
