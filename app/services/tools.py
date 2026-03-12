from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.models.vendor import Vendor
from app.models.leave_application import LeaveApplication
from app.models.user import User
import os
from datetime import datetime


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

# Create purchase order
def create_purchase_order(item: str, quantity: int, db, vendor_name: str = "default_vendor", user_id: int = 1):
    from app.services.email_service import send_po_email

    purchase_order = PurchaseOrder(
        item_name=item.lower(),
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
            po_id=purchase_order.id,
            item_name=item,
            quantity=quantity
        )
    elif vendor_record and not vendor_record.email:
        email_result = {"email_sent": False, "reason": f"No email on file for vendor '{vendor_record.vendor_name}'"}

    return {
        "status": "PO Created",
        "item": item,
        "quantity": quantity,
        "vendor_name": vendor_name,
        "po_id": purchase_order.id,
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
def get_po_status(po_id: int, db, user_id: int = 1):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    
    if not po:
        return {"error": f"Purchase order with ID {po_id} not found."}

    # Try to find the vendor's price to calculate cost
    vendor = db.query(Vendor).filter(
        Vendor.vendor_name.ilike(f"%{po.vendor}%"), 
        Vendor.item_name.ilike(f"%{po.item_name}%")
    ).first()
    
    price = getattr(vendor, 'price', 0.0)
    total_cost = price * po.quantity if price else 0.0

    return {
        "po_id": po.id,
        "status": po.status,
        "item": po.item_name,
        "quantity": po.quantity,
        "vendor": po.vendor,
        "total_cost": total_cost,
        "price_per_unit": price
    }


# Generate Purchase Invoice
def generate_purchase_invoice(po_id: int, db, user_id: int = 1):
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
QUANTITY:      {po_details['quantity']}
UNIT PRICE:    ₹{po_details['price_per_unit']:.2f}
--------------------------------------------------
TOTAL DUE:     ₹{po_details['total_cost']:.2f}
==================================================
Authorized by: ERP AI Agent
"""

    # Ensure the invoices directory exists
    os.makedirs("invoices", exist_ok=True)

    filename = f"invoices/po_invoice_{po_id}.txt"
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
def update_inventory_stock(item: str, quantity: int, db, po_id: int = None, user_id: int = 1):
    """
    Increments inventory quantity for an item. 
    Cross-references with purchase_orders to prevent 'fake' stock additions.
    """
    try:
        item_lower = item.lower()
        po = None
        
        # 1. CROSS-REFERENCE LOGIC
        if po_id:
            # Strict match: Check the specific PO
            po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
            if not po:
                return {"error": f"Security Alert: Purchase Order #{po_id} does not exist. Stock arrival rejected."}
            if po.status == "Delivered":
                return {"error": f"Security Alert: Stock for PO #{po_id} has already been received. Data duplication prevented."}
            # Verify item matches (allow loose matching)
            if item_lower not in po.item_name.lower() and po.item_name.lower() not in item_lower:
                return {"error": f"Data Mismatch: PO #{po_id} is for '{po.item_name}', but you reported '{item}'. Verification failed."}
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
            "message": f"Verified against PO #{po.id}. Inventory for {product.item_name} {action}. Total now: {product.quantity}. PO status marked as Delivered."
        }
    except Exception as e:
        return {"error": f"Verification failed: {str(e)}"}