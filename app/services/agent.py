import requests
import json
import re
import difflib
from app.services.tool_registry import TOOL_REGISTRY

OLLAMA_URL = "http://localhost:11434/api/generate"


def build_tool_prompt():

    tool_text = ""

    for tool_name, tool_data in TOOL_REGISTRY.items():

        description = tool_data.get("description", "")
        args = tool_data.get("args", {})

        arg_string = ", ".join([f"{k}: {v}" for k, v in args.items()])

        tool_text += f"""
{tool_name}({arg_string})
Description: {description}
"""

    return tool_text


def extract_json(text):

    try:
        return json.loads(text)
    except:
        pass

    try:
        match = re.search(r"\{[\s\S]*\}", text)

        if match:
            return json.loads(match.group())

    except Exception as e:
        print("JSON extraction error:", e)

    return None


def fallback_planner(user_message: str, chat_history: str = ""):
    """
    Simplified rule-based backup planner if LLM fails.
    Only handles clear ERP intents. Casual conversation is left to the LLM.
    """

    user_msg = user_message.lower()

    # Fuzzy-correct typos against known ERP terms
    core_keywords = [
        "invoice", "purchase", "order", "status", "cost", "vendor",
        "inventory", "stock", "bottle", "amber", "glass", "generate",
        "create", "check", "less", "than", "billing", "bill",
        "receipt", "quantity", "amount", "price", "total",
        "supplier", "restock", "reorder", "supply", "buy", "procure",
        "many", "left", "supplies", "who", "arishtam", "capsule", "dropper",
        "leave", "apply", "application", "reason", "day", "half", "full",
        "arrived", "received", "delivered", "stock", "add", "increase"
    ]

    for word in re.findall(r'\b\w+\b', user_msg):
        if len(word) >= 4:
            matches = difflib.get_close_matches(word, core_keywords, n=1, cutoff=0.8)
            if matches and matches[0] != word:
                user_msg = re.sub(r'\b' + word + r'\b', matches[0], user_msg)

    msg = f"{chat_history} {user_msg}".lower()

    # --- Invoice generation ---
    if ("invoice" in user_msg or "bill" in user_msg or "receipt" in user_msg) and "create" not in user_msg and "purchase" not in user_msg:
        po_match = re.search(r'(?:for\s+(?:po|order)\s+)?#?(\d+)', user_msg)
        if po_match:
            return {
                "type": "action",
                "steps": [{
                    "type": "tool",
                    "name": "generate_purchase_invoice",
                    "args": {"po_id": int(po_match.group(1))}
                }]
            }

    # --- PO status ---
    if ("status" in user_msg or "cost" in user_msg or "track" in user_msg) and ("po" in user_msg or "order" in user_msg):
        po_match = re.search(r'(?:of\s+(?:po|order)\s+)?#?(\d+)', user_msg)
        if po_match:
            return {
                "type": "action",
                "steps": [{
                    "type": "tool",
                    "name": "get_po_status",
                    "args": {"po_id": int(po_match.group(1))}
                }]
            }

    # --- Conditional PO (if less than X, create order) ---
    if "if" in user_msg and ("less than" in user_msg or "<" in user_msg) and ("purchase" in user_msg or "order" in user_msg or "po" in user_msg):
        try:
            cond_match = re.search(r'(?:less than|<)\s*(\d+)', user_msg)
            threshold = int(cond_match.group(1)) if cond_match else 10

            po_qty_match = re.search(r'(?:purchase|order|po).*?(\d+)', msg)
            po_qty = int(po_qty_match.group(1)) if po_qty_match else 50

            v_match = re.search(r'from vendor\s+([a-zA-Z0-9_]+)', msg)
            vendor = f"vendor {v_match.group(1)}" if v_match else "default_vendor"

            item = extract_item_from_message(user_msg, msg, before_keyword="if")

            return {
                "type": "action",
                "steps": [
                    {"type": "tool", "name": "get_inventory", "args": {"item": item}},
                    {"type": "condition", "left": "last.quantity", "operator": "<", "right": threshold},
                    {"type": "tool", "name": "create_purchase_order", "args": {"item": item, "quantity": po_qty, "vendor_name": vendor}}
                ]
            }
        except Exception:
            pass

    # --- Vendors ---
    if "vendor" in user_msg or "supplies" in user_msg or "who" in user_msg or "supplier" in user_msg:
        return {
            "type": "action",
            "steps": [{"type": "tool", "name": "get_vendors", "args": {}}]
        }

    # --- Purchase order creation ---
    if "purchase" in user_msg or "order" in user_msg or "po" in user_msg or "buy" in user_msg or "procure" in user_msg:
        qty_match = re.search(r"\d+", user_msg)
        quantity = int(qty_match.group()) if qty_match else 1
        item = extract_item_from_message(user_msg, msg)

        steps = [{"type": "tool", "name": "create_purchase_order", "args": {"item": item, "quantity": quantity}}]

        if "invoice" in user_msg or "bill" in user_msg:
            steps.append({"type": "tool", "name": "generate_purchase_invoice", "args": {"po_id": "{last.po_id}"}})

        return {"type": "action", "steps": steps}

    # --- Leave Applications ---
    if "leave" in user_msg or "apply" in user_msg:
        # Simple extraction for fallback
        reason = "No reason provided"
        if "reason" in user_msg:
            r_match = re.search(r'reason\s+(?:is|for)?\s*(.*?)(?:\s+on|\s+at|$)', user_msg)
            if r_match: reason = r_match.group(1).strip()
        
        leave_type = "Full Day"
        if "half" in user_msg:
            if "1st" in user_msg or "first" in user_msg: leave_type = "1st Half"
            elif "2nd" in user_msg or "second" in user_msg: leave_type = "2nd Half"
            else: leave_type = "1st Half" # Default half
            
        date_str = datetime.now().strftime("%Y-%m-%d") # Default to today
        if "tomorrow" in user_msg:
            from datetime import timedelta
            date_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        return {
            "type": "action",
            "steps": [{
                "type": "tool",
                "name": "apply_leave",
                "args": {"reason": reason, "leave_date": date_str, "leave_type": leave_type}
            }]
        }

    # --- Stock Arrival / Received ---
    if "arrived" in user_msg or "received" in user_msg or "delivered" in user_msg:
        qty_match = re.search(r"\d+", user_msg)
        quantity = int(qty_match.group()) if qty_match else 0
        item = extract_item_from_message(user_msg, msg)
        po_match = re.search(r'(?:po|order)\s+#?(\d+)', user_msg)
        po_id = int(po_match.group(1)) if po_match else None
        
        if quantity > 0:
            return {
                "type": "action",
                "steps": [{
                    "type": "tool",
                    "name": "update_inventory_stock",
                    "args": {"item": item, "quantity": quantity, "po_id": po_id}
                }]
            }

    # --- Inventory check ---
    if "inventory" in user_msg or "stock" in user_msg or "check" in user_msg or "have" in user_msg or "many" in user_msg or "left" in user_msg:
        item = extract_item_from_message(user_msg, msg)
        return {
            "type": "action",
            "steps": [{"type": "tool", "name": "get_inventory", "args": {"item": item}}]
        }

    # No ERP intent detected — return None so the caller knows to use a generic LLM response
    return None


def extract_item_from_message(user_msg: str, full_msg: str, before_keyword: str = None) -> str:
    """
    Helper to extract item names from user messages.
    """
    if before_keyword:
        item_match = re.search(rf'(?:for|of)\s+([a-zA-Z0-9\s]+?)\s+{before_keyword}', full_msg)
        if item_match:
            return item_match.group(1).strip()

    item_match = re.search(r'(?:for|of)\s+(?:an?\s+)?(?:\d+\s+)?([a-z0-9\s]+)', user_msg)
    if item_match:
        item = item_match.group(1).strip()
        item = re.sub(r'\s+(?:create|make|generate|produce|and|it).*$', '', item).strip()
        if item and item not in ["them", "it", "the"]:
            return item

    # Try from full message (includes chat history)
    item_match = re.search(r'(?:for|of)\s+(?:an?\s+)?(?:\d+\s+)?([a-z0-9\s]+)', full_msg)
    if item_match:
        item = item_match.group(1).strip()
        item = re.sub(r'\\n.*', '', item).strip()
        item = item.replace('agent', '').strip()
        if item and item not in ["them", "it", "the"]:
            return item

    return "item"


def generate_plan(user_message: str, chat_history: str = ""):

    tools_description = build_tool_prompt()
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d (%A)")

    system_prompt = f"""You are an ERP AI assistant for Thaikkattu Mooss Vaidyaratnam (Ayurvedic company). You handle conversation and ERP tasks.

RESPONSE STYLE: Be brief and direct. No filler phrases. Stick to key information only. Do NOT say things like "Hello! I'm happy to help" or "According to our records" or "Let me check". Just give the answer.

ALWAYS return ONLY valid JSON in one of these two formats:

For greetings/chat/questions: {{"type": "conversation", "response": "your short reply"}}
For ERP tasks: {{"type": "action", "steps": [{{"type": "tool", "name": "TOOL", "args": {{}}}}]}}

Tools: {tools_description}

Conditions can chain steps: {{"type": "condition", "left": "last.quantity", "operator": "<", "right": 10}}

Examples:
User: "hey how are you" -> {{"type": "conversation", "response": "Hi! How can I help?"}}
User: "what can you do" -> {{"type": "conversation", "response": "I can check inventory, create purchase orders, view vendors, check PO status, and generate invoices."}}
User: "check inventory for amber bottle" -> {{"type": "action", "steps": [{{"type": "tool", "name": "get_inventory", "args": {{"item": "amber bottle"}}}}]}}
User: "create PO for 50 bottles" -> {{"type": "action", "steps": [{{"type": "tool", "name": "create_purchase_order", "args": {{"item": "bottles", "quantity": 50}}}}]}}
User: "generate invoice for PO 3" -> {{"type": "action", "steps": [{{"type": "tool", "name": "generate_purchase_invoice", "args": {{"po_id": 3}}}}]}}
User: "I want to apply for leave tomorrow because I'm sick. Full day." -> {{"type": "action", "steps": [{{"type": "tool", "name": "apply_leave", "args": {{"reason": "sick", "leave_date": "2026-03-13", "leave_type": "Full Day"}}}}]}}
User: "PO of 20 arishtam has arrived" -> {{"type": "action", "steps": [{{"type": "tool", "name": "update_inventory_stock", "args": {{"item": "arishtam", "quantity": 20}}}}]}}
User: "received 50 amber bottles for PO 5" -> {{"type": "action", "steps": [{{"type": "tool", "name": "update_inventory_stock", "args": {{"item": "amber bottles", "quantity": 50, "po_id": 5}}}}]}}

Chat history: {chat_history if chat_history else "None"}
Current Date: {today}
Handle typos. Return ONLY JSON. Keep responses SHORT."""

    payload = {
        "model": "llama3",
        "prompt": system_prompt + "\nUser: " + user_message + "\nJSON:",
        "stream": False
    }

    # Try LLM up to 2 times
    for attempt in range(2):
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)
            data = response.json()

            result_text = data.get("response", "")

            print(f"\nLLM OUTPUT (attempt {attempt + 1}):\n", result_text)

            plan = extract_json(result_text)

            if plan:
                # Normalize: if old format {"steps": [...]}, convert to new format
                if "steps" in plan and "type" not in plan:
                    plan["type"] = "action"
                return plan

            # If first attempt failed, retry with a much shorter prompt
            if attempt == 0:
                print("LLM returned invalid JSON. Retrying with shorter prompt...")
                payload["prompt"] = (
                    "Return ONLY a JSON object. No markdown, no explanation. Keep responses SHORT and direct.\n"
                    f"User said: \"{user_message}\"\n"
                    "If greeting/casual talk: {\"type\": \"conversation\", \"response\": \"short direct reply\"}\n"
                    "If ERP task (inventory/order/vendor/invoice): {\"type\": \"action\", \"steps\": [{\"type\": \"tool\", \"name\": \"tool_name\", \"args\": {}}]}\n"
                    "JSON:"
                )
                continue

        except requests.exceptions.ConnectionError:
            print("Ollama is not reachable.")
            break
        except requests.exceptions.Timeout:
            print("Ollama request timed out. Trying lightweight conversation prompt...")
            # On timeout, try once more with ultra-short prompt for conversation
            try:
                short_payload = {
                    "model": "llama3",
                    "prompt": (
                        f"User says: \"{user_message}\"\n"
                        "Reply briefly as an ERP assistant in JSON format:\n"
                        "{\"type\": \"conversation\", \"response\": \"your reply\"}\n"
                        "JSON:"
                    ),
                    "stream": False
                }
                resp2 = requests.post(OLLAMA_URL, json=short_payload, timeout=90)
                data2 = resp2.json()
                result2 = data2.get("response", "")
                print("Short prompt LLM OUTPUT:", result2)
                plan2 = extract_json(result2)
                if plan2:
                    return plan2
            except:
                pass
            break
        except Exception as e:
            print("Planner error:", str(e))
            break

    # LLM failed — try keyword fallback
    print("Using fallback planner.")
    fallback_result = fallback_planner(user_message, chat_history)

    if fallback_result:
        return fallback_result

    # If even fallback doesn't match (likely casual chat) — return a generic friendly response
    return {
        "type": "conversation",
        "response": "I can help with inventory, purchase orders, vendors, PO status, and invoices. What do you need?"
    }