import json
from typing import Iterable


AVAILABLE_FEATURES: tuple[str, ...] = (
    "chat",
    "dashboard",
    "inventory",
    "purchase_orders",
    "vendors",
    "leaves",
    "users",
)

FEATURE_ALIASES: dict[str, str] = {
    "leave": "leaves",
    "purchase_order": "purchase_orders",
    "purchase_orders": "purchase_orders",
}

DEFAULT_FEATURES_BY_ROLE: dict[str, list[str]] = {
    "admin": list(AVAILABLE_FEATURES),
    "administrator": list(AVAILABLE_FEATURES),
    "employee": ["chat", "dashboard", "inventory", "vendors", "leaves"],
    "staff": ["chat", "dashboard", "inventory", "vendors", "leaves"],
    "user": ["chat", "dashboard", "inventory", "vendors", "leaves"],
}

FEATURE_TO_TOOLS: dict[str, set[str]] = {
    "chat": set(),
    "dashboard": {"generate_daily_purchase_report"},
    "inventory": {
        "get_inventory",
        "get_low_stock_items",
        "update_inventory_stock",
        "remove_expired_stock",
    },
    "purchase_orders": {
        "create_purchase_order",
        "cancel_purchase_order",
        "get_po_status",
        "generate_purchase_invoice",
        "generate_daily_purchase_report",
    },
    "vendors": {"get_vendors", "add_vendor", "update_vendor"},
    "leaves": {"apply_leave", "get_leaves_today"},
    "users": set(),
}


def _normalize_feature_name(value: str) -> str:
    key = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return FEATURE_ALIASES.get(key, key)


def normalize_feature_list(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []

    allowed = set(AVAILABLE_FEATURES)
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in values:
        key = _normalize_feature_name(str(raw))
        if key in allowed and key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def parse_feature_access(raw_value: object) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return normalize_feature_list(raw_value)
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return normalize_feature_list(parsed)
        except Exception:
            return normalize_feature_list(text.split(","))
    return []


def effective_feature_access(role: str | None, stored_value: object) -> list[str]:
    role_key = (role or "").strip().lower()
    if role_key in ("admin", "administrator"):
        return list(AVAILABLE_FEATURES)

    explicit = parse_feature_access(stored_value)
    if explicit:
        return explicit
    return DEFAULT_FEATURES_BY_ROLE.get(role_key, ["chat"])


def serialize_feature_access(features: Iterable[str] | None) -> str:
    return json.dumps(normalize_feature_list(features or []))


def tools_allowed_by_features(features: Iterable[str]) -> set[str]:
    allowed_tools: set[str] = set()
    for feature in normalize_feature_list(features):
        allowed_tools.update(FEATURE_TO_TOOLS.get(feature, set()))
    return allowed_tools
