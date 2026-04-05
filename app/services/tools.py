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

        if re.search(rf"\b{re.escape(normalized_query)}\b", normalized_name, re.I) or re.search(rf"\b{re.escape(normalized_name)}\b", normalized_query, re.I):
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

    resolved_item = _resolve_inventory_item(item, db)
    if resolved_item:
        products = [resolved_item]
    else:
        products = db.query(Inventory).filter(Inventory.item_name.ilike(f"%{item.lower()}%")).all()

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


def get_low_stock_items(db, threshold: int = 50, user_id: int = 1):
    try:
        threshold_value = int(threshold)
    except (TypeError, ValueError):
        threshold_value = 50

    if threshold_value <= 0:
        threshold_value = 50

    low_stock = (
        db.query(Inventory)
        .filter(Inventory.quantity < threshold_value)
        .order_by(Inventory.quantity.asc(), Inventory.item_name.asc())
        .all()
    )

    if not low_stock:
        return {
            "threshold": threshold_value,
            "count": 0,
            "items": [],
            "message": f"No low stock items found below {threshold_value} units.",
        }

    preview_limit = 25
    lines = [f"Low stock items (below {threshold_value} units):"]
    for record in low_stock[:preview_limit]:
        item_code = record.item_code or "N/A"
        lines.append(f" - {record.item_name} ({item_code}): {record.quantity}")
    if len(low_stock) > preview_limit:
        lines.append(f" ...and {len(low_stock) - preview_limit} more item(s).")

    payload_items = [
        {
            "item_code": record.item_code,
            "item_name": record.item_name,
            "quantity": record.quantity,
        }
        for record in low_stock[:50]
    ]

    return {
        "threshold": threshold_value,
        "count": len(low_stock),
        "items": payload_items,
        "truncated": len(low_stock) > 50,
        "message": "\n".join(lines),
    }

def remove_expired_stock(db, item: str, quantity: int, reason: str = "expired", user_id: int = 1):
    if not item or item.strip().lower() in {"item", "items", ""}:
        return {"error": "Please provide a valid item name to remove from stock."}
    if quantity <= 0:
        return {"error": "Quantity to remove must be greater than zero."}

    # Find closest match safely
    product = _resolve_inventory_item(item, db)

    if not product:
        return {"error": f"Item '{item}' not found in inventory."}

    if product.quantity < quantity:
        return {"error": f"Cannot remove {quantity} units. Only {product.quantity} units of '{product.item_name}' available in stock."}

    product.quantity -= quantity
    db.commit()

    return {
        "status": "Stock Removed",
        "item": product.item_name,
        "quantity_removed": quantity,
        "remaining_quantity": product.quantity,
        "message": f"Successfully removed {quantity} units of '{product.item_name}' due to: {reason}. Remaining stock: {product.quantity}.",
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


def cancel_purchase_order(
    po_id: str | int,
    db,
    cancellation_reason: str | None = None,
    user_id: int = 1,
):
    from app.services.email_service import send_po_cancellation_email

    po = _resolve_purchase_order(po_id, db)
    if not po:
        return {"error": f"Purchase order with ID '{po_id}' not found."}

    current_status = (po.status or "Pending").strip()
    normalized_status = current_status.lower()

    if normalized_status == "cancelled":
        return {
            "status": "PO Already Cancelled",
            "po_id": po.po_id or str(po.id),
            "message": f"Purchase order {po.po_id or po.id} is already cancelled."
        }

    if normalized_status == "delivered":
        return {
            "error": f"Purchase order {po.po_id or po.id} is already delivered and cannot be cancelled."
        }

    po.status = "Cancelled"
    db.commit()
    db.refresh(po)

    reason_text = (cancellation_reason or "Cancelled by requester.").strip()
    email_result = {"email_sent": False, "reason": "Vendor not found in database"}
    vendor_record = db.query(Vendor).filter(
        Vendor.vendor_name.ilike(f"%{po.vendor}%")
    ).first()

    if vendor_record and vendor_record.email:
        email_result = send_po_cancellation_email(
            vendor_name=vendor_record.vendor_name,
            vendor_email=vendor_record.email,
            po_id=po.po_id or str(po.id),
            item_name=po.item_name,
            quantity=po.quantity,
            cancellation_reason=reason_text,
        )
    elif vendor_record and not vendor_record.email:
        email_result = {
            "email_sent": False,
            "reason": f"No email on file for vendor '{vendor_record.vendor_name}'",
        }

    return {
        "status": "PO Cancelled",
        "po_id": po.po_id or str(po.id),
        "item": po.item_name,
        "quantity": po.quantity,
        "vendor": po.vendor,
        "previous_status": current_status,
        "cancellation_reason": reason_text,
        "email_notification": email_result,
        "message": f"Purchase order {po.po_id or po.id} has been cancelled.",
    }


# --- Vendor helpers ---
def _generate_vendor_code(vendor_name: str, db) -> str:
    base = re.sub(r"[^A-Z0-9]+", "", (vendor_name or "").upper())
    base = base[:4] or "VEND"
    prefix = f"V{base}"

    existing_codes = db.query(Vendor.vendor_code).filter(Vendor.vendor_code.ilike(f"{prefix}%")).all()
    max_seq = 0
    for (code,) in existing_codes:
        match = re.search(r"(\d+)$", code or "")
        if match:
            max_seq = max(max_seq, int(match.group(1)))

    return f"{prefix}{max_seq + 1:03d}"


# Add vendor
def add_vendor(
    vendor_name: str,
    db,
    vendor_code: str | None = None,
    item_category: str | None = None,
    location: str | None = None,
    email: str | None = None,
    item_name: str | None = None,
    price: float | None = None,
    user_id: int = 1,
):
    if not vendor_name or not vendor_name.strip():
        return {"error": "Vendor name is required."}

    normalized_name = vendor_name.strip()
    normalized_category = (item_category or item_name or "General").strip()
    normalized_location = (location or "Unknown").strip()
    normalized_email = email.strip() if isinstance(email, str) and email.strip() else None
    normalized_code = vendor_code.strip().upper() if isinstance(vendor_code, str) and vendor_code.strip() else _generate_vendor_code(normalized_name, db)

    existing = db.query(Vendor).filter(Vendor.vendor_code == normalized_code).first()
    if existing:
        normalized_code = _generate_vendor_code(normalized_name, db)

    vendor_kwargs = {
        "vendor_code": normalized_code,
        "vendor_name": normalized_name,
        "location": normalized_location,
        "item_category": normalized_category,
    }
    if normalized_email is not None:
        vendor_kwargs["email"] = normalized_email

    vendor = Vendor(**vendor_kwargs)

    db.add(vendor)
    db.commit()
    db.refresh(vendor)

    return {
        "status": "Vendor Added",
        "vendor_code": vendor.vendor_code,
        "email": normalized_email,
        "item_category": vendor.item_category,
        "location": vendor.location,
        "note": "Price is not stored in vendor schema." if price is not None else None,
    }


# Update vendor details (email supported, price ignored for backward compatibility)
def update_vendor(
    vendor_name: str,
    db,
    email: str | None = None,
    price: float | None = None,
    user_id: int = 1,
):
    vendor = db.query(Vendor).filter(
        Vendor.vendor_name.ilike(f"%{vendor_name}%")
    ).first()

    if not vendor:
        return {"error": f"Vendor '{vendor_name}' not found."}

    updated_fields = []
    if email is not None:
        vendor.email = email
        updated_fields.append(f"email -> {email}")

    if price is not None:
        updated_fields.append("price ignored (not tracked in vendor schema)")

    if not updated_fields:
        return {"error": "No fields to update. Provide email (price updates are not supported)."}

    if email is not None:
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
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m-%d-%Y", "%m/%d/%Y"):
            try:
                parsed_date = datetime.strptime(leave_date, fmt).date()
                break
            except ValueError:
                continue
        
        if not parsed_date:
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
            # If item is a placeholder or looks like a PO ID, resolve from PO record
            _is_placeholder = (
                item_lower in ("item", "items", "")
                or re.match(r"^\d{6}-[a-z0-9]+-\d{3}$", item_lower)  # PO ID mistakenly used as item
                or re.match(r"^\d+$", item_lower)                     # bare number
            )
            if _is_placeholder:
                item = po.item_name
                item_lower = item.lower()
            # If quantity is 0 or not provided, use PO quantity
            if quantity <= 0:
                quantity = po.quantity
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
        product = _resolve_inventory_item(item_lower, db)

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

# Get leaves today
def get_leaves_today(db, user_id: int = 1):
    today = datetime.now().date()
    # Find all leave applications for today matching 'date'
    leaves = db.query(LeaveApplication).filter(
        LeaveApplication.leave_date == today
    ).all()
    
    if not leaves:
        return {"message": "No one is on leave today.", "date": str(today)}
        
    lines = [f"Leaves for today ({today}):"]
    for l in leaves:
        status_info = f"[{l.admin_remark}]" if l.admin_remark else "[Pending]" if not getattr(l, 'status', None) else f"[{getattr(l, 'status', 'Pending')}]"
        lines.append(f" - {l.username} (Type: {l.leave_type}) Reason: {l.reason} {status_info}")
        
    return {"message": "\n".join(lines), "count": len(leaves), "date": str(today)}

# Generate daily purchase report
def generate_daily_purchase_report(db, user_id: int = 1):
    today = datetime.now().date()
    
    # Query all POs created today 
    # Use exact date bounds or cast depending on DB. SQLite allows Startswith.
    # We will fetch all and filter in memory to be safe across DB backends.
    today_str = today.strftime("%Y-%m-%d")
    all_pos = db.query(PurchaseOrder).all()
    
    today_pos = [po for po in all_pos if po.created_at and isinstance(po.created_at, datetime) and po.created_at.date() == today]
    # For string-based dates
    if not today_pos:
        today_pos = [po for po in all_pos if str(po.created_at).startswith(today_str)]
        
    if not today_pos:
        return {"message": f"No purchase orders were processed today ({today_str}).", "date": today_str}
        
    report = [
        "==================================================",
        "           DAILY PURCHASE REPORT",
        f"           DATE: {today_str}",
        "=================================================="
    ]
    
    total_spend = 0.0
    
    for idx, po in enumerate(today_pos, 1):
        # Resolve MRP 
        price = 0.0
        inv_item = db.query(Inventory).filter(Inventory.item_name.ilike(f"%{po.item_name}%")).first()
        if inv_item and inv_item.mrp:
            price = float(inv_item.mrp)
            
        total_price = price * po.quantity
        total_spend += total_price
        
        report.append(f"{idx}. PO ID: {po.po_id or po.id} | Vendor: {po.vendor}")
        report.append(f"   Item: {po.item_name} (Qty: {po.quantity})")
        report.append(f"   Rate: ₹{price:.2f} | Total: ₹{total_price:.2f}")
        report.append("   -----------------------------------------------")
        
    report.append(f"GRAND TOTAL DECLARED: ₹{total_spend:.2f}")
    report.append("==================================================")
    
    return {
        "message": "\n".join(report),
        "total_spend": total_spend,
        "count": len(today_pos)
    }


