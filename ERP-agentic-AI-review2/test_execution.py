import uuid
from app.services.tools import get_inventory, create_purchase_order
from app.models.erp_logs import ERPAPILog

TOOLS = {
    "get_inventory": get_inventory,
    "create_purchase_order": create_purchase_order
}


def execute_plan(plan: dict, db):

    if not isinstance(plan, dict) or "steps" not in plan:
        return "Invalid execution plan."

    if not isinstance(plan["steps"], list):
        return "Invalid execution steps format."

    plan_id = str(uuid.uuid4())
    last_result = None

    for index, step in enumerate(plan["steps"]):

        step_type = step.get("type")

        # ------------------ TOOL STEP ------------------
        if step_type == "tool":

            tool_name = step.get("name")
            args = step.get("args", {})

            if tool_name not in TOOLS:
                return f"Unknown tool: {tool_name}"

            try:
                tool_function = TOOLS[tool_name]
                result = tool_function(db=db, **args)

                last_result = result

                log_entry = ERPAPILog(
                    tool_name=tool_name,
                    request_payload=str(args),
                    response_status="SUCCESS",
                    plan_id=plan_id,
                    step_index=index
                )
                db.add(log_entry)
                db.commit()

            except Exception as e:

                log_entry = ERPAPILog(
                    tool_name=tool_name,
                    request_payload=str(args),
                    response_status="FAILED",
                    plan_id=plan_id,
                    step_index=index
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

    if last_result:

        if last_result.get("po_id"):
            return f"Purchase order created with ID {last_result['po_id']}."

        if "quantity" in last_result and "item" in last_result:
            return f"Inventory for {last_result['item']} is {last_result['quantity']} units."

    return "Plan executed successfully."