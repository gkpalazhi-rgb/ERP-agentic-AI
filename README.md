# ERP-agentic-AI

Custom ERP agent with semantic intent routing, multi-intent chains, role-based access control, and LLM fallback.

## Quick start

1. Create env file
   - Copy `.env.example` to `.env`
2. Install dependencies
   - `pip install -r requirements.txt`
3. Run API
   - `uvicorn app.main:app --reload`

## Auth

- Register: `POST /auth/register`
- Login: `POST /auth/login`
- Current user: `GET /auth/me`
- Chat now requires bearer token: `POST /chat`

## Project-review assets

- Architecture + security + metrics report: `docs/project_review_report.md`
- Benchmark script: `scripts/intent_benchmark.py`
- Unit tests: `tests/`

## Run verification

- Compile check:
  - `python -m py_compile app/main.py app/services/agent.py app/services/semantic_router.py app/services/execution_engine.py`
- Run tests:
  - `python -m unittest discover -s tests -p "test_*.py"`
- Run benchmark:
  - `python scripts/intent_benchmark.py`
