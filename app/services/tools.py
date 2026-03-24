import os
from datetime import date, datetime

from app.models.inventory import Inventory
from app.models.leave_application import LeaveApplication
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.models.vendor import Vendor


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
    to the legacy numeric primary key for backward compatibility.
    """
    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == str(po_id)).first()
    if po:
        return po

    try:
        numeric_id = int(str(po_id))
    except (TypeError, ValueError):
        return None

    return db.query(PurchaseOrder).filter(PurchaseOrder.id == numeric_id).first()


# Create purchase order
def create_purchase_order(item: str, quantity: int, db, vendor_name: str = "default_vendor", user_id: int = 1):
    from app.services.email_service import send_po_email

    # --- Resolve item_code from inventory ---
    inv_item = db.query(Inventory).filter(
        Inventory.item_name.ilike(f"%{item.lower()}%")
    ).first()
    item_code = inv_item.item_code if inv_item and inv_item.item_code else f"GEN-{item[:3].upper()}"

    # --- Generate dynamic PO ID ---
    po_id_str = _generate_po_id(item_code, db)

    purchase_order = PurchaseOrder(
        po_id=po_id_str,
        item_name=item.lower(),
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
            Vendor.item_name.ilike(f"%{item}%")
        ).first()
        if vendor_record:
            print(f"[PO EMAIL] Matched vendor '{vendor_record.vendor_name}' by item '{item}'")

    print(f"[PO EMAIL] Vendor lookup for '{vendor_name}' / item '{item}': "
          f"{'Found ' + vendor_record.vendor_name + ' (email: ' + str(vendor_record.email) + ')' if vendor_record else 'NOT FOUND'}")

    if vendor_record and vendor_record.email:
        email_result = send_po_email(
            vendor_name=vendor_record.vendor_name,
            vendor_email=vendor_record.email,
            po_id=purchase_order.po_id,
            item_name=item,
            quantity=quantity
        )
    elif vendor_record and not vendor_record.email:
        email_result = {"email_sent": False, "reason": f"No email on file for vendor '{vendor_record.vendor_name}'"}

    return {
        "status": "PO Created",
        "item": item,
        "item_code": item_code,
        "quantity": quantity,
        "vendor_name": vendor_name,
        "po_id": purchase_order.po_id,
        "email_notification": email_result
    }


# Add vendor
def add_vendor(vendor_name: str, item_name: str, price: float, db, email: str = None, user_id: int = 1):

    vendor = Vendor(
        vendor_name=vendor_name,
        item_name=item_name,
        price=price,
        email=email
    )

    db.add(vendor)
    db.commit()
    db.refresh(vendor)

    return {
        "status": "Vendor Added",
        "vendor_id": vendor.id,
        "email": email
    }


# Update vendor details (especially email)
def update_vendor(vendor_name: str, db, email: str = None, price: float = None, user_id: int = 1):
    vendor = db.query(Vendor).filter(
        Vendor.vendor_name.ilike(f"%{vendor_name}%")
    ).first()

    if not vendor:
        return {"error": f"Vendor '{vendor_name}' not found."}

    updated_fields = []
    if email is not None:
        vendor.email = email
        updated_fields.append(f"email → {email}")
    if price is not None:
        vendor.price = price
        updated_fields.append(f"price → {price}")

    if not updated_fields:
        return {"error": "No fields to update. Provide email or price."}

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
            "id": v.id,
            "vendor_name": v.vendor_name,
            "item_name": v.item_name,
            "price": v.price,
            "email": v.email
        }
        for v in vendors
    ]


# Get PO status
def get_po_status(po_id: str, db, user_id: int = 1):
    po = _resolve_purchase_order(po_id, db)
    if not po:
        return {"error": f"Purchase order with ID '{po_id}' not found."}

    # Try to find the vendor's price to calculate cost
    # Strategy: vendor+item match → item-only vendor match → inventory MRP
    price = 0.0

    # 1. Exact match: vendor name + item name
    vendor = db.query(Vendor).filter(
        Vendor.vendor_name.ilike(f"%{po.vendor}%"),
        Vendor.item_name.ilike(f"%{po.item_name}%")
    ).first()

    if vendor and vendor.price:
        price = vendor.price
    else:
        # 2. Fallback: any vendor that supplies this item
        vendor_by_item = db.query(Vendor).filter(
            Vendor.item_name.ilike(f"%{po.item_name}%")
        ).first()
        if vendor_by_item and vendor_by_item.price:
            price = vendor_by_item.price
        else:
            # 3. Fallback: use inventory MRP
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
def update_inventory_stock(item: str, quantity: int, db, po_id: str = None, user_id: int = 1):
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
