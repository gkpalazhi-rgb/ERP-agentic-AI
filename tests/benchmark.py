import time
import sys
import os

# Ensure the app context is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.intent_classifier import classify_and_plan, preload_model

queries = [
    ("inventory check", "check_inventory"),
    ("how much stock of ashwagandha capsules", "check_inventory"),
    ("check stock for paracetamol bottles", "check_inventory"),
    ("do we have enough chyawanprash left", "check_inventory"),
    ("current quantity of triphala churnam", "check_inventory"),
    ("show me stock levels for syringes", "check_inventory"),
    ("how many neem tablets remaining", "check_inventory"),
    ("what's the balance stock of arishtam", "check_inventory"),
    ("check if we are low on glucose bottles", "check_inventory"),
    ("available inventory for giloy juice", "check_inventory"),
    ("tell stock status of turmeric capsules urgently", "check_inventory"),
    ("how much left... that ayurvedic oil one", "check_inventory"),

    ("create po for 50 ashwagandha capsules", "create_purchase_order"),
    ("order 20 bottles of cough syrup", "create_purchase_order"),
    ("buy more neem tablets", "create_purchase_order"),
    ("procure 100 syringes from medsuppliers", "create_purchase_order"),
    ("we need to restock chyawanprash urgently", "create_purchase_order"),
    ("place purchase order for 200 giloy juice", "create_purchase_order"),
    ("arrange 30 turmeric powder packets", "create_purchase_order"),
    ("get stock ready for triphala churnam 60 units", "create_purchase_order"),
    ("purchase arishtam 40 bottles", "create_purchase_order"),
    ("i want to order 25 insulin syringes", "create_purchase_order"),
    ("make a po for that oil we always use", "create_purchase_order"),
    ("order stuff quickly", "create_purchase_order"), 

    ("status of po 12345", "get_po_status"),
    ("track purchase order AYU-2303-001", "get_po_status"),
    ("where is my order #55", "get_po_status"),
    ("has po 260324-AYU001-001 been delivered", "get_po_status"),
    ("check po status for XYZ-999", "get_po_status"),
    ("is my purchase order still pending", "get_po_status"),
    ("did the order for syringes arrive", "get_po_status"),
    ("what is the delivery status of po 876", "get_po_status"),
    ("po update needed for last order", "get_po_status"),
    ("has that order been approved or shipped", "get_po_status"),

    ("generate invoice for po 12345", "generate_invoice"),
    ("create bill for AYU-2303-001", "generate_invoice"),
    ("download receipt for order #55", "generate_invoice"),
    ("print invoice for last purchase", "generate_invoice"),
    ("i need invoice for XYZ-999", "generate_invoice"),
    ("make billing for the recent po", "generate_invoice"),
    ("can you give me the receipt for that order", "generate_invoice"),
    ("invoice for syringes purchase", "generate_invoice"),
    ("generate bill for po 260324-AYU001-001", "generate_invoice"),
    ("show invoice document", "generate_invoice"),

    ("list all vendors", "get_vendors"),
    ("who supplies ashwagandha", "get_vendors"),
    ("vendors for syringes", "get_vendors"),
    ("show supplier list", "get_vendors"),
    ("which vendor provides giloy juice", "get_vendors"),
    ("get me all suppliers for ayurvedic oils", "get_vendors"),
    ("who are our current vendors", "get_vendors"),
    ("find vendor for turmeric powder", "get_vendors"),
    ("vendor details for capsules", "get_vendors"),
    ("who sells arishtam to us", "get_vendors"),

    ("add new vendor medlife suppliers email med@life.com for syringes", "add_vendor"),
    ("register vendor ayu pharma for capsules", "add_vendor"),
    ("onboard supplier herbal world email herbal@world.com", "add_vendor"),
    ("add vendor for turmeric powder with price 120", "add_vendor"),
    ("new vendor: greenleaf, supplies giloy juice", "add_vendor"),
    ("create vendor entry for medsuppliers syringes", "add_vendor"),
    ("add supplier dr herbs email dr@herbs.com", "add_vendor"),
    ("register vendor for arishtam bottles", "add_vendor"),
    ("add vendor quickmed for insulin syringes", "add_vendor"),
    ("include new supplier ayurveda store", "add_vendor"),

    ("update vendor medlife email to new@life.com", "update_vendor"),
    ("change price of syringes vendor to 150", "update_vendor"),
    ("modify vendor herbal world contact info", "update_vendor"),
    ("update supplier for capsules", "update_vendor"),
    ("edit vendor details for ayu pharma", "update_vendor"),
    ("change vendor email for greenleaf", "update_vendor"),
    ("update price for turmeric vendor", "update_vendor"),
    ("correct vendor name for medsuppliers", "update_vendor"),
    ("update supplier info for arishtam", "update_vendor"),
    ("change vendor contact number", "update_vendor"),

    ("apply leave tomorrow", "apply_leave"),
    ("i need sick leave for 2 days", "apply_leave"),
    ("book leave on 25th march", "apply_leave"),
    ("i won't be coming today", "apply_leave"),
    ("request half day leave", "apply_leave"),
    ("leave application for personal reasons", "apply_leave"),
    ("mark me absent tomorrow", "apply_leave"),
    ("i need a day off", "apply_leave"),
    ("apply leave next monday urgent", "apply_leave"),
    ("take leave for medical reasons", "apply_leave"),
    ("i am on leave today", "apply_leave"),
    ("leave pls", "apply_leave"),

    ("stock arrived for po 12345", "stock_arrival"),
    ("mark delivery received for AYU-2303-001", "stock_arrival"),
    ("goods received 50 syringes", "stock_arrival"),
    ("update stock arrival for capsules", "stock_arrival"),
    ("delivery of turmeric powder received", "stock_arrival"),
    ("items from po XYZ-999 arrived", "stock_arrival"),
    ("log stock arrival for giloy juice", "stock_arrival"),
    ("warehouse received 30 bottles", "stock_arrival"),
    ("mark po 260324-AYU001-001 as delivered", "stock_arrival"),
    ("inventory received for arishtam", "stock_arrival"),
    ("goods have been delivered", "stock_arrival"),
    ("shipment came in today", "stock_arrival"),

    ("hello", None),
    ("what is the weather today", None),
    ("tell me a joke", None),
    ("how does erp system work", None),
    ("list all purchase orders", None),
    ("how many pending orders do we have", None),
    ("give me analytics of inventory trends", None),
    ("who approved the last po", None),
    ("why is stock always low", None),
    ("leave the boxes in the warehouse", None),
    ("i need a leave of absence from reality lol", None),
    ("asdjkhaskjdh askjdhakjsd", None)
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
