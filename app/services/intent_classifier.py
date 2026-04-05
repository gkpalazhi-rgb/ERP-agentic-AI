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
CONFIDENCE_THRESHOLD = 0.65

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
        "stock check capsules",
        "inventory balance for general items",
        "how many units of arishtam remain",
        "check stock of giloy juice",
        "what is the balance quantity",
        "show stock ledger",
        "warehouse check for neem tablets",
        "how much stock of ashwagandha capsules",
        "do we have enough chyawanprash left",
        "current quantity of triphala churnam",
        "check if we are low on glucose bottles",
        "available inventory for giloy juice",
        "how much left... that ayurvedic oil one",
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
        "procurement request for 50 units of arishtam",
        "we need to restock chyawanprash urgently",
        "buy 200 boxes of raw materials quickly",
        "place an order for 20 syruip bottles from medlife",
        "make a po for that oil we always use",
        "get stock ready and order 60 units of triphala",
        "buy more neem tablets",
        "arrange 30 turmeric powder packets",
        "purchase arishtam 40 bottles",
        "i want to order 25 insulin syringes",
        "order stuff quickly",
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
        "po status 55",
        "has the order been shipped or approved",
        "where is my order 123",
        "what is the delivery status of po 876",
        "track po AYU-2303-001",
        "po update needed for last order",
        "did the order for syringes arrive",
        "who approved the last po",
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
        "make billing for the recent po",
        "invoice for syringes purchase",
        "generate the billing document for purchase order 123",
        "create bill for AYU-2303-001",
        "download receipt for order #55",
        "print invoice for last purchase",
        "payment receipt for order",
        "make billing for the recent po",
        "invoice for syringes purchase",
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
        "who sells arishtam to us",
        "vendor details for capsules",
        "which vendor provides giloy juice",
        "who sells arishtam to us",
        "get me all suppliers for ayurvedic oils",
        "find vendor for turmeric powder",
        "who are our current vendors",
        "vendor list",
        "supplier lookup",
        "who supplies ashwagandha",
        "vendors for syringes",
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
        "add new vendor medlife suppliers email med@life.com for syringes",
        "add supplier dr herbs email dr@herbs.com",
        "include new supplier ayurveda store",
        "register vendor ayu pharma for capsules",
        "onboard supplier herbal world email herbal@world.com",
        "add vendor for turmeric powder with price 120",
        "new vendor: greenleaf, supplies giloy juice",
        "create vendor entry for medsuppliers syringes",
        "add vendor quickmed for insulin syringes",
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
        "correct vendor name for medsuppliers",
        "change price of syringes vendor to 150",
        "modify vendor herbal world contact info",
        "update supplier for capsules",
        "edit vendor details for ayu pharma",
        "change vendor email for greenleaf",
        "update price for turmeric vendor",
        "update supplier info for arishtam",
        "change vendor contact number",
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
        "i won't be coming today",
        "i need sick leave for 2 days",
        "book leave on 25th march",
        "leave application for personal reasons",
        "i need a day off",
        "apply leave next monday urgent",
        "take leave for medical reasons",
        "i am on leave today",
        "leave pls",
        "apply sick leave",
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
        "update stock arrival for capsules",
        "log stock arrival for giloy juice",
        "warehouse received 30 bottles",
        "inventory received for arishtam",
        "mark po 44 delivered",
        "stock arrived for po 12345",
        "mark delivery received for AYU-2303-001",
        "goods received 50 syringes",
        "delivery of turmeric powder received",
        "items from po XYZ-999 arrived",
        "shipment of cargo came in today",
        "warehouse unloaded items",
        "mark po 260324-AYU001-001 as delivered",
    ],
    "get_leaves_today": [
        "who all are on leave",
        "show me leaves today",
        "who is absent",
        "anyone on leave today",
        "get leaves list",
    ],
    "generate_daily_purchase_report": [
        "show all the purchase orders done today",
        "report of purchases done in that day",
        "report of today's purchases",
        "daily purchase report",
        "what did we order today",
    ],
    "get_low_stock_items": [
        "show low stock items",
        "list low stock products",
        "what items are below reorder level",
        "show stock alerts",
        "find items below 50 units",
        "which products are running low",
    ],
    "cancel_purchase_order": [
        "cancel po 260324-AYU001-001",
        "cancel purchase order 25",
        "void po 55",
        "cancel order 1002",
        "please cancel this purchase order",
        "stop po 260405-PSOIL-001",
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
    "get_leaves_today": "get_leaves_today",
    "generate_daily_purchase_report": "generate_daily_purchase_report",
    "remove_expired_stock": "remove_expired_stock",
    "get_low_stock_items": "get_low_stock_items",
    "cancel_purchase_order": "cancel_purchase_order",
}


@dataclass(frozen=True)
class _KeywordIntentRule:
    intent: str
    patterns: tuple[re.Pattern[str], ...]
    confidence: float = 0.98


KEYWORD_INTENT_RULES: tuple[_KeywordIntentRule, ...] = (
    _KeywordIntentRule(
        intent="get_leaves_today",
        patterns=(
            re.compile(r"\b(?:who all are|who is|show(?: me)?)\b.*\bleave[s]?\b", re.I),
            re.compile(r"\b(?:anyone on|who is on)\b.*\bleave\b", re.I),
        ),
        confidence=0.98,
    ),
    _KeywordIntentRule(
        intent="generate_daily_purchase_report",
        patterns=(
            re.compile(r"\b(?:show|generate|report of)\b.*\b(?:purchases?|purchase orders?)\b.*\b(?:today|in that day)\b", re.I),
            re.compile(r"\b(?:daily purchase report|report of purchases)\b", re.I),
        ),
        confidence=0.98,
    ),
    _KeywordIntentRule(
        intent="remove_expired_stock",
        patterns=(
            re.compile(r"\b(?:remove|discard|subtract|reduce|deduct|throw away)\b.*\b(?:expired|damaged|broken)\b", re.I),
            re.compile(r"\b(?:expired|damaged)\b.*\b(?:remove|discard|reduce|deduct)\b", re.I),
        ),
        confidence=0.95,
    ),
    _KeywordIntentRule(
        intent="get_low_stock_items",
        patterns=(
            re.compile(r"\b(?:show|list|get|display|find)\b.*\blow\s+stock\b", re.I),
            re.compile(r"\blow\s+stock\b", re.I),
            re.compile(r"\b(?:stock\s+alert|stock\s+alerts)\b", re.I),
            re.compile(r"\b(?:below|under|less than|<)\s*\d+\s*(?:units?)?\b.*\bstock\b", re.I),
        ),
        confidence=0.99,
    ),
    _KeywordIntentRule(
        intent="cancel_purchase_order",
        patterns=(
            re.compile(r"\b(?:cancel|void|stop|abort)\b.*\b(?:po|purchase order|order)\b", re.I),
            re.compile(r"\b(?:po|purchase order|order)\b.*\b(?:cancel|void|stop)\b", re.I),
        ),
        confidence=0.99,
    ),
    _KeywordIntentRule(
        intent="generate_invoice",
        patterns=(
            re.compile(r"\b(?:generate|create|make|prepare|print|download|export)\b.*\b(?:invoice|bill|receipt)\b", re.I),
            re.compile(r"\b(?:invoice|bill|receipt)\b.*\b(?:po|order)\b", re.I),
        ),
    ),
    _KeywordIntentRule(
        intent="get_po_status",
        patterns=(
            re.compile(r"\b(?:status|track|where|pending|cost|total cost|summary|details)\b.*\b(?:po|purchase order|order)\b", re.I),
            re.compile(r"\b(?:po|purchase order|order)\b.*\b(?:status|cost|pending|summary|details)\b", re.I),
            re.compile(r"\b(?:where is|what happened to|status of)\b.*\b(?:po|purchase order|order)\b", re.I),
        ),
    ),
    _KeywordIntentRule(
        intent="stock_arrival",
        patterns=(
            re.compile(r"\b(?:arrived|received|delivered|receipt|goods receipt)\b.*\b(?:po|purchase order|stock|shipment|goods|items|units)\b", re.I),
            re.compile(r"\b(?:po|purchase order|stock|shipment|goods|items|warehouse)\b.*\b(?:arrived|received)\b", re.I),
            re.compile(r"\b(?:update|mark|log)\b.*\b(?:stock|inventory|arrival)\b.*\b(?:arrived|received|delivered)?\b", re.I),
            # "11 neem tab arrived" — <quantity> <text> arrived/received/delivered
            re.compile(r"\b\d+\s+[a-z].+\b(?:arrived|received|delivered)\b", re.I),
            # "260328-NEMA-001 arrived" — PO-ID + arrived
            re.compile(r"\b\d{6}-[A-Z0-9]+-\d{3}\b.*\b(?:arrived|received|delivered)\b", re.I),
            # "arrived ... ID 260328-NEMA-001" or "... ID 260328-NEMA-001 arrived"
            re.compile(r"\b(?:arrived|received|delivered)\b.*\b\d{6}-[A-Z0-9]+-\d{3}\b", re.I),
            # "neem tab arrived, ID ..." — item text + arrived + ID/PO ref
            re.compile(r"\b(?:arrived|received|delivered)\b\s*[,.]?\s*\b(?:id|po)\b", re.I),
        ),
        confidence=0.98,
    ),
    _KeywordIntentRule(
        intent="check_inventory",
        patterns=(
            re.compile(r"\b(?:check|show|tell)\b.*\b(?:inventory|stock|quantity|levels|balance)\b", re.I),
            re.compile(r"\b(?:inventory|stock|quantity)\b.*\b(?:left|remaining|available)\b", re.I),
            # "how many X are left" / "how many X"
            re.compile(r"\bhow many\b", re.I),
            # "do we have X" / "do you have X"
            re.compile(r"\b(?:do we have|do you have|are there any)\b", re.I),
            # "count X"
            re.compile(r"\bcount\b\s+[a-z]", re.I),
        ),
        confidence=0.93,
    ),
    _KeywordIntentRule(
        intent="create_purchase_order",
        patterns=(
            re.compile(r"\b(?:create|raise|place|make|issue|new)\b.*\b(?:purchase order|po|order)\b", re.I),
            re.compile(r"\b(?:restock|reorder|procure|replenish)\b", re.I),
            re.compile(r"\b(?:can you|please)\b.*\border\b", re.I),
            re.compile(r"\b(?:buy|order|purchase)\b\s+(?:\d+)?\s*[a-zA-Z]+", re.I),
        ),
        confidence=0.94,
    ),
    _KeywordIntentRule(
        intent="get_vendors",
        patterns=(
            re.compile(r"\b(?:show|list|get|display|find|who)\b.*\b(?:vendors|vendor|suppliers|supplier)\b", re.I),
            re.compile(r"\b(?:supplier directory|vendor catalog)\b", re.I),
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
            re.compile(r"\b(?:apply|request|submit|take|book|mark|put)\b.*\bleaves?\b", re.I),
            re.compile(r"\b(?:sick leave|casual leave|annual leave)\b", re.I),
            re.compile(r"\bleave\b(?:,?\s+\d+|,?\s+(?:tomorrow|today|reason|full(?: day)?|half(?: day)?|sick|casual))", re.I),
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
#  VENDOR CACHE — loads vendors from the DB once, thread-safe
# ===================================================================
class _VendorCache:
    """In-memory cache of all vendor names for fallback matching."""
    def __init__(self, vendors: list[str]):
        # Keep longest first for greedy matching
        self.vendors: list[str] = sorted(set(vendors), key=len, reverse=True)
        self._lower_map = {}
        for v in self.vendors:
            v_norm = _normalize_message(v)
            if v_norm:
                self._lower_map[v_norm] = v

    def find_vendor(self, text: str) -> str | None:
        normalized_text = _normalize_message(text)
        for v_norm, v_orig in self._lower_map.items():
            # If the entire message equals the vendor name, accept it
            if normalized_text == v_norm:
                return v_orig
            # Avoid matching single-letter words or extremely generic terms globally
            if len(v_norm) < 4:
                continue
            
            v_escaped = re.escape(v_norm)
            if re.search(r'(?<!\w)' + v_escaped + r'(?!\w)', normalized_text, re.I):
                return v_orig
                
        return None

_vendor_cache: _VendorCache | None = None

def _load_vendor_cache() -> _VendorCache:
    global _vendor_cache
    if _vendor_cache is not None:
        return _vendor_cache

    vendors: list[str] = []
    try:
        from app.database.db import SessionLocal
        from app.models.vendor import Vendor
        db = SessionLocal()
        try:
            rows = db.query(Vendor.vendor_name).all()
            vendors = [r[0] for r in rows if r[0]]
        finally:
            db.close()
    except Exception as exc:
        print(f"[Intent] Could not load vendors: {exc}")

    _vendor_cache = _VendorCache(vendors)
    print(f"[Intent] Cached {len(vendors)} vendors for extraction.")
    return _vendor_cache


def refresh_vendor_cache() -> None:
    """Force-reload vendor cache."""
    global _vendor_cache
    _vendor_cache = None
    _load_vendor_cache()



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
    normalized_text = re.sub(r"\b(\d+)\s*(ml|mg|kg|gm|g|l|lt|ltr)\b", r"\1 \2", normalized_text, flags=re.I)

    item_patterns = (
        r"(?:inventory|stock|quantity|availability|available)\s+(?:for|of)\s+([a-z0-9][a-z0-9\s-]+)",
        r"(?:for|of)\s+(?:an?\s+)?(?:\d+\s+)?([a-z0-9][a-z0-9\s-]+)",
        r"(?:buy|order|purchase|procure|restock|reorder|receive|received|deliver|delivered|arrived|update)\s+(?:\d+\s+)?([a-z0-9][a-z0-9\s-]+)",
        # "11 neem tab arrived" — <quantity> <item> <arrival verb>
        r"\b\d+\s+([a-z][a-z0-9\s-]+?)\s+(?:arrived|received|delivered|has\s+arrived|have\s+arrived)\b",
        # "how many X", "do we have X", "are there any X", "count X"
        r"\b(?:how many|do we have|are there any|count|do you have)\s+([a-z0-9][a-z0-9\s-]+?)(?:\s+(?:left|remaining|in stock|available))?$",
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
    # Remove PO ID patterns so they aren't mistaken for item names
    stripped = re.sub(r"\b\d{6}-[A-Z0-9]+-\d{3}\b", " ", stripped, flags=re.I)
    stripped = re.sub(r"\b(?:id)\s+\S+", " ", stripped, flags=re.I)
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


def _extract_low_stock_threshold(text: str, default: int = 50) -> int:
    threshold_patterns = (
        r"\b(?:below|under|less than)\s*(\d+)\b",
        r"\b(?:threshold|limit)\s*(?:of|is|=)?\s*(\d+)\b",
        r"\bstock\s*<\s*(\d+)\b",
    )
    for pattern in threshold_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = int(match.group(1))
            return value if value > 0 else default
    return default


def _extract_cancellation_reason(text: str) -> str | None:
    patterns = (
        r"\b(?:because|due to|reason)\s*[:\-]?\s*(.+)$",
        r"\b(?:cancel|void|stop)\b.*?\b(?:for|as)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            reason = match.group(1).strip(" .")
            if reason:
                return reason
    return None


def _extract_po_id(text: str) -> str | None:
    """Extract PO ID — supports both YYMMDD-CODE-NNN and plain numeric."""
    # New format:  260324-AYU001-001
    match = re.search(r"(\d{6}-[A-Z0-9]+-\d{3})", text, re.I)
    if match:
        return match.group(1).upper()

    # Legacy generic:  po 5 / order #3 / po abc-999
    match = re.search(r"(?:po|order|#)\s*#?\s*([a-z0-9-]+)", text, re.I)
    if match:
        return match.group(1).upper()

    return None


def _extract_vendor(text: str) -> str:
    """Extract vendor name after from / vendor / supplier keywords or via DB cache."""
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

    # Fallback to DB exact match cache
    try:
        cache = _load_vendor_cache()
        found = cache.find_vendor(text)
        if found:
            return found
    except Exception:
        pass

    return "default_vendor"


# ---------- Leave arguments ----------
def _extract_leave_args(text: str) -> dict[str, str]:
    reason = "Personal"
    reason_patterns = [
        r"(?:because|reason|due to)[\s:]+(.+?)(?:\s+on|\s+tomorrow|\s+for|\.|\s*$|,\s*)",
        r"(?:i(?:'m| am))\s+(.+?)(?:\s+on|\s+need|\.|,|\s*$)",
    ]
    for pattern in reason_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            reason = match.group(1).strip()
            # If there's an appointment, we preserve the text.
            break

    lowered = text.lower()
    if reason == "Personal":
        # Extract leftover text as a fallback reason
        cleaned = re.sub(r"\b(can|you|please|i|want|to|apply|request|submit|take|book|mark|put|leave|leaves|for|on|full day|half day|1st half|2nd half|first half|second half)\b", " ", text, flags=re.I)
        # Remove date formats
        cleaned = re.sub(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?\b", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", cleaned)
        # Remove relative/weekday date words from reason text
        cleaned = re.sub(r"\b(?:today|tomorrow|day after tomorrow)\b", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"\bnext\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"[,._/-]", " ", cleaned).strip()
        cleaned = " ".join(cleaned.split())
        
        if len(cleaned) > 3 and not cleaned.isspace():
            reason = cleaned.capitalize()
        elif "sick" in lowered:
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
                r"(?:(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?)?"
                r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
                r"(?:\s+(\d{1,2})(?:st|nd|rd|th)?)?",
                text,
                re.I,
            )
            if match and (match.group(1) or match.group(3)):
                day = int(match.group(1) or match.group(3))
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

    email = _extract_email(text)
    item_name = _extract_item(text)
    item_category = "General" if item_name == "item" else item_name

    vendor_code = None
    code_match = re.search(r"(?:vendor\s*code|code)\s*[:#-]?\s*([A-Z0-9-]{3,})", text, re.I)
    if code_match:
        vendor_code = code_match.group(1).upper()

    location = None
    location_match = re.search(r"(?:location|located at|in)\s+([a-zA-Z][a-zA-Z0-9,\\s.-]+)", text, re.I)
    if location_match:
        location = location_match.group(1).strip()

    compact_text = _normalize_message(text)
    compact_text = re.sub(r"\b(?:add|register|create|onboard|save|new)\b", " ", compact_text, flags=re.I)
    compact_text = re.sub(r"\b(?:vendor|supplier)\b", " ", compact_text, flags=re.I)
    if email:
        compact_text = compact_text.replace(email.lower(), " ")
    compact_text = re.sub(r"\b(?:price|at|rs|inr|code|location)\b", " ", compact_text, flags=re.I)
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
        item_category = cache.find_substring(fallback_item) or fallback_item

    args: dict[str, Any] = {
        "vendor_name": vendor_name,
        "item_category": item_category,
        "location": location or "Unknown",
        "email": email,
    }
    if vendor_code:
        args["vendor_code"] = vendor_code
    return args


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

    elif intent == "get_low_stock_items":
        args = {"threshold": _extract_low_stock_threshold(user_message)}

    elif intent == "create_purchase_order":
        item = _extract_item(user_message)
        if item == "item":
            return None
        vendor = _extract_vendor(user_message)
        if vendor == "default_vendor":
            return None  # Will trigger missing_required_arguments -> vendor clarification
        args = {
            "item": item,
            "quantity": _extract_quantity(user_message),
            "vendor_name": vendor,
        }

    elif intent == "get_po_status":
        po_id = _extract_po_id(user_message)
        if not po_id:
            return None
        args = {"po_id": po_id}

    elif intent == "cancel_purchase_order":
        po_id = _extract_po_id(user_message)
        if not po_id:
            return None
        args = {"po_id": po_id}
        cancel_reason = _extract_cancellation_reason(user_message)
        if cancel_reason:
            args["cancellation_reason"] = cancel_reason

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

    elif intent == "get_leaves_today":
        args = {}

    elif intent == "generate_daily_purchase_report":
        args = {}

    elif intent == "remove_expired_stock":
        item = _extract_item(user_message)
        quantity = _extract_quantity(user_message, default=0)
        reason = "expired"
        if "damaged" in user_message.lower() or "broken" in user_message.lower():
            reason = "damaged"
        
        if item == "item":
            return None
        if quantity <= 0:
            return None
        
        args = {"item": item, "quantity": quantity, "reason": reason}

    elif intent == "stock_arrival":
        item = _extract_item(user_message)
        quantity = _extract_quantity(user_message, default=0)
        po_id = _extract_po_id(user_message)
        # If we have a PO ID, we can look up the item from the PO record —
        # so only fail if BOTH item and po_id are missing, or quantity is zero.
        if item == "item" and not po_id:
            return None
        if quantity <= 0 and not po_id:
            return None
        args = {
            "item": item,
            "quantity": quantity if quantity > 0 else 0,
        }
        if po_id:
            args["po_id"] = po_id

    else:
        return None

    return {
        "type": "action",
        "steps": [{"type": "tool", "name": tool_name, "args": args}],
    }


def _get_missing_required_arguments(intent: str, user_message: str) -> list[str]:
    if intent in {"check_inventory"}:
        return ["item"] if _extract_item(user_message) == "item" else []

    if intent == "create_purchase_order":
        missing: list[str] = []
        if _extract_item(user_message) == "item":
            missing.append("item")
        if _extract_vendor(user_message) == "default_vendor":
            missing.append("vendor_name")
        return missing

    if intent in {"get_po_status", "generate_invoice", "cancel_purchase_order"}:
        return ["po_id"] if _extract_po_id(user_message) is None else []

    if intent == "add_vendor":
        args = _extract_vendor_add_args(user_message)
        missing: list[str] = []
        if args["vendor_name"] == "Unknown":
            missing.append("vendor_name")
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
        has_po_id = _extract_po_id(user_message) is not None
        # If we have a PO ID, item and quantity can be resolved from the PO record
        if not has_po_id:
            if _extract_item(user_message) == "item":
                missing.append("item")
            if _extract_quantity(user_message, default=0) <= 0:
                missing.append("quantity")
        return missing

    if intent == "remove_expired_stock":
        missing: list[str] = []
        if _extract_item(user_message) == "item":
            missing.append("item")
        if _extract_quantity(user_message, default=0) <= 0:
            missing.append("quantity")
        return missing

    return []


def _get_vendor_list_prompt() -> str:
    """Query the database for all vendors and return a formatted prompt."""
    try:
        from app.database.db import SessionLocal
        from app.models.vendor import Vendor

        db = SessionLocal()
        try:
            vendors = db.query(Vendor).order_by(Vendor.vendor_name).all()
            if vendors:
                vendor_lines = [f"  {i+1}. {v.vendor_name}" for i, v in enumerate(vendors)]
                return (
                    "Which vendor should I place this order with? "
                    "Here are the available vendors:\n"
                    + "\n".join(vendor_lines)
                    + "\n\nPlease type the vendor name."
                )
        finally:
            db.close()
    except Exception:
        pass

    return "Which vendor should I place this order with?"

def build_clarification_response(intent: str | None, user_message: str) -> str | None:
    if not intent:
        return None

    missing = _get_missing_required_arguments(intent, user_message)
    if not missing:
        return None

    prompts = {
        ("check_inventory", "item"): "Which item should I check in inventory?",
        ("remove_expired_stock", "item"): "Which item has expired and needs to be removed from the inventory?",
        ("remove_expired_stock", "quantity"): "How many units have expired and should be removed?",
        ("create_purchase_order", "item"): "Which item should I create the purchase order for?",
        ("create_purchase_order", "vendor_name"): _get_vendor_list_prompt(),
        ("get_po_status", "po_id"): "Which PO ID should I check?",
        ("cancel_purchase_order", "po_id"): "Which PO ID should I cancel?",
        ("generate_invoice", "po_id"): "Which PO ID should I generate the invoice for?",
        ("add_vendor", "vendor_name"): "What is the vendor name?",
        ("add_vendor", "item_category"): "Which item category does this vendor supply?",
        ("add_vendor", "location"): "What is the vendor location?",
        ("update_vendor", "vendor_name"): "Which vendor should I update?",
        ("update_vendor", "email_or_price"): "What should I update for the vendor: email or price?",
        ("stock_arrival", "item"): "Which item arrived?",
        ("stock_arrival", "quantity"): "How many units arrived?",
    }

    if len(missing) == 1:
        return prompts.get((intent, missing[0]))

    if intent == "add_vendor":
        return "Please share the vendor name."
    if intent == "update_vendor":
        return "Please share the vendor name and what to update: email or price."
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
    _load_vendor_cache()
    elapsed = (time.time() - t0) * 1000
    print(f"[Intent] Preload complete in {elapsed:.0f}ms.")
