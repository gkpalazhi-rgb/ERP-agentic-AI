import os
import re
from datetime import date, datetime
from difflib import SequenceMatcher

from app.models.inventory import Inventory
from app.models.leave_application import LeaveApplication
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.models.vendor import Vendor


_ITEM_QUERY_STOP_WORDS = {
    "a", "an", "and", "check", "create", "for", "get", "have", "how",
    "i", "in", "inventory", "is", "item", "items", "left", "make", "need",
    "of", "order", "please", "po", "purchase", "quantity", "reorder", "show",
    "stock", "the", "to", "want",
}


def _normalize_item_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (value or "").lower())).strip()


def _tokenize_item_text(value: str) -> list[str]:
    return [
        token for token in _normalize_item_text(value).split()
        if token and token not in _ITEM_QUERY_STOP_WORDS
    ]


def _resolve_inventory_item(item: str, db):
    normalized_query = _normalize_item_text(item)
    query_tokens = _tokenize_item_text(item)
    if not normalized_query:
        return None

    exact_item = db.query(Inventory).filter(Inventory.item_name.ilike(item.strip())).first()
    if exact_item:
        return exact_item

    inventory_items = db.query(Inventory).all()
    best_match = None
    best_score = 0.0

    for inventory_item in inventory_items:
        item_name = inventory_item.item_name or ""
        normalized_name = _normalize_item_text(item_name)
        if not normalized_name:
            continue

        if normalized_name == normalized_query:
            return inventory_item

        name_tokens = set(_tokenize_item_text(item_name))
        common_tokens = set(query_tokens) & name_tokens
        token_overlap = (len(common_tokens) / len(query_tokens)) if query_tokens else 0.0
        prefix_overlap = 0.0
        if query_tokens:
            prefix_hits = sum(
                1
                for query_token in query_tokens
                if any(
                    name_token.startswith(query_token) or query_token.startswith(name_token)
                    for name_token in name_tokens
                )
            )
            prefix_overlap = prefix_hits / len(query_tokens)

        similarity = SequenceMatcher(None, normalized_query, normalized_name).ratio()

        if normalized_query in normalized_name or normalized_name in normalized_query:
            score = 0.9 + (0.05 * token_overlap) + (0.05 * similarity)
        elif common_tokens:
            score = (0.65 * token_overlap) + (0.2 * prefix_overlap) + (0.15 * similarity)
        else:
            score = 0.35 * similarity

        if score > best_score:
            best_match = inventory_item
            best_score = score

    if best_match and best_score >= 0.72:
        return best_match

    return None


# Check inventory
def get_inventory(item: str, db, user_id: int = 1):

    # Split item phrase into words to search individually or together
    words = item.lower().split()
    
    query = db.query(Inventory)
    for word in words:
        query = query.filter(Inventory.item_name.ilike(f"%{word}%"))
        
    products = query.all()

    if not products:
        # Also try a direct substring match if word split was too strict
        products = db.query(Inventory).filter(Inventory.item_name.ilike(f"%{item.lower()}%")).all()

    if not products:
        resolved_item = _resolve_inventory_item(item, db)
        if resolved_item:
            products = [resolved_item]

    if not products:
        return {
            "item": item,
            "quantity": 0,
            "message": f"Item '{item}' not found in inventory"
        }

    # If multiple products match, we can sum them or list them. 
    if len(products) == 1:
        return {
            "item": products[0].item_name,
            "quantity": products[0].quantity
        }
    
    # Multiple matches
    result_lines = [f"{p.item_name}: {p.quantity}" for p in products]
    total_qty = sum(p.quantity for p in products)
    
    return {
        "item": item,
        "quantity": total_qty,
        "message": "Found multiple matching items:\n" + "\n".join(result_lines)
    }

# --- Dynamic PO ID helper ---
def _generate_po_id(item_code: str, db) -> str:
    """
    Generates a Purchase Order ID in the format:  YYMMDD-ITEMCODE-NNN
    NNN = zero-padded count of POs already created for this item today + 1.
    Example: 260324-AYU001-003
    """
    today = date.today()
    date_part = today.strftime("%y%m%d")          # e.g. "260324"
    item_part = item_code.upper()                  # e.g. "AYU001"

    # Count POs for the same item created today
    prefix = f"{date_part}-{item_part}-"
    existing_count = db.query(PurchaseOrder).filter(
        PurchaseOrder.po_id.like(f"{prefix}%")
    ).count()

    seq = existing_count + 1
    return f"{date_part}-{item_part}-{seq:03d}"


def _resolve_purchase_order(po_id: str | int, db):
    """
    Finds a purchase order by the new string PO ID first, then falls back
    to the legacy numeric primary key, then tries a prefix match.
    """
    po_id_str = str(po_id).strip()

    # 1. Exact match on po_id column
    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id_str).first()
    if po:
        return po

    # 2. Prefix / partial match (e.g. user says "260324" and the full ID is "260324-FG00639-001")
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.po_id.ilike(f"{po_id_str}%")
    ).first()
    if po:
        return po

    # 3. Legacy numeric primary key fallback
    try:
        numeric_id = int(po_id_str)
    except (TypeError, ValueError):
        return None

    return db.query(PurchaseOrder).filter(PurchaseOrder.id == numeric_id).first()


# Create purchase order
def create_purchase_order(item: str, quantity: int, db, vendor_name: str = "default_vendor", user_id: int = 1):
    from app.services.email_service import send_po_email

    # --- Resolve item_code from inventory ---
    inv_item = _resolve_inventory_item(item, db)
    resolved_item_name = inv_item.item_name if inv_item and inv_item.item_name else item.lower()
    item_code = inv_item.item_code if inv_item and inv_item.item_code else f"GEN-{item[:3].upper()}"

    # --- Generate dynamic PO ID ---
    po_id_str = _generate_po_id(item_code, db)

    purchase_order = PurchaseOrder(
        po_id=po_id_str,
        item_name=resolved_item_name,
        item_code=item_code,
        quantity=quantity,
        vendor=vendor_name
    )

    db.add(purchase_order)
    db.commit()
    db.refresh(purchase_order)

    # Look up vendor email and send notification
    email_result = {"email_sent": False, "reason": "Vendor not found in database"}

    # Try matching by vendor name first, then by item name as fallback
    vendor_record = db.query(Vendor).filter(
        Vendor.vendor_name.ilike(f"%{vendor_name}%")
    ).first()

    if not vendor_record and vendor_name == "default_vendor":
        # If no vendor specified, try finding one that supplies this item
        vendor_record = db.query(Vendor).filter(
            Vendor.item_category.ilike(f"%{resolved_item_name}%")
        ).first()
        if vendor_record:
            print(f"[PO EMAIL] Matched vendor '{vendor_record.vendor_name}' by item '{resolved_item_name}'")

    print(f"[PO EMAIL] Vendor lookup for '{vendor_name}' / item '{item}': "
          f"{'Found ' + vendor_record.vendor_name + ' (email: ' + str(vendor_record.email) + ')' if vendor_record else 'NOT FOUND'}")

    if vendor_record and vendor_record.email:
        email_result = send_po_email(
            vendor_name=vendor_record.vendor_name,
            vendor_email=vendor_record.email,
            po_id=po_id_str,
            item_name=resolved_item_name,
            quantity=quantity
        )
    elif vendor_record and not vendor_record.email:
        email_result = {"email_sent": False, "reason": f"No email on file for vendor '{vendor_record.vendor_name}'"}

    return {
        "status": "PO Created",
        "item": resolved_item_name,
        "item_code": item_code,
        "quantity": quantity,
        "vendor_name": vendor_name,
        "po_id": purchase_order.po_id,
        "email_notification": email_result
    }


# Add vendor
def add_vendor(vendor_name: str, vendor_code: str, item_category: str, location: str, db, email: str | None = None, user_id: int = 1):
    vendor_kwargs = {
        "vendor_code": vendor_code,
        "vendor_name": vendor_name,
        "location": location,
        "item_category": item_category,
    }
    if email is not None:
        vendor_kwargs["email"] = email

    vendor = Vendor(**vendor_kwargs)

    db.add(vendor)
    db.commit()
    db.refresh(vendor)

    return {
        "status": "Vendor Added",
        "vendor_code": vendor.vendor_code,
        "email": email
    }


# Update vendor details (especially email)
def update_vendor(vendor_name: str, db, email: str | None = None, user_id: int = 1):
    vendor = db.query(Vendor).filter(
        Vendor.vendor_name.ilike(f"%{vendor_name}%")
    ).first()

    if not vendor:
        return {"error": f"Vendor '{vendor_name}' not found."}

    updated_fields = []
    if email is not None:
        vendor.email = email
        updated_fields.append(f"email → {email}")

    if not updated_fields:
        return {"error": "No fields to update. Provide email."}

    db.commit()
    db.refresh(vendor)

    return {
        "status": "Vendor Updated",
        "vendor_name": vendor.vendor_name,
        "updated": ", ".join(updated_fields)
    }


# Get vendor list
def get_vendors(db, user_id: int = 1):

    vendors = db.query(Vendor).all()

    return [
        {
            "vendor_code": v.vendor_code,
            "vendor_name": v.vendor_name,
            "location": v.location,
            "item_category": v.item_category,
            "email": v.email
        }
        for v in vendors
    ]


# Get PO status
def get_po_status(po_id: str, db, user_id: int = 1):
    po = _resolve_purchase_order(po_id, db)
    if not po:
        return {"error": f"Purchase order with ID '{po_id}' not found."}

    # Try to find the item's MRP to calculate cost
    price = 0.0

    # Fallback: use inventory MRP
    inv_item = db.query(Inventory).filter(
        Inventory.item_name.ilike(f"%{po.item_name}%")
    ).first()
    if inv_item and inv_item.mrp:
        price = inv_item.mrp

    total_cost = price * po.quantity if price else 0.0

    return {
        "po_id": po.po_id or str(po.id),
        "status": po.status,
        "item": po.item_name,
        "item_code": po.item_code,
        "quantity": po.quantity,
        "vendor": po.vendor,
        "total_cost": total_cost,
        "price_per_unit": price
    }


# Generate Purchase Invoice
def generate_purchase_invoice(po_id: str, db, user_id: int = 1):
    po_details = get_po_status(po_id, db, user_id=user_id)
    
    if "error" in po_details:
        return {"error": po_details["error"]}
        
    invoice_text = f"""==================================================
           THAIKKATTU MOOSS VAIDYARATNAM
                PURCHASE INVOICE
==================================================
PO ID:         {po_details['po_id']}
STATUS:        {po_details['status']}
VENDOR:        {po_details['vendor'].title()}
--------------------------------------------------
ITEM:          {po_details['item'].title()}
ITEM CODE:     {po_details.get('item_code', 'N/A')}
QUANTITY:      {po_details['quantity']}
UNIT PRICE:    ₹{po_details['price_per_unit']:.2f}
--------------------------------------------------
TOTAL DUE:     ₹{po_details['total_cost']:.2f}
==================================================
Authorized by: ERP AI Agent
"""

    # Ensure the invoices directory exists
    os.makedirs("invoices", exist_ok=True)

    # Use po_id as filename (replace hyphens with underscores for safe filenames)
    safe_po_id = str(po_id).replace("-", "_")
    filename = f"invoices/po_invoice_{safe_po_id}.txt"
    with open(filename, "w", encoding='utf-8') as f:
        f.write(invoice_text)

    return {
        "invoice_generated": True,
        "filename": filename,
        "po_id": po_id
    }

# Apply for leave
def apply_leave(reason: str, leave_date: str, leave_type: str, db, user_id: int = 1):
    try:
        try:
            parsed_date = datetime.strptime(leave_date, "%Y-%m-%d").date()
        except ValueError:
            parsed_date = datetime.now().date()
        
        # Normalize leave type
        lt = leave_type.lower()
        if "1st" in lt or "first" in lt: leave_type = "1st Half"
        elif "2nd" in lt or "second" in lt: leave_type = "2nd Half"
        else: leave_type = "Full Day"
        
        # Fetch username from users table
        user = db.query(User).filter(User.id == user_id).first()
        username = user.username if user else f"User_{user_id}"

        leave_app = LeaveApplication(
            user_id=user_id, 
            username=username, 
            reason=reason, 
            leave_date=parsed_date, 
            leave_type=leave_type
        )
        db.add(leave_app)
        db.commit()
        db.refresh(leave_app)
        return {"status": "Leave Applied", "leave_id": leave_app.id, "date": str(leave_app.leave_date), "type": leave_app.leave_type}
    except Exception as e:
        return {"error": str(e)}

# Update inventory when goods arrive
def update_inventory_stock(item: str, quantity: int, db, po_id=None, user_id: int = 1):
    """
    Increments inventory quantity for an item. 
    Cross-references with purchase_orders to prevent 'fake' stock additions.
    """
    try:
        item_lower = item.lower()
        po = None
        
        # 1. CROSS-REFERENCE LOGIC
        if po_id:
            po = _resolve_purchase_order(po_id, db)
            if not po:
                return {"error": f"Security Alert: Purchase Order '{po_id}' does not exist. Stock arrival rejected."}
            if po.status == "Delivered":
                return {"error": f"Security Alert: Stock for PO '{po_id}' has already been received. Data duplication prevented."}
            # Verify item matches (allow loose matching)
            if item_lower not in po.item_name.lower() and po.item_name.lower() not in item_lower:
                return {"error": f"Data Mismatch: PO '{po_id}' is for '{po.item_name}', but you reported '{item}'. Verification failed."}
        else:
            # Optional: Try to find a matching pending PO if none specified
            po = db.query(PurchaseOrder).filter(
                PurchaseOrder.item_name.ilike(f"%{item_lower}%"),
                PurchaseOrder.status == "Pending"
            ).first()
            
            if not po:
                return {"error": f"No pending Purchase Order found for '{item}'. Please provide a PO ID to verify this stock arrival."}

        # 2. UPDATE INVENTORY
        product = db.query(Inventory).filter(Inventory.item_name.ilike(f"%{item_lower}%")).first()

        if product:
            product.quantity += quantity
            action = "updated"
        else:
            product = Inventory(item_name=item_lower, quantity=quantity, item_code=f"GEN-{item_lower[:3].upper()}", category="General")
            db.add(product)
            action = "created"
            
        # 3. MARK PO AS DELIVERED
        po.status = "Delivered"

        db.commit()
        db.refresh(product)

        return {
            "status": "Stock Updated",
            "item": product.item_name,
            "added_quantity": quantity,
            "new_total": product.quantity,
            "message": f"Verified against PO '{po.po_id or po.id}'. Inventory for {product.item_name} {action}. Total now: {product.quantity}. PO status marked as Delivered."
        }
    except Exception as e:
        return {"error": f"Verification failed: {str(e)}"}
