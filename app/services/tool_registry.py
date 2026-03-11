from app.services.tools import get_inventory, create_purchase_order, add_vendor, get_vendors, get_po_status, generate_purchase_invoice

TOOL_REGISTRY = {

    "get_inventory": {
        "function": get_inventory,
        "description": "Check current inventory quantity of an item",
        "args": {
            "item": "string"
        }
    },

    "create_purchase_order": {
        "function": create_purchase_order,
        "description": "Create purchase order for inventory restocking",
        "args": {
            "item": "string",
            "quantity": "integer",
            "vendor_name": "string"
        }
    },

    "add_vendor": {
        "function": add_vendor,
        "description": "Add a new vendor with item name and price",
        "args": {
            "vendor_name": "string",
            "item_name": "string",
            "price": "number"
        }
    },

    "get_vendors": {
        "function": get_vendors,
        "description": "Get a list of all vendors",
        "args": {}
    },

    "get_po_status": {
        "function": get_po_status,
        "description": "Check the status and total cost of an existing purchase order ID",
        "args": {
            "po_id": "integer"
        }
    },

    "generate_purchase_invoice": {
        "function": generate_purchase_invoice,
        "description": "Generate a .txt file purchase invoice for an existing purchase order ID",
        "args": {
            "po_id": "integer"
        }
    }
}