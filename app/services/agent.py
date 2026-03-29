import difflib
import json
import os
import re
import time
from datetime import datetime, timedelta

import requests

from app.services.intent_classifier import build_clarification_response, classify_and_plan
from app.services.semantic_router import get_agent_router
from app.services.tool_registry import TOOL_REGISTRY

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "25"))
OLLAMA_FALLBACK_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_FALLBACK_TIMEOUT_SECONDS", "12"))


def build_tool_prompt():
    tool_text = ""

    for tool_name, tool_data in TOOL_REGISTRY.items():
        description = tool_data.get("description", "")
        args = tool_data.get("args", {})
        arg_string = ", ".join([f"{key}: {value}" for key, value in args.items()])

        tool_text += f"""
{tool_name}({arg_string})
Description: {description}
"""

    return tool_text


def extract_json(text):
    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
    except Exception as exc:
        print("JSON extraction error:", exc)

    return None


def _compact_chat_history(chat_history: str, max_chars: int = 500) -> str:
    if not chat_history.strip():
        return "None"

    matches = re.findall(r"User:\s*(.*?)\nAgent:\s*(.*?)(?=\nUser:|$)", chat_history, re.S)
    if not matches:
        return "None"

    # Keep up to last 3 turns for better multi-turn context
    recent_turns = matches[-3:]
    compact = "Previous context:\n"
    for idx, (user_msg, agent_msg) in enumerate(recent_turns):
        compact += f"Turn {idx+1}: User: {user_msg[:120]} | Agent: {agent_msg[:120]}\n"
        
    return compact.strip()[:max_chars]


def _build_planner_prompt(user_message: str, chat_history: str) -> str:
    compact_history = _compact_chat_history(chat_history)
    today = datetime.now().strftime("%Y-%m-%d (%A)")

    return (
        "You are an ERP planner. Return only one JSON object. "
        "No markdown. No explanation. Keep values short. "
        "Use {'type':'conversation','response':'...'} for casual chat. "
        "Use {'type':'action','steps':[...]} for ERP actions. "
        "Allowed tools: get_inventory(item), create_purchase_order(item, quantity, vendor_name), "
        "get_po_status(po_id), generate_purchase_invoice(po_id), get_vendors(), add_vendor(vendor_name, item_name, price, email), "
        "update_vendor(vendor_name, email, price), apply_leave(reason, leave_date, leave_type), update_inventory_stock(item, quantity, po_id). "
        "Prefer a single tool step unless inventory check must be followed by a conditional reorder. "
        "Fix minor typos in item names and IDs. "
        f"Date: {today}. Context: {compact_history}. User: {user_message}"
    )


def _get_last_turn(chat_history: str) -> tuple[str, str] | None:
    if not chat_history.strip():
        return None

    matches = re.findall(r"User:\s*(.*?)\nAgent:\s*(.*?)(?=\nUser:|$)", chat_history, re.S)
    if not matches:
        return None

    user_message, agent_message = matches[-1]
    return user_message.strip(), agent_message.strip()


def _continue_clarification(user_message: str, chat_history: str = ""):
    if not chat_history.strip():
        return None

    matches = re.findall(r"User:\s*(.*?)\nAgent:\s*(.*?)(?=\nUser:|$)", chat_history, re.S)
    if not matches:
        return None

    user_msgs = [m[0].strip() for m in matches]
    agent_msgs = [m[1].strip() for m in matches]
    
    last_agent_response = agent_msgs[-1]
    
    # Find the original user query that started this clarification loop
    original_idx = len(agent_msgs) - 1
    while original_idx > 0 and agent_msgs[original_idx - 1] == last_agent_response:
        original_idx -= 1
        
    original_user_message = user_msgs[original_idx]

    from app.services.intent_classifier import classify_and_plan, build_clarification_response
    _, previous_metadata = classify_and_plan(original_user_message)

    if previous_metadata.get("reason") != "missing_required_arguments":
        return None

    previous_intent = previous_metadata.get("intent")
    if not isinstance(previous_intent, str):
        return None

    expected_prompt = build_clarification_response(previous_intent, original_user_message)
    if not expected_prompt or last_agent_response != expected_prompt:
        return None

    # Merge all subsequent user answers into one mega-message to extract the arg
    subsequent_answers = " ".join(user_msgs[original_idx+1:])
    merged_message = f"{original_user_message} {subsequent_answers} {user_message}".strip()
    
    plan, merged_metadata = classify_and_plan(merged_message)
    if plan is None:
        if merged_metadata.get("reason") == "missing_required_arguments":
            clarification = build_clarification_response(previous_intent, merged_message)
            if clarification:
                return {
                    "type": "conversation",
                    "response": clarification,
                    "intent_detection": {
                        **merged_metadata,
                        "source": "semantic_followup_clarification",
                        "merged_from": original_user_message,
                    },
                }
        return None

    plan["intent_detection"] = {
        **merged_metadata,
        "source": "semantic_followup",
        "merged_from": original_user_message,
    }
    return plan


def _legacy_keyword_logic(user_message: str) -> dict | None:
    plan, intent_metadata = classify_and_plan(user_message)
    if plan is not None:
        return plan

    if intent_metadata.get("reason") == "missing_required_arguments":
        intent_name = intent_metadata.get("intent")
        clarification = (
            build_clarification_response(intent_name, user_message)
            if isinstance(intent_name, str)
            else None
        )
        if clarification:
            return {
                "type": "conversation",
                "response": clarification,
                "intent_detection": {
                    **intent_metadata,
                    "source": "semantic_clarification",
                },
            }

    return fallback_planner(user_message)


def fallback_planner(user_message: str, chat_history: str = ""):
    """
    Simplified rule-based backup planner if LLM fails.
    Only handles clear ERP intents. Casual conversation is left to the LLM.
    """

    user_msg = user_message.lower()

    core_keywords = [
        "invoice", "purchase", "order", "status", "cost", "vendor",
        "inventory", "stock", "bottle", "amber", "glass", "generate",
        "create", "check", "less", "than", "billing", "bill",
        "receipt", "quantity", "amount", "price", "total",
        "supplier", "restock", "reorder", "supply", "buy", "procure",
        "many", "left", "supplies", "who", "arishtam", "capsule", "dropper",
        "leave", "apply", "application", "reason", "day", "half", "full",
        "arrived", "received", "delivered", "stock", "add", "increase",
    ]

    for word in re.findall(r"\b\w+\b", user_msg):
        if len(word) >= 4:
            matches = difflib.get_close_matches(word, core_keywords, n=1, cutoff=0.8)
            if matches and matches[0] != word:
                user_msg = re.sub(r"\b" + word + r"\b", matches[0], user_msg)

    msg = f"{chat_history} {user_msg}".lower()

    words = set(re.findall(r"\b\w+\b", user_msg))

    if words.intersection({"invoice", "bill", "receipt"}) and not words.intersection({"create", "purchase"}):
        po_match = re.search(r"(?:for\s+(?:po|order)\s+)?#?(\d+)", user_msg)
        if po_match:
            return {
                "type": "action",
                "steps": [{
                    "type": "tool",
                    "name": "generate_purchase_invoice",
                    "args": {"po_id": int(po_match.group(1))},
                }],
            }

    if words.intersection({"status", "cost", "track"}) and words.intersection({"po", "order"}):
        po_match = re.search(r"(?:of\s+(?:po|order)\s+)?#?(\d+)", user_msg)
        if po_match:
            return {
                "type": "action",
                "steps": [{
                    "type": "tool",
                    "name": "get_po_status",
                    "args": {"po_id": int(po_match.group(1))},
                }],
            }

    if "if" in user_msg and ("less than" in user_msg or "<" in user_msg) and ("purchase" in user_msg or "order" in user_msg or "po" in user_msg):
        try:
            cond_match = re.search(r"(?:less than|<)\s*(\d+)", user_msg)
            threshold = int(cond_match.group(1)) if cond_match else 10

            po_qty_match = re.search(r"(?:purchase|order|po).*?(\d+)", msg)
            po_qty = int(po_qty_match.group(1)) if po_qty_match else 50

            vendor_match = re.search(r"from vendor\s+([a-zA-Z0-9_]+)", msg)
            vendor = f"vendor {vendor_match.group(1)}" if vendor_match else "default_vendor"

            item = extract_item_from_message(user_msg, msg, before_keyword="if")

            return {
                "type": "action",
                "steps": [
                    {"type": "tool", "name": "get_inventory", "args": {"item": item}},
                    {"type": "condition", "left": "last.quantity", "operator": "<", "right": threshold},
                    {"type": "tool", "name": "create_purchase_order", "args": {"item": item, "quantity": po_qty, "vendor_name": vendor}},
                ],
            }
        except Exception:
            pass

    if "vendor" in user_msg or "supplies" in user_msg or "who" in user_msg or "supplier" in user_msg:
        return {
            "type": "action",
            "steps": [{"type": "tool", "name": "get_vendors", "args": {}}],
        }

    if words.intersection({"purchase", "order", "po", "buy", "procure"}):
        qty_match = re.search(r"\d+", user_msg)
        quantity = int(qty_match.group()) if qty_match else 1
        item = extract_item_from_message(user_msg, msg)

        steps = [{"type": "tool", "name": "create_purchase_order", "args": {"item": item, "quantity": quantity}}]
        if "invoice" in user_msg or "bill" in user_msg:
            steps.append({"type": "tool", "name": "generate_purchase_invoice", "args": {"po_id": "{last.po_id}"}})

        return {"type": "action", "steps": steps}

    if "leave" in user_msg or "apply" in user_msg:
        reason = "No reason provided"
        if "reason" in user_msg:
            reason_match = re.search(r"reason\s+(?:is|for)?\s*(.*?)(?:\s+on|\s+at|$)", user_msg)
            if reason_match:
                reason = reason_match.group(1).strip()

        leave_type = "Full Day"
        if "half" in user_msg:
            if "1st" in user_msg or "first" in user_msg:
                leave_type = "1st Half"
            elif "2nd" in user_msg or "second" in user_msg:
                leave_type = "2nd Half"
            else:
                leave_type = "1st Half"

        date_str = datetime.now().strftime("%Y-%m-%d")
        explicit_date = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", user_msg)
        if explicit_date:
            date_str = explicit_date.group(1)
        elif "tomorrow" in user_msg:
            date_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        return {
            "type": "action",
            "steps": [{
                "type": "tool",
                "name": "apply_leave",
                "args": {"reason": reason, "leave_date": date_str, "leave_type": leave_type},
            }],
        }

    if "arrived" in user_msg or "received" in user_msg or "delivered" in user_msg:
        # Extract PO ID — support YYMMDD-CODE-NNN format + legacy numeric
        po_id = None
        po_fmt_match = re.search(r"(\d{6}-[A-Z0-9]+-\d{3})", user_msg, re.I)
        if po_fmt_match:
            po_id = po_fmt_match.group(1).upper()
        else:
            po_legacy_match = re.search(r"(?:po|order)\s+#?(\d+)", user_msg)
            if po_legacy_match:
                po_id = po_legacy_match.group(1)

        # Extract quantity — skip digits inside PO IDs
        scrubbed_msg = re.sub(r"\b\d{6}-[A-Z0-9]+-\d{3}\b", " ", user_msg, flags=re.I)
        scrubbed_msg = re.sub(r"(?:po|order)\s*#?\s*\d+", " ", scrubbed_msg, flags=re.I)
        qty_match = re.search(r"\d+", scrubbed_msg)
        quantity = int(qty_match.group()) if qty_match else 0

        item = extract_item_from_message(user_msg, msg)

        if quantity > 0 or po_id:
            return {
                "type": "action",
                "steps": [{
                    "type": "tool",
                    "name": "update_inventory_stock",
                    "args": {"item": item, "quantity": quantity, "po_id": po_id},
                }],
            }

    if "inventory" in user_msg or "stock" in user_msg or "check" in user_msg or "have" in user_msg or "many" in user_msg or "left" in user_msg or "count" in user_msg:
        item = extract_item_from_message(user_msg, msg)
        return {
            "type": "action",
            "steps": [{"type": "tool", "name": "get_inventory", "args": {"item": item}}],
        }

    return None


def extract_item_from_message(user_msg: str, full_msg: str, before_keyword: str | None = None) -> str:
    if before_keyword:
        item_match = re.search(rf"(?:for|of)\s+([a-zA-Z0-9\s]+?)\s+{before_keyword}", full_msg)
        if item_match:
            return item_match.group(1).strip()

    # Match "11 neem tab arrived" / "50 bottles received" — <quantity> <item> <arrival verb>
    arrival_match = re.search(r"\b\d+\s+([a-z][a-z0-9\s]+?)\s+(?:arrived|received|delivered|has\s+arrived|have\s+arrived)", user_msg, re.I)
    if arrival_match:
        item = arrival_match.group(1).strip()
        # Clean out PO-related fragments
        item = re.sub(r"\b(?:for|from|vendor|po|order|id)[\s\w]*$", "", item, flags=re.I).strip()
        if item and item.lower() not in ["them", "it", "the", "some", "more"]:
            return item

    # Match "buy 15 neem tabs" or "order 50 amber bottles"
    direct_match = re.search(r"\b(?:buy|order|get|procure|purchase)\s+(?:\d+)?\s*([a-z0-9\s]+)", user_msg)
    if direct_match:
        item = direct_match.group(1).strip()
        item = re.sub(r"\b(?:from|vendor)[\s\w]+$", "", item).strip()
        if item and item not in ["them", "it", "the", "some", "more"]:
            return item

    item_match = re.search(r"(?:for|of)\s+(?:an?\s+)?(?:\d+\s+)?([a-z0-9\s]+)", user_msg)
    if item_match:
        item = item_match.group(1).strip()
        item = re.sub(r"\s+(?:create|make|generate|produce|and|it).*$", "", item).strip()
        if item and item not in ["them", "it", "the"]:
            return item

    # Match "how many aloe vera gel" / "do we have amber bottles" / "count brahmi"
    qty_check_match = re.search(r"\b(?:how many|do we have|do you have|are there any|count)\s+([a-zA-Z0-9\s-]+?)(?:\s+(?:left|remaining|in stock|available))?$", user_msg, re.I)
    if qty_check_match:
        item = qty_check_match.group(1).strip()
        item = re.sub(r"\b(?:inventory|stock)\b.*", "", item, flags=re.I).strip()
        if item and item.lower() not in ["them", "it", "the", "some", "more"]:
            return item

    item_match = re.search(r"(?:for|of)\s+(?:an?\s+)?(?:\d+\s+)?([a-z0-9\s]+)", full_msg)
    if item_match:
        item = item_match.group(1).strip()
        item = re.sub(r"\\n.*", "", item).strip()
        item = item.replace("agent", "").strip()
        if item and item not in ["them", "it", "the"]:
            return item

    return "item"


def _attach_intent_metadata(plan, intent_metadata, source: str, elapsed_ms: float):
    if plan is None:
        return None

    plan["intent_detection"] = {
        **plan.get("intent_detection", intent_metadata),
        "source": source,
        "latency_ms": round(elapsed_ms, 2),
    }
    return plan


def generate_plan(user_message: str, chat_history: str = ""):
    continued_plan = _continue_clarification(user_message, chat_history)
    if continued_plan is not None:
        print("[Semantic] Completed prior clarification - skipping LLM.")
        return continued_plan

    router = get_agent_router(_legacy_keyword_logic, lambda text: text)
    router_plan = router.route_plan(user_message)
    if router_plan is not None:
        print("[Semantic Router] Resolved before LLM.")
        return router_plan

    elapsed_ms = 0.0
    intent_metadata = {"reason": "unknown_intent"}

    print("[Semantic] No confident match - falling back to LLM.")

    system_prompt = _build_planner_prompt(user_message, chat_history)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": system_prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 120,
            "num_ctx": 1024,
        },
    }

    for attempt in range(2):
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
            data = response.json()
            result_text = data.get("response", "")

            print(f"\nLLM OUTPUT (attempt {attempt + 1}):\n", result_text)

            plan = extract_json(result_text)
            if plan:
                if "steps" in plan and "type" not in plan:
                    plan["type"] = "action"
                return _attach_intent_metadata(plan, intent_metadata, "llm", elapsed_ms)

            if attempt == 0:
                print("LLM returned invalid JSON. Retrying with shorter prompt...")
                payload["prompt"] = (
                    "Return only valid JSON. "
                    "Use conversation for chat, action+steps for ERP. "
                    f"User: {user_message}"
                )
                payload["options"]["num_ctx"] = 768
                continue

        except requests.exceptions.ConnectionError:
            print("Ollama is not reachable.")
            break
        except requests.exceptions.Timeout:
            print("Ollama request timed out. Trying lightweight conversation prompt...")
            try:
                short_payload = {
                    "model": OLLAMA_MODEL,
                    "prompt": (
                        "Return one JSON object only. "
                        f"User: {user_message}"
                    ),
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0,
                        "num_predict": 80,
                        "num_ctx": 512,
                    },
                }
                resp2 = requests.post(OLLAMA_URL, json=short_payload, timeout=OLLAMA_FALLBACK_TIMEOUT_SECONDS)
                data2 = resp2.json()
                result2 = data2.get("response", "")
                print("Short prompt LLM OUTPUT:", result2)
                plan2 = extract_json(result2)
                if plan2:
                    return _attach_intent_metadata(plan2, intent_metadata, "llm", elapsed_ms)
            except Exception:
                pass
            break
        except Exception as exc:
            print("Planner error:", str(exc))
            break

    print("Using fallback planner.")
    fallback_result = fallback_planner(user_message, chat_history)
    if fallback_result:
        return _attach_intent_metadata(fallback_result, intent_metadata, "fallback", elapsed_ms)

    return {
        "type": "conversation",
        "response": "I can help with inventory, purchase orders, vendors, PO status, and invoices. What do you need?",
        "intent_detection": {
            **intent_metadata,
            "source": "default",
            "latency_ms": round(elapsed_ms, 2),
        },
    }
