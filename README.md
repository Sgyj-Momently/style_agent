# Style Agent

Applies editorial styling to draft Markdown. When a `voice_profile` is supplied,
the agent rewrites with Ollama to mimic the learned voice profile and falls back
to deterministic style hints if the local LLM is unavailable.

## API

- `GET /health`
- `POST /api/v1/styles`

## Environment

- `OLLAMA_BASE_URL` defaults to `http://localhost:11434`
- `STYLE_MODEL` defaults to `qwen2.5:14b`
- `OLLAMA_TIMEOUT_SECONDS` defaults to `120`

## Verification

```bash
PYTHON=/path/to/python scripts/verify.sh
```
