import uuid
from app.services.tool_registry import TOOL_REGISTRY
from app.models.erp_logs import ERPAPILog


def execute_plan(plan: dict, db, user_id: int = 1):

    if not isinstance(plan, dict) or "steps" not in plan:
        return "Invalid execution plan."

    if not isinstance(plan["steps"], list):
        return "Invalid execution steps format."

    plan_id = str(uuid.uuid4())
    last_result = None
    context = {}

    for index, step in enumerate(plan["steps"]):

        step_type = step.get("type")

        # ------------------ TOOL STEP ------------------
        if step_type == "tool":

            tool_name = step.get("name")
            args = step.get("args", {})

            if tool_name not in TOOL_REGISTRY:
                return f"Unknown tool: {tool_name}"

            tool_function = TOOL_REGISTRY[tool_name]["function"]

            try:
                # Format any variable bindings inside args like "{last.po_id}"
                formatted_args = {}
                for key, val in args.items():
                    if isinstance(val, str) and "{last." in val and "}" in val and last_result:
                        try:
                            field_name = val.replace("{last.", "").replace("}", "")
                            formatted_args[key] = last_result.get(field_name, val)
                        except:
                            formatted_args[key] = val
                    else:
                        formatted_args[key] = val

                # PASS DB AND USER_ID INTO TOOL
                if "user_id" not in formatted_args:
                    formatted_args["user_id"] = user_id

                result = tool_function(db=db, **formatted_args)

                last_result = result
                
                if tool_name == "get_inventory" and isinstance(result, dict):
                    context["initial_inventory_quantity"] = result.get("quantity")
                    context["inventory_item"] = result.get("item")
                elif tool_name == "create_purchase_order" and isinstance(result, dict):
                    context["po_created"] = True
                    context["po_quantity"] = result.get("quantity", args.get("quantity"))
                    context["po_item"] = result.get("item", args.get("item"))
                    context["po_vendor"] = result.get("vendor_name", args.get("vendor_name", "the default vendor"))

                log_entry = ERPAPILog(
                    tool_name=tool_name,
                    request_payload=str(args),
                    response_status="SUCCESS"
                )

                db.add(log_entry)
                db.commit()

            except Exception as e:

                log_entry = ERPAPILog(
                    tool_name=tool_name,
                    request_payload=str(args),
                    response_status="FAILED"
                )

                db.add(log_entry)
                db.commit()

                return f"Execution failed at step {index}: {str(e)}"

        # ------------------ CONDITION STEP ------------------
        elif step_type == "condition":

            if not last_result:
                return f"Condition at step {index} cannot be evaluated."

            left = step.get("left")
            operator = step.get("operator")
            right = step.get("right")

            if not left or not left.startswith("last."):
                return f"Invalid condition format at step {index}."

            field = left.split("last.")[1]

            if field not in last_result:
                return f"Field '{field}' not found in last result."

            left_value = last_result[field]

            if operator == "==":
                condition_result = left_value == right
            elif operator == "<":
                condition_result = left_value < right
            elif operator == ">":
                condition_result = left_value > right
            else:
                return f"Unsupported operator '{operator}' at step {index}."

            if not condition_result:
                return "Condition not met. No further action taken."

            continue

        else:
            return f"Unsupported step type at step {index}."

    # Format response for user
    if context.get("po_created") and context.get("initial_inventory_quantity") is not None:
        item_name = str(context.get('inventory_item', 'Item')).capitalize()
        vendor_text = f" from {context['po_vendor'].title()}" if context.get('po_vendor') and context['po_vendor'] != "the default vendor" else ""
        return f"{item_name} in inventory = {context['initial_inventory_quantity']}, PO created for {context['po_quantity']} {context.get('po_item')}{vendor_text}."

    if isinstance(last_result, dict):
        if "error" in last_result:
            return last_result["error"]
            
        if "invoice_generated" in last_result:
            return f"Purchase invoice successfully generated! Saved as {last_result['filename']}."

        if "total_cost" in last_result:
            cost_text = f" Total estimated cost is ₹{last_result['total_cost']:.2f}." if last_result['total_cost'] > 0 else ""
            return f"Order #{last_result['po_id']} for {last_result['quantity']} {last_result['item']} from {last_result['vendor'].title()} is actively {last_result['status']}.{cost_text}"

        if "po_id" in last_result:
            return f"Purchase order created with ID {last_result['po_id']}."

        if "vendor_id" in last_result:
            return f"Vendor added successfully with ID {last_result['vendor_id']}."

        if last_result.get("status") == "Stock Updated":
            return last_result.get("message", f"Updated inventory for {last_result.get('item')}.")

        if "leave_id" in last_result:
            return f"Leave application submitted successfully (ID: {last_result['leave_id']}) for {last_result['date']} ({last_result['type']})."

        if "quantity" in last_result and "item" in last_result:
            if last_result.get("message"):
                return last_result["message"]
            return f"Inventory for {last_result['item']} is {last_result['quantity']} units."

    if isinstance(last_result, list):
        if len(last_result) > 0 and isinstance(last_result[0], dict) and "vendor_name" in last_result[0]:
            vendor_names = [v['vendor_name'] for v in last_result]
            return f"Found {len(last_result)} vendors: {', '.join(vendor_names)}."
        return str(last_result)

    return "Plan executed successfully."