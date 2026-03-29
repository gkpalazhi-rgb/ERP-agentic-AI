# ERP Agentic AI - Project Review Report

## 1) Architecture Overview

```text
Client (Web/UI)
  -> FastAPI endpoints (/auth, /chat, /history, /inventory...)
    -> JWT auth + role checks
      -> AgentRouter (semantic wrapper)
        -> IntentResolver (semantic + keyword fallback)
        -> IntentChainOrchestrator (known workflow chains)
        -> Legacy keyword planner fallback
        -> Ollama LLM fallback (unknown/open-ended)
      -> ExecutionEngine (tool-level RBAC + step execution)
        -> ERP tools + SQLAlchemy models
          -> Database (users, inventory, purchase orders, logs, conversations)
```

## 2) Implemented Improvements

- Semantic intent resolver with cached sentence embeddings at startup
- Canonical phrase bank for 6 ERP intents with typo and Indian-English variants
- Multi-intent detection and chain planning for sequential workflows
- Chain support: `verify_and_update`, `order_and_invoice`, `invoice_and_update`
- JWT enforcement in `/chat` (identity taken from token, not request user_id)
- Role-based tool authorization inside execution engine
- Structured API error response format:

```json
{
  "error": {
    "code": "HTTP_ERROR",
    "message": "Invalid token",
    "details": {}
  }
}
```

- Audit logging for chat runs with user/role/intents/chain/response preview

## 3) Access Control Matrix

| Tool | Employee | Admin |
|---|---:|---:|
| get_inventory | Yes | Yes |
| create_purchase_order | Yes | Yes |
| get_po_status | Yes | Yes |
| generate_purchase_invoice | Yes | Yes |
| apply_leave | Yes | Yes |
| update_inventory_stock | Yes | Yes |
| get_vendors | Yes | Yes |
| add_vendor | No | Yes |
| update_vendor | No | Yes |

## 4) Verification Checklist

- Compile checks passed for modified modules
- Unit tests added for semantic resolver, chain orchestration, chat auth
- Benchmark script added for intent accuracy + latency reporting

### Test Run Result

- Command: `python -m unittest discover -s tests -p "test_*.py"`
- Result: `Ran 8 tests ... OK`

### Benchmark Result

- Command: `python scripts/intent_benchmark.py`
- Resolver mode: `semantic`
- Samples: `28`
- Top-1 accuracy (known intents): `25/26 = 96.15%`
- Multi-intent detection accuracy: `3/3 = 100.00%`
- Unknown-intent fallback precision: `2/2 = 100.00%`
- Latency avg: `11.12 ms`
- Latency p95: `11.21 ms`
- Latency min/max: `8.96 / 34.46 ms`

## 5) Repro Steps for Review

1. Install dependencies: `pip install -r requirements.txt`
2. Set env: copy `.env.example` -> `.env`
3. Start API: `uvicorn app.main:app --reload`
4. Run tests: `python -m unittest discover -s tests -p "test_*.py"`
5. Run benchmark: `python scripts/intent_benchmark.py`

## 6) Expected Demo Flow (Review Day)

1. Login and get JWT token
2. Single intent: `check inventory for brahmi chm`
3. Multi-intent chain: `verify PO-1002 and update inventory for cement 10 units`
4. Role denial: employee tries `add vendor`
5. Unknown query -> LLM fallback
