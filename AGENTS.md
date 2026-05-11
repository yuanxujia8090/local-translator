# AGENTS.md — Local-Translator

## Setup & Run

```bash
uv sync                          # install deps (Python 3.13 required)
uvicorn app:app --reload --host 0.0.0.0 --port 8980
```

Tests: `pytest` (no subcommand needed). Requires oMLX mock — tests patch `requests.post`; no real model server needed.

## Config

`config.json` is the single source of truth — both `app.py` and `translate.py` read it at import time. Changing it requires a server restart. Key keys:

- `omlx.*` — host, port (default 8050), model name, temperature, max_tokens
- `server.port` — FastAPI port (default 8980)
- `history_limit` — max saved translations (default 20)

## Architecture

```
app.py          # FastAPI — routes, request/response models, history management
translate.py    # Translation logic — builds prompt with <start_of_turn>/<end_of_turn> tokens, calls oMLX /v1/completions
config.json     # All runtime configuration (read at import)
templates/index.html  # Single-page frontend, no build step
```

Critical detail: `translate.py` uses `/v1/completions` (not chat/completions). Prompt format must include `<start_of_turn>` / `<end_of_turn>` tokens for TranslateGemma. See `check-omlx.py` for reference.

## Testing quirks

- Tests use a `fake_config` fixture that creates a temp `config.json` and clears `sys.modules["app"]` / `sys.modules["translate"]` so re-import picks up the new config.
- Tests mock `requests.post` to return fake completions responses — never hit a real oMLX server.
- `conftest.py` provides shared fixtures: `fake_config`, `mock_omlx_response`, `patch_omlx_call`, `patch_health_check`.

## History

Translations are persisted to `.history/translations.json` (plain JSON, thread-safe via lock). Ignored by git.

## Known issues

- `app.py:206` — health endpoint computes `omlx_status` but never uses it in the response (returns URL instead). Tests document this behavior.

## Existing guidance

See `CLAUDE.md` for architecture details and development commands.
