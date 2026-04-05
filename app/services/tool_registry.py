from app.services.tools import get_inventory, create_purchase_order, add_vendor, update_vendor, get_vendors, get_po_status, generate_purchase_invoice, apply_leave, update_inventory_stock, get_leaves_today, generate_daily_purchase_report, remove_expired_stock, get_low_stock_items, cancel_purchase_order

TOOL_REGISTRY = {

    "get_inventory": {
        "function": get_inventory,
        "description": "Check current inventory quantity of an item",
        "args": {
            "item": "string"
        }
    },

    "get_low_stock_items": {
        "function": get_low_stock_items,
        "description": "List items whose stock is below a threshold.",
        "args": {
            "threshold": "integer (optional, default 50)"
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

    "cancel_purchase_order": {
        "function": cancel_purchase_order,
        "description": "Cancel an existing purchase order by PO ID and notify the vendor via email.",
        "args": {
            "po_id": "string or integer",
            "cancellation_reason": "string (optional)"
        }
    },

    "add_vendor": {
        "function": add_vendor,
        "description": "Add a new vendor. Vendor code can be auto-generated; item category and location default if missing.",
        "args": {
            "vendor_name": "string",
            "vendor_code": "string (optional)",
            "item_category": "string (optional)",
            "location": "string (optional)",
            "email": "string (optional)"
        }
    },

    "update_vendor": {
        "function": update_vendor,
        "description": "Update a vendor's email (price input is accepted but ignored by current schema).",
        "args": {
            "vendor_name": "string",
            "email": "string (optional)",
            "price": "number (optional, ignored)"
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
            "po_id": "string or integer"
        }
    },

    "generate_purchase_invoice": {
        "function": generate_purchase_invoice,
        "description": "Generate a .txt file purchase invoice for an existing purchase order ID",
        "args": {
            "po_id": "string or integer"
        }
    },

    "apply_leave": {
        "function": apply_leave,
        "description": "Apply for leave with a reason, date, and type (Full Day, 1st Half, or 2nd Half)",
        "args": {
            "reason": "string",
            "leave_date": "string (YYYY-MM-DD)",
            "leave_type": "string",
            "user_id": "integer (optional)"
        }
    },

    "update_inventory_stock": {
        "function": update_inventory_stock,
        "description": "Increase inventory quantity for a product (e.g., when a PO arrives or stock is received)",
        "args": {
            "item": "string",
            "quantity": "integer",
            "po_id": "string or integer (optional)"
        }
    },
    
    "get_leaves_today": {
        "function": get_leaves_today,
        "description": "Get a list of all employees who are on leave today",
        "args": {}
    },
    
    "generate_daily_purchase_report": {
        "function": generate_daily_purchase_report,
        "description": "Generates a comprehensive report of all purchase orders placed today, calculating total amounts and cross-referencing inventory.",
        "requires_auth": True,
    },
    "remove_expired_stock": {
        "function": remove_expired_stock,
        "description": "Reduces inventory quantity for items that are expired, damaged, or discarded.",
        "requires_auth": True,
    },
}
