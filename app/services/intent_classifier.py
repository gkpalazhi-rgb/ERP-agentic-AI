"""
Semantic intent classifier for the ERP chatbot.

This module uses sentence-transformers to detect high-confidence ERP intents
before falling back to the LLM planner. It is intentionally conservative:
ambiguous queries should still flow to the LLM.

Optimised for 900+ inventory items:
  - Items are loaded from the DB once and cached in memory.
  - A precomputed lowercase→original mapping enables O(1) exact lookups.
  - Fuzzy matching (via difflib) is only invoked on cache-miss.
  - Embedding matrices for intents are computed once at startup.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_NAME = "all-MiniLM-L6-v2"
CONFIDENCE_THRESHOLD = 0.55

# ---------------------------------------------------------------------------
# Module-level singletons (lazy-initialised, thread-safe)
# ---------------------------------------------------------------------------
_model = None
_model_load_error: str | None = None
_intent_embeddings: dict[str, np.ndarray] | None = None
_semantic_index: _SemanticIndex | None = None
_lock = threading.Lock()

# Item cache (populated from DB on first call)
_item_cache: _ItemCache | None = None

# ---------------------------------------------------------------------------
# Intent training examples
# ---------------------------------------------------------------------------
INTENT_EXAMPLES: dict[str, list[str]] = {
    "check_inventory": [
        "check inventory for bottles",
        "how many amber bottles do we have",
        "stock of arishtam",
        "do we have capsules in stock",
        "inventory left for dropper bottles",
        "how much stock is remaining",
        "what is the quantity of glass bottles",
        "check stock levels",
        "how many items left",
        "current inventory count",
        "do we have enough bottles",
        "show me the stock",
        "is arishtam available",
        "how many droppers are left",
        "check quantity of capsules",
        "what is the stock of this item",
        "available quantity",
        "show inventory",
        "remaining stock",
        "quantity in hand",
        "how many do we have in warehouse",
        "items in stock",
        "is this product available",
        "any stock left",
        "inventory for amber bottle",
        "available stock for capsules",
        "warehouse balance for arishtam",
        "how much amber bottle stock is there",
        "check item quantity",
        "look up current stock",
        "see inventory for glass bottle",
        "stock count for dropper bottles",
        "is bottle stock available",
        "tell me inventory quantity",
    ],
    "create_purchase_order": [
        "create a purchase order for 50 bottles",
        "order 100 capsules",
        "buy 200 amber bottles",
        "create PO for arishtam",
        "purchase 30 dropper bottles",
        "place an order for glass bottles",
        "i want to order capsules",
        "restock bottles",
        "procure 50 items",
        "make a PO for 100 units",
        "we need to buy more arishtam",
        "raise a purchase order",
        "order more supplies",
        "place purchase order for 75 amber bottles from vendor",
        "need to reorder stock",
        "create order for raw materials",
        "purchase supplies from vendor",
        "buy inventory items",
        "raise PO for restocking",
        "get more stock ordered",
        "create restock order for capsules",
        "make purchase order for glass bottle",
        "procurement request for amber bottle",
        "issue po for 20 bottles",
        "place replenishment order",
        "order stock from supplier",
        "raise reorder for inventory",
        "create vendor order for capsules",
    ],
    "get_po_status": [
        "status of PO 260324-AYU001-001",
        "check status of purchase order",
        "what is the status of order 3",
        "track PO 5",
        "where is my order",
        "how is PO 260324-BOT001-002 going",
        "show me order status",
        "is my purchase order delivered",
        "check PO status",
        "what happened to order 260324-CAP001-001",
        "cost of PO 3",
        "total cost of purchase order",
        "where is the order",
        "purchase order tracking",
        "PO delivery status",
        "has my order arrived",
        "current status of PO",
        "what is the total cost of po 5",
        "show po details",
        "get purchase order cost",
        "track order delivery",
        "is purchase order pending",
        "show me po summary",
        "lookup po information",
    ],
    "generate_invoice": [
        "generate invoice for PO 260324-AYU001-001",
        "create invoice for order 3",
        "make a bill for PO 5",
        "invoice for purchase order",
        "print invoice",
        "generate billing for PO",
        "prepare receipt for PO 2",
        "make purchase invoice",
        "generate bill for order",
        "i need an invoice for PO 260324-BOT001-002",
        "print the bill",
        "create billing document",
        "invoice generation",
        "make receipt for this PO",
        "download invoice for order 5",
        "create purchase invoice text file",
        "prepare invoice copy for po 12",
        "billing file for purchase order",
        "export invoice for po",
        "invoice for delivered order",
    ],
    "get_vendors": [
        "show all vendors",
        "list vendors",
        "who are our suppliers",
        "get vendor list",
        "vendor details",
        "who supplies bottles",
        "show me the supplier list",
        "which vendors do we have",
        "all our suppliers",
        "show suppliers",
        "display vendor information",
        "vendor catalog",
        "supplier directory",
        "list all suppliers",
        "show vendor master",
        "which vendor supplies capsules",
        "who supplies amber bottles",
        "vendor list for inventory",
        "display supplier contacts",
        "find available vendors",
    ],
    "add_vendor": [
        "add a new vendor called pharma corp",
        "register a supplier",
        "add vendor ravi for bottles at price 50",
        "new vendor for capsules",
        "create a vendor entry",
        "add supplier with email",
        "register new supplier in system",
        "add vendor details",
        "onboard a new vendor",
        "create supplier record",
        "add supplier medix for capsules with email medix@test.com",
        "create vendor profile for bottle supplier",
        "save a new supplier with price 45",
        "new vendor named herbal source",
        "register vendor for amber bottle supply",
    ],
    "update_vendor": [
        "update vendor email",
        "change vendor price",
        "update pharma corp email to test@test.com",
        "modify vendor details",
        "change supplier price to 100",
        "edit vendor information",
        "update supplier email address",
        "modify vendor pricing",
        "change vendor contact",
        "edit supplier details",
        "set vendor email to purchase@test.com",
        "revise supplier rate to 45",
        "update vendor contact info",
        "change supplier email and price",
        "edit vendor record",
    ],
    "apply_leave": [
        "i want to apply for leave",
        "apply leave for tomorrow",
        "i am sick, need a day off",
        "taking half day leave",
        "apply for full day leave on monday",
        "i need leave on 25th march",
        "request sick leave",
        "apply 1st half leave",
        "apply 2nd half day",
        "can i take a leave tomorrow",
        "mark me absent tomorrow",
        "leave application for personal reason",
        "submit leave request",
        "day off tomorrow",
        "need time off",
        "going on leave",
        "request day off",
        "submit leave for next monday",
        "book personal leave",
        "mark leave for tomorrow",
        "request half day off",
        "apply casual leave",
        "take second half leave today",
    ],
    "stock_arrival": [
        "50 bottles have arrived",
        "received 100 capsules for PO 3",
        "stock delivered for PO 260324-AYU001-001",
        "PO 5 items have been received",
        "goods arrived for order 2",
        "we received the shipment",
        "30 arishtam arrived for PO 260324-ARI001-001",
        "delivery received for purchase order",
        "stock has come in",
        "amber bottles have been delivered",
        "inventory received",
        "goods received against PO",
        "shipment arrived for order",
        "stock delivery completed",
        "items have been delivered",
        "received goods for po 5",
        "mark stock as delivered",
        "inventory replenishment arrived",
        "po shipment received",
        "update stock after delivery",
        "goods receipt for purchase order",
    ],
}


INTENT_TO_TOOL: dict[str, str] = {
    "check_inventory": "get_inventory",
    "create_purchase_order": "create_purchase_order",
    "get_po_status": "get_po_status",
    "generate_invoice": "generate_purchase_invoice",
    "get_vendors": "get_vendors",
    "add_vendor": "add_vendor",
    "update_vendor": "update_vendor",
    "apply_leave": "apply_leave",
    "stock_arrival": "update_inventory_stock",
}


@dataclass(frozen=True)
class _KeywordIntentRule:
    intent: str
    patterns: tuple[re.Pattern[str], ...]
    confidence: float = 0.98


KEYWORD_INTENT_RULES: tuple[_KeywordIntentRule, ...] = (
    _KeywordIntentRule(
        intent="generate_invoice",
        patterns=(
            re.compile(r"\b(?:generate|create|make|prepare|print|download|export)\b.*\b(?:invoice|bill|receipt)\b", re.I),
            re.compile(r"\b(?:invoice|bill|receipt)\b.*\b(?:po|order)\b", re.I),
        ),
    ),
    _KeywordIntentRule(
        intent="stock_arrival",
        patterns=(
            re.compile(r"\b(?:arrived|received|delivered|receipt|goods receipt)\b.*\b(?:po|purchase order|stock|shipment|goods|items)\b", re.I),
            re.compile(r"\b(?:update|mark)\b.*\b(?:stock|inventory)\b.*\b(?:arrived|received|delivered)\b", re.I),
        ),
        confidence=0.98,
    ),
    _KeywordIntentRule(
        intent="get_po_status",
        patterns=(
            re.compile(r"\b(?:status|track|where|delivered|pending|cost|total cost|summary|details)\b.*\b(?:po|purchase order|order)\b", re.I),
            re.compile(r"\b(?:po|purchase order|order)\b.*\b(?:status|cost|delivered|pending|summary|details)\b", re.I),
        ),
    ),
    _KeywordIntentRule(
        intent="check_inventory",
        patterns=(
            re.compile(r"\b(?:inventory|stock|quantity|available|availability|balance|warehouse)\b", re.I),
            re.compile(r"\bhow many\b.*\b(?:have|left|in stock)\b", re.I),
        ),
        confidence=0.93,
    ),
    _KeywordIntentRule(
        intent="create_purchase_order",
        patterns=(
            re.compile(r"\b(?:create|raise|place|make|issue)\b.*\b(?:purchase order|po)\b", re.I),
            re.compile(r"\b(?:restock|reorder|procure|purchase|buy|replenish)\b", re.I),
        ),
        confidence=0.94,
    ),
    _KeywordIntentRule(
        intent="get_vendors",
        patterns=(
            re.compile(r"\b(?:show|list|get|display|find|who)\b.*\b(?:vendors|vendor|suppliers|supplier)\b", re.I),
            re.compile(r"\b(?:vendors|suppliers|supplier directory|vendor catalog)\b", re.I),
        ),
        confidence=0.95,
    ),
    _KeywordIntentRule(
        intent="add_vendor",
        patterns=(
            re.compile(r"\b(?:add|register|create|onboard|save)\b.*\b(?:vendor|supplier)\b", re.I),
        ),
        confidence=0.97,
    ),
    _KeywordIntentRule(
        intent="update_vendor",
        patterns=(
            re.compile(r"\b(?:update|change|modify|edit|revise|set)\b.*\b(?:vendor|supplier)\b", re.I),
        ),
        confidence=0.97,
    ),
    _KeywordIntentRule(
        intent="apply_leave",
        patterns=(
            re.compile(r"\b(?:apply|request|submit|take|book|mark)\b.*\bleave\b", re.I),
            re.compile(r"\b(?:day off|half day|time off|sick leave|casual leave)\b", re.I),
        ),
        confidence=0.98,
    ),
)


# ---------------------------------------------------------------------------
# Data class for detection result
# ---------------------------------------------------------------------------
@dataclass
class IntentDetection:
    intent: str | None
    confidence: float
    matched_example: str | None
    reason: str
    available: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": round(self.confidence, 4),
            "matched_example": self.matched_example,
            "reason": self.reason,
            "available": self.available,
        }


@dataclass(frozen=True)
class _SemanticIndex:
    matrix: np.ndarray
    intents: tuple[str, ...]
    examples: tuple[str, ...]


# ===================================================================
#  ITEM CACHE — loads 900+ items from the DB once, thread-safe
# ===================================================================
class _ItemCache:
    """In-memory cache of all inventory item names for fast extraction."""

    def __init__(self, items: list[str]):
        # Keep originals sorted longest-first for greedy substring matching
        self.items: list[str] = sorted(set(items), key=len, reverse=True)
        # Lowercase lookup map:  lowercase_name  →  original_name
        self._lower_map: dict[str, str] = {i.lower(): i for i in self.items}
        # Pre-split for fuzzy matching (list of lowercase names)
        self._lower_keys: list[str] = list(self._lower_map.keys())
        escaped_items = [re.escape(item) for item in self.items]
        self._substring_pattern = (
            re.compile(r"(?<!\w)(?:" + "|".join(escaped_items) + r")(?!\w)", re.I)
            if escaped_items
            else None
        )

    # -- fast path: substring scan against user text --
    def find_substring(self, text: str) -> str | None:
        """Return the longest item name found as a substring in *text*."""
        if self._substring_pattern is None:
            return None
        match = self._substring_pattern.search(text)
        if match:
            return self._lower_map.get(match.group(0).lower())
        return None

    # -- slower path: fuzzy match --
    def find_fuzzy(self, text: str, cutoff: float = 0.6) -> str | None:
        """Token-level fuzzy match against the item catalogue."""
        import difflib

        words = text.lower().split()
        # Try multi-word combos (bigrams, trigrams) first, then single words
        candidates: list[str] = []
        for n in range(min(4, len(words)), 0, -1):
            for i in range(len(words) - n + 1):
                candidates.append(" ".join(words[i : i + n]))

        for candidate in candidates:
            matches = difflib.get_close_matches(
                candidate, self._lower_keys, n=1, cutoff=cutoff
            )
            if matches:
                return self._lower_map[matches[0]]
        return None


def _load_item_cache() -> _ItemCache:
    """Load all item names from the inventory table."""
    global _item_cache
    if _item_cache is not None:
        return _item_cache

    items: list[str] = []
    try:
        from app.database.db import SessionLocal
        from app.models.inventory import Inventory

        db = SessionLocal()
        try:
            rows = db.query(Inventory.item_name).all()
            items = [r[0] for r in rows if r[0]]
        finally:
            db.close()
    except Exception as exc:
        print(f"[Intent] Could not load inventory items: {exc}")

    if not items:
        # Minimal fallback so the classifier still works without DB
        items = [
            "arishtam", "capsule", "capsules", "bottle", "bottles",
            "amber bottle", "amber bottles", "dropper", "droppers",
            "glass bottle", "glass bottles",
        ]

    _item_cache = _ItemCache(items)
    print(f"[Intent] Cached {len(items)} inventory items for extraction.")
    return _item_cache


def refresh_item_cache() -> None:
    """Force-reload item cache (call after bulk inventory imports)."""
    global _item_cache
    _item_cache = None
    _load_item_cache()


# ===================================================================
#  SEMANTIC MODEL — lazy singleton
# ===================================================================
def _get_model():
    global _model, _model_load_error
    if _model is not None or _model_load_error:
        return _model

    with _lock:
        # Double-check after acquiring lock
        if _model is not None or _model_load_error:
            return _model

        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(MODEL_NAME)
            print(f"[Intent] Loaded semantic model '{MODEL_NAME}'.")
        except Exception as exc:
            _model_load_error = str(exc)
            print(f"[Intent] Semantic model unavailable: {_model_load_error}")

    return _model


def _get_intent_embeddings() -> dict[str, np.ndarray] | None:
    global _intent_embeddings
    if _intent_embeddings is not None:
        return _intent_embeddings

    model = _get_model()
    if model is None:
        return None

    with _lock:
        if _intent_embeddings is not None:
            return _intent_embeddings

        _intent_embeddings = {}
        for intent, examples in INTENT_EXAMPLES.items():
            _intent_embeddings[intent] = model.encode(
                examples,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=64,  # encode in one shot for speed
            )

        print(f"[Intent] Cached embeddings for {len(_intent_embeddings)} intents.")
    return _intent_embeddings


def _get_semantic_index() -> _SemanticIndex | None:
    global _semantic_index
    if _semantic_index is not None:
        return _semantic_index

    intent_embeddings = _get_intent_embeddings()
    if intent_embeddings is None:
        return None

    with _lock:
        if _semantic_index is not None:
            return _semantic_index

        matrix_parts: list[np.ndarray] = []
        intents: list[str] = []
        examples: list[str] = []

        for intent, sample_texts in INTENT_EXAMPLES.items():
            embeddings = intent_embeddings[intent]
            matrix_parts.append(embeddings)
            intents.extend([intent] * len(sample_texts))
            examples.extend(sample_texts)

        _semantic_index = _SemanticIndex(
            matrix=np.vstack(matrix_parts),
            intents=tuple(intents),
            examples=tuple(examples),
        )

    return _semantic_index


def _normalize_message(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s@.-]+", " ", text.lower())).strip()


def _match_keyword_intent(user_message: str) -> IntentDetection | None:
    normalized = _normalize_message(user_message)
    has_po_id = _extract_po_id(user_message) is not None

    for rule in KEYWORD_INTENT_RULES:
        if rule.intent in {"generate_invoice", "get_po_status", "stock_arrival"} and not has_po_id:
            continue

        for pattern in rule.patterns:
            if pattern.search(normalized):
                return IntentDetection(
                    intent=rule.intent,
                    confidence=rule.confidence,
                    matched_example=pattern.pattern,
                    reason="keyword_rule_match",
                    available=True,
                )

    return None


# ===================================================================
#  CORE DETECTION
# ===================================================================
def detect_intent(user_message: str) -> IntentDetection:
    keyword_match = _match_keyword_intent(user_message)
    if keyword_match is not None:
        return keyword_match

    model = _get_model()
    semantic_index = _get_semantic_index()

    if model is None or semantic_index is None:
        return IntentDetection(
            intent=None,
            confidence=0.0,
            matched_example=None,
            reason=_model_load_error or "semantic model unavailable",
            available=False,
        )

    query_embedding = model.encode(
        [user_message],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0]

    similarities = semantic_index.matrix @ query_embedding
    best_index = int(np.argmax(similarities))
    best_score = float(similarities[best_index])
    best_intent = semantic_index.intents[best_index]
    best_example = semantic_index.examples[best_index]

    if best_score >= CONFIDENCE_THRESHOLD:
        return IntentDetection(
            intent=best_intent,
            confidence=best_score,
            matched_example=best_example,
            reason="high_confidence_match",
            available=True,
        )

    return IntentDetection(
        intent=None,
        confidence=best_score,
        matched_example=best_example,
        reason="below_threshold",
        available=True,
    )


# ===================================================================
#  ARGUMENT EXTRACTION HELPERS
# ===================================================================

# ---------- STOP-WORDS used during extraction ----------
_STOP_WORDS = frozenset({
    "them", "it", "the", "a", "an", "this", "that", "these", "those",
    "vendor", "supplier", "order", "purchase", "po", "stock", "inventory",
    "for", "of", "from", "and", "or", "in", "on", "to", "is", "are",
    "was", "were", "be", "been", "do", "does", "did", "will", "can",
    "could", "would", "should", "shall", "may", "might", "must",
    "have", "has", "had", "i", "we", "you", "my", "our",
    "check", "get", "show", "list", "see", "give", "tell", "find",
    "create", "make", "generate", "produce", "raise", "place",
    "how", "what", "where", "when", "many", "much",
    "please", "need", "want", "like", "some", "any",
})

_ITEM_BOUNDARY_WORDS = (
    "for", "from", "with", "price", "email", "vendor", "supplier", "status",
    "delivered", "arrived", "received", "tomorrow", "today", "please",
    "po", "order",
)


def _clean_extracted_phrase(phrase: str, extra_stop_words: tuple[str, ...] = ()) -> str:
    phrase = re.sub(r"[\s,.;:]+", " ", phrase).strip()
    if not phrase:
        return ""

    stop_words = _ITEM_BOUNDARY_WORDS + extra_stop_words
    phrase = re.sub(
        r"\s+(?:" + "|".join(re.escape(word) for word in stop_words) + r")\b.*$",
        "",
        phrase,
        flags=re.I,
    ).strip()
    phrase = re.sub(
        r"(?:\b(?:" + "|".join(re.escape(word) for word in stop_words) + r")\b\s*)+$",
        "",
        phrase,
        flags=re.I,
    ).strip()
    phrase = re.sub(r"\b(?:po|order)\s*#?\s*[a-z0-9-]+\b", "", phrase, flags=re.I)
    phrase = re.sub(r"\b(?:have|has|is|are)\b$", "", phrase, flags=re.I).strip()
    phrase = re.sub(r"\s+", " ", phrase).strip(" -")
    return phrase


def _extract_email(text: str) -> str | None:
    match = re.search(r"[\w.-]+@[\w.-]+\.\w+", text)
    return match.group(0) if match else None


def _extract_price(text: str) -> float | None:
    match = re.search(r"(?:price|priced?|cost|at|rs|inr)\s*(?:to\s+)?(?:rs\.?\s*|inr\s*)?(\d+(?:\.\d+)?)", text, re.I)
    if match:
        return float(match.group(1))
    return None


def _extract_item(text: str) -> str:
    """
    Extract an item name from user text.

    Strategy (fast → slow):
      1. Regex-based phrase extraction after keywords like  for / of
      2. Exact substring match against the item cache (O(n) scan, longest first)
      3. Fuzzy match against the item cache  (difflib, only on miss)
      4. Fallback to "item"
    """
    cache = _load_item_cache()
    normalized_text = _normalize_message(text)

    item_patterns = (
        r"(?:inventory|stock|quantity|availability|available)\s+(?:for|of)\s+([a-z][a-z\s-]+)",
        r"(?:for|of)\s+(?:an?\s+)?(?:\d+\s+)?([a-z][a-z\s-]+)",
        r"(?:buy|order|purchase|procure|restock|reorder|receive|received|deliver|delivered|arrived|update)\s+(?:\d+\s+)?([a-z][a-z\s-]+)",
    )

    phrase_candidates: list[str] = []

    # --- 1. Regex phrase capture around common ERP verbs ---
    for pattern in item_patterns:
        match = re.search(pattern, normalized_text, re.I)
        if not match:
            continue

        phrase = _clean_extracted_phrase(match.group(1), extra_stop_words=("if", "and"))
        if phrase and phrase.lower() not in _STOP_WORDS:
            found = cache.find_substring(phrase)
            if found:
                return found
            found = cache.find_fuzzy(phrase)
            if found:
                return found
            if len(phrase) >= 3:
                phrase_candidates.append(phrase)

    # --- 2.  Substring scan of the full text against the item cache ---
    found = cache.find_substring(normalized_text)
    if found:
        return found

    # --- 3.  Fuzzy match ---
    found = cache.find_fuzzy(normalized_text)
    if found:
        return found

    for phrase in phrase_candidates:
        found = cache.find_fuzzy(phrase)
        if found:
            return found

    if phrase_candidates:
        return phrase_candidates[0]

    # --- 4.  Last-resort: try to pull any remaining 2+ char noun ---
    # Remove common ERP verbs/prepositions and grab the first remaining word
    stripped = re.sub(
        r"\b(?:check|show|get|how|many|much|do|we|have|left|in|stock|"
        r"is|the|a|an|of|for|what|quantity|inventory|available|remaining|"
        r"received|receive|arrived|delivered|delivery|update|mark|po|order)\b",
        "",
        normalized_text,
        flags=re.I,
    ).strip()
    tokens = [t for t in stripped.split() if len(t) >= 3 and t.lower() not in _STOP_WORDS]
    if tokens:
        return " ".join(tokens[:3])  # max 3-word fallback

    return "item"


def _extract_quantity(text: str, default: int = 1) -> int:
    """Extract the first explicit quantity while ignoring PO identifiers."""
    scrubbed = re.sub(r"\b\d{6}-[A-Z0-9]+-\d{3}\b", " ", text, flags=re.I)
    scrubbed = re.sub(r"\b(?:po|order)\s*#?\s*\d+\b", " ", scrubbed, flags=re.I)
    match = re.search(r"\b(?:qty|quantity|for|of)?\s*(\d+)\b", scrubbed, re.I)
    return int(match.group(1)) if match else default


def _extract_po_id(text: str) -> str | None:
    """Extract PO ID — supports both YYMMDD-CODE-NNN and plain numeric."""
    # New format:  260324-AYU001-001
    match = re.search(r"(\d{6}-[A-Z0-9]+-\d{3})", text, re.I)
    if match:
        return match.group(1).upper()

    # Legacy numeric:  po 5 / order #3
    match = re.search(r"(?:po|order|#)\s*#?\s*(\d+)", text, re.I)
    if match:
        return match.group(1)

    return None


def _extract_vendor(text: str) -> str:
    """Extract vendor name after from / vendor / supplier keywords."""
    normalized_text = _normalize_message(text)
    patterns = (
        r"from\s+(?:vendor\s+|supplier\s+)?(?:named\s+|called\s+)?([a-z][a-z0-9\s&.-]+?)(?:\s+(?:for|at|with|price|email|item)\b|$)",
        r"(?:vendor|supplier)\s+(?:named\s+|called\s+)?([a-z][a-z0-9\s&.-]+?)(?:\s+(?:for|at|with|price|email|item)\b|$)",
        r"(?:update|change|modify|edit|set)\s+([a-z][a-z0-9\s&.-]+?)\s+(?:vendor\s+)?(?:email|price|contact|details?)\b",
    )

    for pattern in patterns:
        match = re.search(pattern, normalized_text, re.I)
        if match:
            vendor = _clean_extracted_phrase(
                match.group(1),
                extra_stop_words=("item", "details", "contact"),
            )
            if vendor and vendor.lower() not in _STOP_WORDS:
                return vendor
    return "default_vendor"


# ---------- Leave arguments ----------
def _extract_leave_args(text: str) -> dict[str, str]:
    reason = "Personal"
    reason_patterns = [
        r"(?:because|reason|due to)\s+(.+?)(?:\s+on|\s+tomorrow|\s+for|\.|\s*$)",
        r"(?:i(?:'m| am))\s+(.+?)(?:\s+on|\s+need|\.|,|\s*$)",
    ]
    for pattern in reason_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            reason = match.group(1).strip()
            break

    lowered = text.lower()
    if "sick" in lowered:
        reason = "Sick"
    elif "personal" in lowered:
        reason = "Personal"

    today = datetime.now()
    if "tomorrow" in lowered:
        leave_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if match:
            leave_date = match.group(1)
        else:
            match = re.search(
                r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?"
                r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*",
                text,
                re.I,
            )
            if match:
                day = int(match.group(1))
                month_map = {
                    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
                    "may": 5, "jun": 6, "jul": 7, "aug": 8,
                    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
                }
                month_key = match.group(2).lower()[:3]
                leave_date = f"{today.year}-{month_map[month_key]:02d}-{day:02d}"
            else:
                leave_date = today.strftime("%Y-%m-%d")

    leave_type = "Full Day"
    if "1st half" in lowered or "first half" in lowered:
        leave_type = "1st Half"
    elif "2nd half" in lowered or "second half" in lowered:
        leave_type = "2nd Half"
    elif "half" in lowered:
        leave_type = "1st Half"

    return {"reason": reason, "leave_date": leave_date, "leave_type": leave_type}


# ---------- Vendor add arguments ----------
def _extract_vendor_add_args(text: str) -> dict[str, Any]:
    vendor_name = _extract_vendor(text)
    if vendor_name == "default_vendor":
        vendor_name = "Unknown"

    item_name = _extract_item(text)

    price = _extract_price(text) or 0.0

    email = _extract_email(text)

    compact_text = _normalize_message(text)
    compact_text = re.sub(r"\b(?:add|register|create|onboard|save|new)\b", " ", compact_text, flags=re.I)
    compact_text = re.sub(r"\b(?:vendor|supplier)\b", " ", compact_text, flags=re.I)
    if email:
        compact_text = compact_text.replace(email.lower(), " ")
    compact_text = re.sub(r"\b(?:price|at|rs|inr)\b", " ", compact_text, flags=re.I)
    compact_text = re.sub(r"\b\d+(?:\.\d+)?\b", " ", compact_text)
    compact_tokens = [t for t in compact_text.split() if t.lower() not in _STOP_WORDS]

    compact_add_request = re.search(r"\b(?:add|register|create|onboard|save)\b.*\b(?:vendor|supplier)\b", text, re.I)
    explicit_vendor_fields = re.search(r"\b(?:for|at|with|price|email)\b", text, re.I)

    if compact_add_request and not explicit_vendor_fields and compact_tokens:
        vendor_name = compact_tokens[0]
        if len(compact_tokens) > 1:
            fallback_item = " ".join(compact_tokens[1:])
            cache = _load_item_cache()
            item_name = cache.find_substring(fallback_item) or fallback_item

    if vendor_name == "Unknown" and compact_tokens:
        vendor_name = compact_tokens[0]

    if item_name == "item" and len(compact_tokens) > 1:
        fallback_item = " ".join(compact_tokens[1:])
        cache = _load_item_cache()
        item_name = cache.find_substring(fallback_item) or fallback_item

    if price <= 0:
        trailing_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", _normalize_message(text))
        if trailing_numbers:
            price = float(trailing_numbers[-1])

    return {
        "vendor_name": vendor_name,
        "item_name": item_name,
        "price": price,
        "email": email,
    }


# ---------- Vendor update arguments ----------
def _extract_vendor_update_args(text: str) -> dict[str, Any]:
    vendor_name = _extract_vendor(text)

    email = _extract_email(text)

    price = _extract_price(text)

    args: dict[str, Any] = {"vendor_name": vendor_name}
    if email:
        args["email"] = email
    if price is not None:
        args["price"] = price
    return args


# ===================================================================
#  PLAN BUILDER
# ===================================================================
def _build_plan_for_intent(intent: str, user_message: str) -> dict[str, Any] | None:
    tool_name = INTENT_TO_TOOL[intent]

    if intent == "check_inventory":
        args = {"item": _extract_item(user_message)}

    elif intent == "create_purchase_order":
        item = _extract_item(user_message)
        if item == "item":
            return None
        args = {
            "item": item,
            "quantity": _extract_quantity(user_message),
            "vendor_name": _extract_vendor(user_message),
        }

    elif intent == "get_po_status":
        po_id = _extract_po_id(user_message)
        if not po_id:
            return None
        args = {"po_id": po_id}

    elif intent == "generate_invoice":
        po_id = _extract_po_id(user_message)
        if not po_id:
            return None
        args = {"po_id": po_id}

    elif intent == "get_vendors":
        args = {}

    elif intent == "add_vendor":
        args = _extract_vendor_add_args(user_message)

    elif intent == "update_vendor":
        args = _extract_vendor_update_args(user_message)

    elif intent == "apply_leave":
        args = _extract_leave_args(user_message)

    elif intent == "stock_arrival":
        item = _extract_item(user_message)
        quantity = _extract_quantity(user_message, default=0)
        if item == "item" or quantity <= 0:
            return None
        args = {
            "item": item,
            "quantity": quantity,
        }
        po_id = _extract_po_id(user_message)
        if po_id:
            args["po_id"] = po_id

    else:
        return None

    return {
        "type": "action",
        "steps": [{"type": "tool", "name": tool_name, "args": args}],
    }


def _get_missing_required_arguments(intent: str, user_message: str) -> list[str]:
    if intent in {"check_inventory", "create_purchase_order"}:
        return ["item"] if _extract_item(user_message) == "item" else []

    if intent in {"get_po_status", "generate_invoice"}:
        return ["po_id"] if _extract_po_id(user_message) is None else []

    if intent == "add_vendor":
        args = _extract_vendor_add_args(user_message)
        missing: list[str] = []
        if args["vendor_name"] == "Unknown":
            missing.append("vendor_name")
        if args["item_name"] == "item":
            missing.append("item_name")
        if args["price"] <= 0:
            missing.append("price")
        return missing

    if intent == "update_vendor":
        args = _extract_vendor_update_args(user_message)
        missing: list[str] = []
        if args["vendor_name"] == "default_vendor":
            missing.append("vendor_name")
        if "email" not in args and "price" not in args:
            missing.append("email_or_price")
        return missing

    if intent == "stock_arrival":
        missing: list[str] = []
        if _extract_item(user_message) == "item":
            missing.append("item")
        if _extract_quantity(user_message, default=0) <= 0:
            missing.append("quantity")
        return missing

    return []


def build_clarification_response(intent: str | None, user_message: str) -> str | None:
    if not intent:
        return None

    missing = _get_missing_required_arguments(intent, user_message)
    if not missing:
        return None

    prompts = {
        ("check_inventory", "item"): "Which item should I check in inventory?",
        ("create_purchase_order", "item"): "Which item should I create the purchase order for?",
        ("get_po_status", "po_id"): "Which PO ID should I check?",
        ("generate_invoice", "po_id"): "Which PO ID should I generate the invoice for?",
        ("add_vendor", "vendor_name"): "What is the vendor name?",
        ("add_vendor", "item_name"): "Which item does this vendor supply?",
        ("add_vendor", "price"): "What price should I save for this vendor?",
        ("update_vendor", "vendor_name"): "Which vendor should I update?",
        ("update_vendor", "email_or_price"): "What should I update for the vendor: email, price, or both?",
        ("stock_arrival", "item"): "Which item arrived?",
        ("stock_arrival", "quantity"): "How many units arrived?",
    }

    if len(missing) == 1:
        return prompts.get((intent, missing[0]))

    if intent == "add_vendor":
        return "Please share the vendor name, supplied item, and price."
    if intent == "update_vendor":
        return "Please share the vendor name and what to update: email, price, or both."
    if intent == "stock_arrival":
        return "Please share the item name and quantity that arrived."

    return "I need one more detail to continue."


# ===================================================================
#  PUBLIC API
# ===================================================================
def classify_and_plan(
    user_message: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """
    Detect intent and — if confident — build a ready-to-execute plan.

    Returns
    -------
    (plan_or_None, intent_metadata_dict)
    """
    detection = detect_intent(user_message)
    metadata = detection.to_dict()

    if detection.intent is None:
        return None, metadata

    missing_arguments = _get_missing_required_arguments(detection.intent, user_message)
    if missing_arguments:
        metadata["reason"] = "missing_required_arguments"
        metadata["missing_arguments"] = missing_arguments
        return None, metadata

    plan = _build_plan_for_intent(detection.intent, user_message)
    if plan is None:
        metadata["reason"] = "missing_required_arguments"
        return None, metadata

    plan["intent_detection"] = metadata
    return plan, metadata


def preload_model() -> None:
    """
    Eagerly load the semantic model, intent embeddings, and item cache.
    Call this at server startup so the first chat request isn't slow.
    """
    import time

    t0 = time.time()
    _get_model()
    _get_intent_embeddings()
    _get_semantic_index()
    _load_item_cache()
    elapsed = (time.time() - t0) * 1000
    print(f"[Intent] Preload complete in {elapsed:.0f}ms.")
