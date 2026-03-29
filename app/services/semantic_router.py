from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from app.services.intent_classifier import _get_model


logger = logging.getLogger(__name__)


INTENT_PHRASES: dict[str, list[str]] = {
    "inventory_query": [
        "check inventory for item",
        "show stock for item",
        "inventory status for item",
        "how much stock is there for item",
        "available quantity for item",
        "only 5 units are there for item",
        "kindly check stock of item",
        "please check inventory for item",
        "stock left for item",
        "balance stock for item",
        "qty of item",
        "stock?",
        "inv check for item",
        "check check the stock for item",
        "CHECK INVENTORY FOR ITEM",
        "is item available now",
        "warehouse stock for item",
        "how many pcs left for item",
    ],
    "purchase_order_create": [
        "create purchase order for item",
        "raise po for item",
        "make a po for item",
        "create po for 10 units of item",
        "order item",
        "purchase item from vendor",
        "procure item",
        "reorder item",
        "kindly create po",
        "please generate purchase order",
        "do the needful and raise po",
        "PO undakkണം for item",
        "make po for item",
        "purchese order for item",
        "issue po for item",
        "new po for item",
        "book order for item",
        "create and send po for item",
    ],
    "leave_application": [
        "apply leave for tomorrow",
        "i need leave today",
        "mark leave for me",
        "leave application for employee",
        "please apply casual leave",
        "kindly put leave for tomorrow",
        "half day leave for Anil",
        "sick leave apply cheyyu",
        "leave?",
        "put one day leave for me",
        "i will be on leave tomorrow",
        "leave request for next monday",
        "can you submit leave application",
        "do the needful for leave",
        "mark cl for today",
        "take leave for friday",
        "leave form submit for employee",
        "apply leave due to fever",
    ],
    "purchase_invoice_create": [
        "create purchase invoice",
        "generate invoice for po",
        "make purchase inv",
        "create inv for purchase order",
        "invoice against po",
        "prepare vendor invoice",
        "generate purchese invoce",
        "inv create for po",
        "bill create for po",
        "make bill for purchase",
        "purchase invoice ready cheyyu",
        "raise invoice for verified po",
        "create grn invoice",
        "invoice please",
        "inv?",
        "create vendor bill entry",
        "prepare purchase bill",
        "close purchase with invoice",
    ],
    "purchase_order_verify": [
        "verify purchase order",
        "check po status",
        "validate po number",
        "is po approved",
        "verify and close the po",
        "po is came verify it",
        "check and close the po",
        "confirm purchase order",
        "po verification needed",
        "verify goods against po",
        "match item with po",
        "purchase order verify cheyyu",
        "po status?",
        "po verify",
        "check whether po is valid",
        "verify recieved po",
        "cross check po details",
        "confirm po before update",
    ],
    "inventory_update": [
        "update inventory for item",
        "add stock for item",
        "increase stock by 20 units",
        "goods received update stock",
        "grn update inventory",
        "stock update cheyyu",
        "inventory update for received item",
        "item recieved add to stock",
        "recieve item and update inventory",
        "please update stock balance",
        "adjust inventory quantity",
        "close po and update stock",
        "verify and update inventory",
        "post goods receipt",
        "material came update stock",
        "check and update stock",
        "add 10 nos to item",
        "update stock ledger for item",
        "mark as arrived",
        "50 items arrived",
        "mark delivered",
        "item arrived update stock",
        "goods arrived mark po",
        "mark 50 dhanwantharam as arrived",
        "po delivered update inventory",
    ],
}


INTENT_TO_TOOL = {
    "inventory_query": "get_inventory",
    "purchase_order_create": "create_purchase_order",
    "leave_application": "apply_leave",
    "purchase_invoice_create": "generate_purchase_invoice",
    "purchase_order_verify": "get_po_status",
    "inventory_update": "update_inventory_stock",
}


def _normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[\u0D00-\u0D7F]+", " ", text)
    text = re.sub(r"\b(kindly|please|can you|could you|would you|do the needful|pls|pls\.)\b", " ", text)
    text = re.sub(r"\b(check)\s+\1\b", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, default=str)
    except Exception:
        return str(value)


@dataclass(frozen=True)
class _IntentScore:
    intent: str
    confidence: float


class IntentResolver:
    _fallback_token_pattern = re.compile(r"\w+")

    def __init__(
        self,
        intent_phrases: dict[str, list[str]] | None = None,
        confidence_threshold: float = 0.45,
        multi_intent_threshold: float = 0.40,
    ) -> None:
        self.intent_phrases = intent_phrases or INTENT_PHRASES
        self.confidence_threshold = confidence_threshold
        self.multi_intent_threshold = multi_intent_threshold
        self.mode = "keyword"
        self._intent_embeddings: dict[str, list[list[float]]] = {}
        self._lock = threading.Lock()
        self._initialised = False
        self._initialise()

    def _initialise(self) -> None:
        if self._initialised:
            return
        with self._lock:
            if self._initialised:
                return
            model = _get_model()
            if model is None:
                self.mode = "keyword"
                logger.info("IntentResolver active mode: keyword")
                self._initialised = True
                return

            try:
                for intent, phrases in self.intent_phrases.items():
                    vectors = model.encode(
                        phrases,
                        normalize_embeddings=True,
                        convert_to_numpy=True,
                    )
                    self._intent_embeddings[intent] = [vector.tolist() for vector in vectors]
                self.mode = "semantic"
                logger.info("IntentResolver active mode: semantic")
            except Exception as exc:
                self.mode = "keyword"
                logger.warning("IntentResolver falling back to keyword mode: %s", exc)

            self._initialised = True

    def _semantic_scores(self, user_input: str) -> list[_IntentScore]:
        model = _get_model()
        if model is None or not self._intent_embeddings:
            return self._keyword_scores(user_input)

        query_vector = model.encode(
            [user_input],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0].tolist()

        scores = [
            _IntentScore(
                intent=intent,
                confidence=max(_cosine_similarity(query_vector, vector) for vector in vectors),
            )
            for intent, vectors in self._intent_embeddings.items()
        ]
        return sorted(scores, key=lambda score: score.confidence, reverse=True)

    def _keyword_scores(self, user_input: str) -> list[_IntentScore]:
        input_tokens = set(self._fallback_token_pattern.findall(_normalize_text(user_input)))
        scores: list[_IntentScore] = []

        for intent, phrases in self.intent_phrases.items():
            best_score = 0.0
            for phrase in phrases:
                phrase_tokens = set(self._fallback_token_pattern.findall(_normalize_text(phrase)))
                if not phrase_tokens:
                    continue
                overlap = len(input_tokens & phrase_tokens) / len(phrase_tokens)
                exact_bonus = 0.2 if _normalize_text(phrase) in _normalize_text(user_input) else 0.0
                best_score = max(best_score, min(1.0, overlap + exact_bonus))
            scores.append(_IntentScore(intent=intent, confidence=best_score))

        self.mode = "keyword"
        return sorted(scores, key=lambda score: score.confidence, reverse=True)

    def _extract_item_name(self, text: str) -> str | None:
        patterns = (
            r"\b(?:of|for|item|stock of|inventory for|update inventory for|order for)\s+([A-Za-z][A-Za-z0-9 .&/-]+?)(?:\s+(?:today|tomorrow|next|po|invoice|qty|quantity|units|kg|pcs|boxes|nos)\b|$)",
            r"\b(?:cement|steel rods|sand|tiles|wire|bricks|capsules|bottles|amber bottles|glass bottles|brahmi chm)\b",
            # "11 neem tab arrived" — <quantity> <item> <arrival verb>
            r"\b\d+\s+([A-Za-z][A-Za-z0-9 .&/-]+?)\s+(?:arrived|received|delivered|has\s+arrived|have\s+arrived)\b",
            # "mark 50 dhanwantharam as arrived"
            r"\b\d+\s+([A-Za-z][A-Za-z0-9 .&/-]+?)\s+(?:as\s+)?(?:arrived|received|delivered)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                cleaned = re.sub(
                    r"\b(?:and\s+generate|and\s+create|and\s+update|generate|create|update|invoice|verify|check|po)\b.*$",
                    "",
                    value,
                    flags=re.I,
                )
                cleaned = re.sub(r"\b\d+\b", " ", cleaned)
                cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
                if cleaned:
                    return cleaned
        return None

    def _extract_quantity(self, text: str) -> int | None:
        match = re.search(r"\b(\d+)\s*(?:units?|kg|kgs|pcs?|pieces?|boxes?|nos?)\b", text, re.I)
        if match:
            return int(match.group(1))
        match = re.search(r"\b(?:add|update|increase|create|make|order|raise|purchase|buy)\s+(\d+)\b", text, re.I)
        if match:
            return int(match.group(1))
        return None

    def _extract_date(self, text: str) -> str | None:
        explicit = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", text)
        if explicit:
            return explicit.group(1)

        lowered = text.lower()
        today = datetime.now()
        if "today" in lowered:
            return today.strftime("%Y-%m-%d")
        if "tomorrow" in lowered:
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")

        weekday_match = re.search(
            r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            lowered,
        )
        if weekday_match:
            weekday_lookup = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }
            target = weekday_lookup[weekday_match.group(1)]
            delta = (target - today.weekday()) % 7
            delta = 7 if delta == 0 else delta
            return (today + timedelta(days=delta)).strftime("%Y-%m-%d")
        return None

    def _extract_employee_name(self, text: str, detected_intents: list[str]) -> str | None:
        if "leave_application" not in detected_intents:
            return None
        for pattern in (r"\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", r"\bby\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"):
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def _extract_po_number(self, text: str) -> str | None:
        # 1. Match YYMMDD-ITEMCODE-NNN format (e.g. 260324-FG00639-001)
        match = re.search(r"\b(\d{6}-[A-Z0-9]+-\d{3})\b", text, re.I)
        if match:
            return match.group(1).upper()
        # 2. Match PO-xxx or PO/xxx format
        match = re.search(r"\b(PO[-/][A-Z0-9-]+)\b", text, re.I)
        if match:
            return match.group(1).upper()
        # 3. Match "PO : <id>" or "po number <id>" or "PO #<id>"
        match = re.search(r"\bpo\s*(?:number|no|id|#)?\s*[:\-/]?\s*([A-Z0-9][\w-]+)", text, re.I)
        if match:
            return match.group(1)
        return None

    def _extract_invoice_number(self, text: str) -> str | None:
        match = re.search(r"\b(INV[-/][A-Z0-9-]+)\b", text, re.I)
        if match:
            return match.group(1).upper()
        return None

    def _extract_entities(self, text: str, detected_intents: list[str]) -> dict[str, Any]:
        return {
            "item_name": self._extract_item_name(text),
            "quantity": self._extract_quantity(text),
            "date": self._extract_date(text),
            "employee_name": self._extract_employee_name(text, detected_intents),
            "po_number": self._extract_po_number(text),
            "invoice_number": self._extract_invoice_number(text),
        }

    def resolve(self, user_input: str) -> dict[str, Any]:
        normalized_input = _normalize_text(user_input)
        scores = self._semantic_scores(normalized_input) if self.mode == "semantic" else self._keyword_scores(normalized_input)
        if not scores:
            scores = [_IntentScore(intent="unknown_intent", confidence=0.0)]

        matched = [
            {"intent": score.intent, "confidence": round(score.confidence, 4)}
            for score in scores
            if score.confidence >= self.multi_intent_threshold
        ]

        top = scores[0]
        if top.confidence < self.confidence_threshold:
            intents = [{"intent": "unknown_intent", "confidence": round(top.confidence, 4)}]
            detected_names: list[str] = []
            is_multi_intent = False
        else:
            intents = matched or [{"intent": top.intent, "confidence": round(top.confidence, 4)}]
            detected_names = [intent["intent"] for intent in intents]
            is_multi_intent = len(intents) >= 2

        return {
            "intents": intents,
            "entities": self._extract_entities(user_input, detected_names),
            "is_multi_intent": is_multi_intent,
            "raw_input": user_input,
            "resolver_mode": self.mode,
        }


class IntentChainOrchestrator:
    KNOWN_CHAINS: dict[str, list[str]] = {
        "verify_and_update": ["purchase_order_verify", "inventory_update"],
        "order_and_invoice": ["purchase_order_create", "purchase_invoice_create"],
        "invoice_and_update": ["purchase_invoice_create", "inventory_update"],
    }

    def detect_chain(self, resolved: dict[str, Any]) -> dict[str, Any] | None:
        detected = {item["intent"] for item in resolved.get("intents", [])}
        for chain_name, steps in self.KNOWN_CHAINS.items():
            if set(steps).issubset(detected):
                return {"name": chain_name, "steps": steps, "status": "pending"}
        return None

    def attach_chain(self, resolved: dict[str, Any]) -> dict[str, Any]:
        chain = self.detect_chain(resolved)
        if chain:
            resolved["chain"] = chain
        return resolved

    def execute_chain(
        self,
        chain_name: str,
        entities: dict[str, Any],
        agent_tools: dict[str, Callable[[dict[str, Any]], Any]],
    ) -> dict[str, Any]:
        steps = self.KNOWN_CHAINS.get(chain_name, [])
        context = dict(entities)
        completed: list[str] = []
        failed: list[str] = []
        log: list[dict[str, Any]] = []

        for step in steps:
            tool = agent_tools.get(step)
            if tool is None:
                failed.append(step)
                log.append({"step": step, "status": "failed", "output": "missing tool"})
                break

            output = tool(context)
            success = not (isinstance(output, dict) and output.get("success") is False)
            log.append({"step": step, "status": "success" if success else "failed", "output": output})

            if isinstance(output, dict):
                context.update(output)
                context["previous_step_output"] = output

            if not success:
                failed.append(step)
                break
            completed.append(step)

        if failed and completed:
            final_status = "partial"
        elif failed:
            final_status = "failed"
        else:
            final_status = "success"

        return {
            "chain": chain_name,
            "steps_completed": completed,
            "steps_failed": failed,
            "final_status": final_status,
            "log": log,
        }


class AgentRouter:
    def __init__(
        self,
        resolver: IntentResolver,
        orchestrator: IntentChainOrchestrator,
        existing_keyword_logic: Callable[[str], dict[str, Any] | None],
        llm_handler: Callable[[str], str],
    ) -> None:
        self.resolver = resolver
        self.orchestrator = orchestrator
        self.existing_keyword_logic = existing_keyword_logic
        self.llm_handler = llm_handler

    def _build_leave_args(self, raw_input: str, entities: dict[str, Any]) -> dict[str, Any]:
        leave_type = "Full Day"
        lowered = raw_input.lower()
        if "1st half" in lowered or "first half" in lowered:
            leave_type = "1st Half"
        elif "2nd half" in lowered or "second half" in lowered:
            leave_type = "2nd Half"
        elif "half" in lowered:
            leave_type = "1st Half"

        reason_match = re.search(r"(?:because|due to|reason)\s+(.+?)(?:\s+(?:on|for|tomorrow|today)|$)", raw_input, re.I)
        reason = reason_match.group(1).strip() if reason_match else "Personal"
        return {
            "reason": reason,
            "leave_date": entities.get("date") or datetime.now().strftime("%Y-%m-%d"),
            "leave_type": leave_type,
        }

    def _single_intent_step(self, intent_name: str, resolved: dict[str, Any]) -> dict[str, Any] | None:
        entities = resolved.get("entities", {})
        raw_input = resolved.get("raw_input", "")
        tool_name = INTENT_TO_TOOL[intent_name]

        if intent_name == "inventory_query":
            item_name = entities.get("item_name")
            if not item_name:
                return None
            return {"type": "tool", "name": tool_name, "args": {"item": item_name}}

        if intent_name == "purchase_order_create":
            item_name = entities.get("item_name")
            if not item_name:
                return None
            return {
                "type": "tool",
                "name": tool_name,
                "args": {
                    "item": item_name,
                    "quantity": entities.get("quantity") or 1,
                    "vendor_name": "default_vendor",
                },
            }

        if intent_name == "leave_application":
            return {"type": "tool", "name": tool_name, "args": self._build_leave_args(raw_input, entities)}

        if intent_name == "purchase_invoice_create":
            po_number = entities.get("po_number")
            if not po_number:
                return None
            return {"type": "tool", "name": tool_name, "args": {"po_id": po_number}}

        if intent_name == "purchase_order_verify":
            po_number = entities.get("po_number")
            if not po_number:
                return None
            return {"type": "tool", "name": tool_name, "args": {"po_id": po_number}}

        if intent_name == "inventory_update":
            item_name = entities.get("item_name")
            quantity = entities.get("quantity")
            if not item_name or quantity is None:
                return None
            args = {"item": item_name, "quantity": quantity}
            if entities.get("po_number"):
                args["po_id"] = entities["po_number"]
            return {"type": "tool", "name": tool_name, "args": args}

        return None

    def _build_chain_plan(self, resolved: dict[str, Any]) -> dict[str, Any] | None:
        chain = resolved.get("chain")
        entities = resolved.get("entities", {})
        if not chain:
            return None

        if chain["name"] == "verify_and_update" and entities.get("po_number"):
            steps = [
                {"type": "tool", "name": "get_po_status", "args": {"po_id": entities["po_number"]}},
                {
                    "type": "tool",
                    "name": "update_inventory_stock",
                    "args": {"item": "{last.item}", "quantity": "{last.quantity}", "po_id": "{last.po_id}"},
                },
            ]
        elif chain["name"] == "order_and_invoice":
            create_step = self._single_intent_step("purchase_order_create", resolved)
            if create_step is None:
                return None
            steps = [create_step, {"type": "tool", "name": "generate_purchase_invoice", "args": {"po_id": "{last.po_id}"}}]
        elif chain["name"] == "invoice_and_update" and entities.get("po_number") and entities.get("item_name") and entities.get("quantity") is not None:
            steps = [
                {"type": "tool", "name": "generate_purchase_invoice", "args": {"po_id": entities["po_number"]}},
                {
                    "type": "tool",
                    "name": "update_inventory_stock",
                    "args": {
                        "item": entities["item_name"],
                        "quantity": entities["quantity"],
                        "po_id": entities["po_number"],
                    },
                },
            ]
        else:
            return None

        return {
            "type": "action",
            "steps": steps,
            "intent_detection": {
                "source": "semantic_router",
                "resolver_mode": resolved.get("resolver_mode"),
                "resolved_intents": resolved.get("intents"),
                "entities": entities,
                "chain": chain,
            },
        }

    def route_plan(self, user_input: str) -> dict[str, Any] | None:
        resolved = self.orchestrator.attach_chain(self.resolver.resolve(user_input))
        intents = resolved.get("intents", [])
        if not intents:
            return self.existing_keyword_logic(user_input)

        if intents[0]["intent"] == "unknown_intent":
            return self.existing_keyword_logic(user_input)

        if resolved.get("chain"):
            chain_plan = self._build_chain_plan(resolved)
            if chain_plan is not None:
                return chain_plan

        steps = []
        for intent_payload in intents:
            step = self._single_intent_step(intent_payload["intent"], resolved)
            if step is None:
                return self.existing_keyword_logic(user_input)
            steps.append(step)

        return {
            "type": "action",
            "steps": steps,
            "intent_detection": {
                "source": "semantic_router",
                "resolver_mode": resolved.get("resolver_mode"),
                "resolved_intents": intents,
                "entities": resolved.get("entities"),
                "is_multi_intent": resolved.get("is_multi_intent", False),
            },
        }

    def route(self, user_input: str) -> str:
        plan = self.route_plan(user_input)
        if plan is None:
            return self.llm_handler(user_input)
        return _safe_json(plan)


_resolver_singleton: IntentResolver | None = None
_orchestrator_singleton: IntentChainOrchestrator | None = None
_router_singleton: AgentRouter | None = None
_singleton_lock = threading.RLock()


def get_intent_resolver() -> IntentResolver:
    global _resolver_singleton
    if _resolver_singleton is None:
        with _singleton_lock:
            if _resolver_singleton is None:
                _resolver_singleton = IntentResolver()
    return _resolver_singleton


def get_chain_orchestrator() -> IntentChainOrchestrator:
    global _orchestrator_singleton
    if _orchestrator_singleton is None:
        with _singleton_lock:
            if _orchestrator_singleton is None:
                _orchestrator_singleton = IntentChainOrchestrator()
    return _orchestrator_singleton


def get_agent_router(
    existing_keyword_logic: Callable[[str], dict[str, Any] | None],
    llm_handler: Callable[[str], str],
) -> AgentRouter:
    global _router_singleton
    if _router_singleton is None:
        with _singleton_lock:
            if _router_singleton is None:
                _router_singleton = AgentRouter(
                    resolver=get_intent_resolver(),
                    orchestrator=get_chain_orchestrator(),
                    existing_keyword_logic=existing_keyword_logic,
                    llm_handler=llm_handler,
                )
    return _router_singleton


def preload_semantic_router() -> None:
    get_intent_resolver()
    get_chain_orchestrator()


if __name__ == "__main__":
    resolver = IntentResolver()
    orchestrator = IntentChainOrchestrator()
    router = AgentRouter(resolver, orchestrator, lambda _: None, lambda text: f"LLM fallback: {text}")

    examples = [
        "check inventory for steel rods",
        "verify PO-1002 and update inventory for cement 10 units",
        "create po for 20 units of cement and generate invoice",
        "what should we do for vendor negotiation this quarter",
    ]
    for sample in examples:
        resolved = orchestrator.attach_chain(resolver.resolve(sample))
        print("input:", sample)
        print("resolved:", _safe_json(resolved))
        print("route:", router.route(sample))
