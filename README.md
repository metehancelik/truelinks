# Lease and property-issue agents

A small full-stack service for a property owner. An agent reads a lease into a structured, verifiable record and checks it against the owner's rules; a second agent turns photos of a unit into a reported issue and a draft work order. Both meet on the unit.

> **Status: in progress.** Working today: lease field extraction with source quotes, and deterministic verification of every extracted field. Rules, review UI and issue reporting are next. See [DECISIONS.md](DECISIONS.md) for the reasoning so far.

## Layout

```
backend/   Python: agents, verification, rules (FastAPI to come)
web/       Next.js: review UI (scaffold only for now)
data/      Owner ruleset and unit records supplied with the brief
samples/   Sample leases
```

## Requirements

- [uv](https://docs.astral.sh/uv/) (installs the right Python for you)
- [Ollama](https://ollama.com/) with a vision-capable model, or any OpenAI-compatible API
- Node.js 22+ for the web app

## Backend

```bash
cd backend
cp .env.example .env
uv sync
uv run pytest
```

The tests need no model.

### Run extraction on a sample lease

Start a model. Ollama truncates input at 4,096 tokens by default and does so silently, so set the context length:

```bash
ollama pull gemma4:12b
OLLAMA_CONTEXT_LENGTH=16384 ollama serve
```

Then:

```bash
uv run python scripts/extract_lease.py ../samples/leases/01-clean-mc-b-1204.txt
```

Each field prints with a computed status: `VERIFIED` (the quote is in the document and agrees with the value), `UNVERIFIED` (a value whose source could not be confirmed) or `MISSING`. On an M4 with 24 GB this takes about 75 seconds with `gemma4:12b`.

### Using another model

Settings are read from `backend/.env`. To use a hosted OpenAI-compatible API:

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_TEXT_MODEL=<model name>
LLM_REASONING_EFFORT=
```

### Code quality

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

## Web

```bash
cd web
npm install
npm run dev
```
