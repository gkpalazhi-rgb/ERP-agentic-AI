from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.models.vendor import Vendor
import os


# Check inventory
def get_inventory(item: str, db):

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
    # The requirement is just to return them. Let's return the first one's format, 
    # but aggregate the message if there are multiple.
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
def create_purchase_order(item: str, quantity: int, db, vendor_name: str = "default_vendor"):

    purchase_order = PurchaseOrder(
        item_name=item.lower(),
        quantity=quantity,
        vendor=vendor_name
    )

    db.add(purchase_order)
    db.commit()
    db.refresh(purchase_order)

    return {
        "status": "PO Created",
        "item": item,
        "quantity": quantity,
        "vendor_name": vendor_name,
        "po_id": purchase_order.id
    }


# Add vendor
def add_vendor(vendor_name: str, item_name: str, price: float, db):

    vendor = Vendor(
        vendor_name=vendor_name,
        item_name=item_name,
        price=price
    )

    db.add(vendor)
    db.commit()
    db.refresh(vendor)

    return {
        "status": "Vendor Added",
        "vendor_id": vendor.id
    }


# Get vendor list
def get_vendors(db):

    vendors = db.query(Vendor).all()

    return [
        {
            "id": v.id,
            "vendor_name": v.vendor_name,
            "item_name": v.item_name,
            "price": v.price
        }
        for v in vendors
    ]


# Get PO status
def get_po_status(po_id: int, db):
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
        "status": "Processing",
        "item": po.item_name,
        "quantity": po.quantity,
        "vendor": po.vendor,
        "total_cost": total_cost,
        "price_per_unit": price
    }


# Generate Purchase Invoice
def generate_purchase_invoice(po_id: int, db):
    po_details = get_po_status(po_id, db)
    
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