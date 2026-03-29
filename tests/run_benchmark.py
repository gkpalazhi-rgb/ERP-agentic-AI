import time
import sys
import os

# Ensure the app context is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.intent_classifier import classify_and_plan, preload_model

queries = [
    # ---- 1. Inventory Check ----
    ("check inventory for bottles", "check_inventory"),
    ("do we have any amber bottles left in the warehouse", "check_inventory"),
    ("what is the stock of DHANWANTHARAM SOFT GEL CAPSULE", "check_inventory"),
    ("how many left?", "check_inventory"),
    ("stock levels for generic meds", "check_inventory"),
    ("any capsules available right now?", "check_inventory"),
    ("inventory balance for item 42", "check_inventory"),

    # ---- 2. Purchase Order Creation ----
    ("create a purchase order for 50 bottles", "create_purchase_order"),
    ("we need to buy more arishtam immediately", "create_purchase_order"),
    ("procure exactly 100 boxes of paracetamol from Medix", "create_purchase_order"),
    ("place order for 20 units of vicks", "create_purchase_order"),
    ("i want to purchase 15 items of shampoo", "create_purchase_order"),
    ("can you order 500 syringes", "create_purchase_order"),

    # ---- 3. PO Status (with and without ID) ----
    ("status of PO 260324-AYU001-001", "get_po_status"),
    ("what is the current status of order 260324-AYU001-001", "get_po_status"),
    ("has my order 1234 been delivered", "get_po_status"),
    ("where is PO abc-999", "get_po_status"),
    ("status of po", "get_po_status"), # Misses po_id, but intent should be get_po_status
    ("track order #999", "get_po_status"),

    # ---- 4. Invoicing ----
    ("generate invoice for PO 260324-AYU001-001", "generate_invoice"),
    ("can you get me the bill for this PO 5", "generate_invoice"),
    ("print receipt for order 99", "generate_invoice"),
    ("invoice 12345", "generate_invoice"),

    # ---- 5. Vendors ----
    ("show all vendors", "get_vendors"),
    ("who supplies us with dropper bottles", "get_vendors"),
    ("list our suppliers", "get_vendors"),
    ("add supplier generic pharma for items", "add_vendor"),
    ("onboard new vendor Acme Corp for anvils at 50", "add_vendor"),
    ("change pricing for vendor medix to 40", "update_vendor"),
    ("update email for supplier ABC to admin@abc.com", "update_vendor"),

    # ---- 6. Leaves ----
    ("apply leave for tomorrow", "apply_leave"),
    ("i need to take a sick day next monday", "apply_leave"),
    ("request 1st half leave on 25th because of doctor appointment", "apply_leave"),
    ("i am feeling unwell today", "apply_leave"),

    # ---- 7. Stock Arrival (Update Inventory) ----
    ("50 bottles have arrived", "stock_arrival"),
    ("the shipment of 100 capsules was just delivered to us", "stock_arrival"),
    ("received 20 boxes of generic items", "stock_arrival"),
    ("po 123 arrived with 50 units", "stock_arrival"),

    # ---- 8. Outliers / Bugs / Edge Cases ----
    ("how many amrutha shampoo", "check_inventory"), # po substring trigger (Fixed)
    ("how many pending orders remaining", None), # Unsupported list request (Fixed)
    ("list all purchase orders", None), # Unsupported list request
    ("show me all pending pos", None), # Unsupported list request
    ("generate a bill for purchase order 99", "generate_invoice"), # bill + purchase
    ("is purchase order pending", "get_po_status"), # generic matcher
    ("i need a new PO for shampoo", "create_purchase_order"), 
    ("are there any more leaves available?", "apply_leave"), # Wait, asking available -> probably apply?
    ("hello, how are you", None), # Chit chat
    ("tell me a joke", None), # Chit chat
    ("inventory", "check_inventory"), # One word
    ("leaves", "apply_leave"), # One word
    ("what is erp", None), # General question
    ("a"*100, None), # Garbage input
    ("add vendor without any price", "add_vendor"), 
]

def run_benchmark():
    print("Preloading model (simulating startup)...")
    start_load = time.time()
    preload_model()
    load_time = (time.time() - start_load) * 1000
    print(f"Model Preload Time: {load_time:.2f} ms\n")
    
    print(f"{'Query':<65} | {'Expected':<22} | {'Predicted':<22} | {'Time (ms)':<10} | {'Correct'}")
    print("-" * 140)
    
    total_time = 0
    correct = 0
    failed_cases = []
    
    for query, expected in queries:
        start_time = time.time()
        plan, metadata = classify_and_plan(query)
        end_time = time.time()
        
        elapsed_ms = (end_time - start_time) * 1000
        total_time += elapsed_ms
        
        predicted = metadata.get("intent") if metadata else None
        
        # Consider correct if intent matches (or if we expect None and it's None)
        is_correct = predicted == expected
        if is_correct:
            correct += 1
        else:
            failed_cases.append((query, expected, predicted))
            
        print(f"{query[:63]:<65} | {str(expected):<22} | {str(predicted):<22} | {elapsed_ms:<10.2f} | {is_correct}")
        
    print("-" * 140)
    print(f"Total Classifier Queries: {len(queries)}")
    print(f"Average Classifier Latency: {total_time / len(queries):.2f} ms")
    print(f"Classifier Accuracy: {correct / len(queries) * 100:.2f}%\n")
    
    if failed_cases:
        print("FAILED CASES:")
        for q, e, p in failed_cases:
            print(f" - '{q}' -> Expected: {e}, Got: {p}")

if __name__ == '__main__':
    run_benchmark()
