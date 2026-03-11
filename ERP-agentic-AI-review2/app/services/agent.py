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
    Rule based backup planner if LLM fails
    """

    user_msg = user_message.lower()

    # Dynamically fix typos using Python's built-in difflib fuzzy matching
    core_keywords = [
        "invoice", "purchase", "order", "status", "cost", "vendor", 
        "inventory", "stock", "bottle", "amber", "glass", "generate", 
        "create", "check", "less", "than", "billing", "bill", 
        "receipt", "quantity", "amount", "price", "total", 
        "supplier", "restock", "reorder", "supply", "buy", "procure"
    ]
    
    # Extract all words and fuzzy match longer ones to securely avoid breaking small terms like 'po' or 'if'
    for word in re.findall(r'\b\w+\b', user_msg):
        if len(word) >= 4:
            matches = difflib.get_close_matches(word, core_keywords, n=1, cutoff=0.8)
            if matches and matches[0] != word:
                # Replace the exact word bounds so we don't accidentally replace subsets
                user_msg = re.sub(r'\b' + word + r'\b', matches[0], user_msg)

    # Fuse previous chat history context securely into the regex engine to handle pronouns natively
    msg = f"{chat_history} {user_msg}".lower()

    if ("invoice" in user_msg) and "create" not in user_msg and "purchase" not in user_msg:
        try:
            po_match = re.search(r'(?:for\s+(?:po|order)\s+)?#?(\d+)', user_msg)
            if po_match:
                return {
                    "steps": [
                        {
                            "type": "tool",
                            "name": "generate_purchase_invoice",
                            "args": {"po_id": int(po_match.group(1))}
                        }
                    ]
                }
        except:
            pass
            
    if ("status" in user_msg or "cost" in user_msg) and ("po" in user_msg or "order" in user_msg):
        try:
            po_match = re.search(r'(?:of\s+(?:po|order)\s+)?#?(\d+)', user_msg)
            if po_match:
                return {
                    "steps": [
                        {
                            "type": "tool",
                            "name": "get_po_status",
                            "args": {"po_id": int(po_match.group(1))}
                        }
                    ]
                }
        except:
            pass

    if "if" in user_msg and ("less than" in user_msg or "<" in user_msg) and ("purchase" in user_msg or "order" in user_msg or "po" in user_msg):
        try:
            # Extract condition threshold e.g. "less than 10"
            cond_match = re.search(r'(?:less than|<)\s*(\d+)', user_msg)
            threshold = int(cond_match.group(1)) if cond_match else 10
            
            # Extract PO details
            po_qty_match = re.search(r'(?:purchase|order|po).*?(\d+)', msg)
            po_qty = int(po_qty_match.group(1)) if po_qty_match else 50
            
            # Extract vendor if applicable
            v_match = re.search(r'from vendor\s+([a-zA-Z0-9_]+)', msg)
            vendor = f"vendor {v_match.group(1)}" if v_match else "default_vendor"
            
            # Extract item by looking between 'for' and 'if'
            item_match = re.search(r'(?:for|of)\s+([a-zA-Z0-9\s]+?)\s+if', msg)
            if item_match:
                item = item_match.group(1).strip()
            else:
                item_match = re.search(r'if (.*?)\s+(?:is |are |quantity |stock )?(?:less than|<)', msg)
                item = item_match.group(1).strip() if item_match else "glass bottle"
            
            return {
                "steps": [
                    {
                        "type": "tool",
                        "name": "get_inventory",
                        "args": {"item": item}
                    },
                    {
                        "type": "condition",
                        "left": "last.quantity",
                        "operator": "<",
                        "right": threshold
                    },
                    {
                        "type": "tool",
                        "name": "create_purchase_order",
                        "args": {
                            "item": item,
                            "quantity": po_qty,
                            "vendor_name": vendor
                        }
                    }
                ]
            }
        except Exception:
            pass

    if "purchase" in user_msg or "order" in user_msg or "po" in user_msg:

        qty_match = re.search(r"\d+", user_msg)
        quantity = int(qty_match.group()) if qty_match else 1

        item = "item"
        item_match = re.search(r'(?:for|of)\s+([a-zA-Z0-9\s]+?)(?:\s+and)', user_msg)
        if item_match and item_match.group(1).strip() not in ["them", "it"]:
            item = item_match.group(1).strip()
            # Clean up trailing words like 'produce' or 'generate'
            item = re.sub(r'\s+(?:create|make|generate|produce|it).*$', '', item).strip()
        elif re.search(r'(?:for|of)\s+(?:an?\s+)?(?:[0-9]+\s+)?([a-z0-9\s]+)', user_msg) and re.search(r'(?:for|of)\s+(?:an?\s+)?(?:[0-9]+\s+)?([a-z0-9\s]+)', user_msg).group(1).strip() not in ["them", "it"]:
            item_match = re.search(r'(?:for|of)\s+(?:an?\s+)?(?:[0-9]+\s+)?([a-z0-9\s]+)', user_msg)
            item = item_match.group(1).strip()
        elif re.search(r'(?:for|of)\s+(?:an?\s+)?(?:[0-9]+\s+)?([a-z0-9\s]+)', msg):
            item_match = re.search(r'(?:for|of)\s+(?:an?\s+)?(?:[0-9]+\s+)?([a-z0-9\s]+)', msg)
            item = item_match.group(1).strip()
            item = re.sub(r'\\n.*', '', item).strip()
            item = item.replace('agent', '').strip()
        else:
            for keyword in ["laptop", "mouse", "keyboard", "arishtam", "kashayam", "choornam", "bottle"]:
                if keyword in msg:
                    item = keyword
                    break

        steps = [
            {
                "type": "tool",
                "name": "create_purchase_order",
                "args": {
                    "item": item,
                    "quantity": quantity
                }
            }
        ]

        if "invoice" in user_msg:
            steps.append({
                "type": "tool",
                "name": "generate_purchase_invoice",
                "args": {"po_id": "{last.po_id}"}
            })

        return {
            "steps": steps
        }


    if "inventory" in user_msg or "stock" in user_msg or "check" in user_msg:

        item = "item"
        item_match = re.search(r'(?:for|of)\s+(?:an?\s+)?(?:[0-9]+\s+)?([a-z0-9\s]+)', user_msg)
        if item_match:
            item = item_match.group(1).strip()
        else:
            for keyword in ["laptop", "mouse", "keyboard", "arishtam", "kashayam", "choornam", "bottle"]:
                if keyword in msg:
                    item = keyword
                    break

        return {
            "steps": [
                {
                    "type": "tool",
                    "name": "get_inventory",
                    "args": {
                        "item": item
                    }
                }
            ]
        }

    return None


def generate_plan(user_message: str, chat_history: str = ""):

    tools_description = build_tool_prompt()

    system_prompt = f"""
You are the primary ERP AI agent for Thaikkattu Mooss Vaidyaratnam, a prestigious Ayurvedic company.
You are assisting the company's internal employees with their daily tasks. Be helpful and precise.
CRITICAL: End users may make spelling mistakes or typos (e.g. "invice", "purchse", "chek"). You must intelligently infer their intent, correct the spelling, and supply the correct tool execution anyways.

Available tools:

{tools_description}

Here is the recent conversation history for memory context:
{chat_history}

You can also use condition logic to execute steps conditionally. A condition checks the result of the LAST executed tool step.
Condition support operators: '==', '<', '>'

Format:
{{
 "steps":[
   {{
     "type":"tool",
     "name":"get_inventory",
     "args":{{"item": "bottle"}}
   }},
   {{
     "type":"condition",
     "left":"last.quantity",
     "operator":"<",
     "right":10
   }},
   {{
     "type":"tool",
     "name":"create_purchase_order",
     "args":{{"item": "bottle", "quantity": 50, "vendor_name": "vendor A"}}
   }}
 ]
}}

Return ONLY JSON strings, nothing else. Never talk outside of JSON.
"""

    payload = {
        "model": "llama3",
        "prompt": system_prompt + "\nUser: " + user_message,
        "stream": False
    }

    try:

        response = requests.post(OLLAMA_URL, json=payload)
        data = response.json()

        result_text = data.get("response", "")

        print("\nLLM OUTPUT:\n", result_text)

        plan = extract_json(result_text)

        if plan:
            return plan

        print("LLM failed. Using fallback planner.")

        return fallback_planner(user_message, chat_history)

    except Exception as e:

        print("Planner error:", str(e))

        return fallback_planner(user_message, chat_history)